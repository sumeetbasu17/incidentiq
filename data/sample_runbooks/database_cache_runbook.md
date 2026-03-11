# Database & Cache — Incident Runbook
## PostgreSQL (RDS) + Redis (ElastiCache)

### Overview
Production databases: PostgreSQL 15 on RDS Multi-AZ (db.r6g.2xlarge). Cache layer: Redis 7.x on ElastiCache cluster mode (3 shards, 1 replica each). All services connect via PgBouncer connection pooler.

---

## PostgreSQL: Connection Pool Exhaustion

### Symptoms
- Application logs: `FATAL: too many connections for role "app_user"` or `connection pool exhausted`
- PgBouncer stats show high `cl_waiting` count
- New requests timing out while existing queries run

### Investigation
```sql
-- Active connections by state
SELECT state, count(*) FROM pg_stat_activity GROUP BY state;

-- Long-running queries (> 30 seconds)
SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '30 seconds'
AND state != 'idle'
ORDER BY duration DESC;

-- Connections by application
SELECT application_name, count(*) FROM pg_stat_activity GROUP BY application_name;

-- Check for locks
SELECT blocked.pid AS blocked_pid, blocked.query AS blocked_query,
       blocking.pid AS blocking_pid, blocking.query AS blocking_query
FROM pg_stat_activity AS blocked
JOIN pg_locks blocked_locks ON blocked.pid = blocked_locks.pid
JOIN pg_locks blocking_locks ON blocked_locks.locktype = blocking_locks.locktype
    AND blocked_locks.relation = blocking_locks.relation
JOIN pg_stat_activity AS blocking ON blocking_locks.pid = blocking.pid
WHERE NOT blocked_locks.granted;
```

### Resolution
1. **Immediate: Kill idle connections**
   ```sql
   SELECT pg_terminate_backend(pid) FROM pg_stat_activity
   WHERE datname = 'production' AND state = 'idle'
   AND state_change < now() - interval '10 minutes';
   ```

2. **Increase PgBouncer pool**: Edit parameter group, set `max_client_conn = 200`

3. **Find the leak**: Check application code for unclosed connections
   - Common: missing `finally` block in exception handlers
   - Common: long-lived transactions from batch jobs

4. **Long-term**: Implement connection pool monitoring
   - Add PgBouncer stats to Datadog
   - Alert when `cl_waiting > 10` for more than 2 minutes

### Connection Limits Reference
- RDS max_connections (r6g.2xlarge): 1624
- PgBouncer default_pool_size: 25 per user/db pair
- Application pool (per pod): 20 connections
- Target: Never exceed 80% of RDS max_connections

---

## PostgreSQL: Replication Lag

### Symptoms
- CloudWatch: `ReplicaLag` metric increasing
- Read-after-write inconsistencies reported by users
- Read replica falling behind primary

### Investigation
```sql
-- On primary: check replication slots
SELECT slot_name, active, restart_lsn, confirmed_flush_lsn FROM pg_replication_slots;

-- On replica: check lag
SELECT now() - pg_last_xact_replay_timestamp() AS replication_lag;
```

### Resolution
1. If lag < 30s: Usually transient, monitor
2. If lag > 60s: Check for long-running queries on replica blocking replay
3. If lag > 5m: Consider promoting replica and failing over
4. Check for large transactions or DDL operations on primary

---

## Redis: Memory Pressure / Eviction

### Symptoms
- CloudWatch: `EngineCPUUtilization > 80%` or `DatabaseMemoryUsagePercentage > 90%`
- Application logs: `OOM command not allowed when used memory > maxmemory`
- Increased cache miss rate in application metrics

### Investigation
```bash
# Connect to Redis
redis-cli -h <endpoint> -p 6379

# Memory overview
INFO memory

# Top keys by memory
redis-cli --bigkeys

# Key count and TTL distribution
redis-cli DBSIZE
redis-cli --scan --pattern "session:*" | head -20
```

### Resolution
1. **Immediate: Flush expired keys**
   - Redis is lazy about expiring keys — force a scan: `redis-cli --scan | head -10000 | xargs redis-cli OBJECT FREQ`
   
2. **Identify bloated keys**
   - `redis-cli MEMORY USAGE <key>` for suspected large keys
   - Common culprits: unbounded lists, large sorted sets, oversized hash maps

3. **Set TTLs**: Ensure all keys have TTL. No key should live forever.
   ```bash
   # Find keys without TTL
   redis-cli --scan | while read key; do
     ttl=$(redis-cli TTL "$key")
     if [ "$ttl" -eq "-1" ]; then echo "NO TTL: $key"; fi
   done
   ```

4. **Scale up**: Modify ElastiCache cluster to next instance size
   - Current: cache.r6g.large (13.07 GB)
   - Next: cache.r6g.xlarge (26.32 GB)

### Eviction Policy
Current: `allkeys-lru` — evicts least recently used keys when memory is full. This is correct for cache workloads. Do NOT change to `noeviction` in production.

---

## Redis: Connection Refused

### Symptoms
- Application logs: `ConnectionRefusedError: Redis connection refused`
- Sudden spike in cache miss rate
- All pods affected simultaneously

### Investigation
```bash
# Check ElastiCache events
aws elasticache describe-events --source-type cache-cluster --duration 60

# Check endpoint resolution
nslookup <redis-endpoint>

# Check security groups
aws ec2 describe-security-groups --group-ids <sg-id>
```

### Resolution
1. **Check failover**: ElastiCache may have failed over to replica
   - New primary endpoint should resolve automatically
   - If not, check application connection string

2. **Check maintenance window**: AWS may be patching
   - Verify in ElastiCache console > Maintenance tab

3. **Network**: Security group or NACL change blocking port 6379
   - Verify inbound rule allows app security group on port 6379

---

## Monitoring
- **CloudWatch**: RDS and ElastiCache metrics
- **Datadog**: Custom metrics from PgBouncer stats
- **Alerts**:
  - RDS CPU > 80% for 5 min → Page
  - Replica lag > 60s → Page
  - Redis memory > 85% → Warn
  - Redis memory > 95% → Page
  - PgBouncer cl_waiting > 10 → Warn
