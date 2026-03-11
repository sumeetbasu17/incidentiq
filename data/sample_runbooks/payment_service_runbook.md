# PaymentService Runbook
## Service Overview
PaymentService handles all payment processing for the platform. It connects to PostgreSQL (primary DB), Redis (caching), and Stripe API (payment gateway).

## Architecture
- **Language:** Python 3.11 (FastAPI)
- **Database:** PostgreSQL 15 via SQLAlchemy + asyncpg
- **Connection Pool:** Default max_connections=20, pool_timeout=30s
- **Cache:** Redis 7.x for session and idempotency keys
- **External APIs:** Stripe, PayPal

## Common Issues

### Database Connection Pool Exhaustion
**Symptoms:** `ConnectionError: Connection pool exhausted`, increasing latency, 500 errors on payment endpoints.

**Root Cause:** Usually caused by:
1. Long-running queries holding connections
2. Missing connection release in error paths
3. Sudden traffic spike beyond pool capacity
4. Deadlocks in concurrent transaction handling

**Resolution:**
1. **Immediate:** Restart the service pods: `kubectl rollout restart deployment/payment-service -n payments`
2. **Check connections:** `SELECT count(*) FROM pg_stat_activity WHERE datname='payments';`
3. **Kill idle connections:** `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='payments' AND state='idle' AND state_change < now() - interval '10 minutes';`
4. **Increase pool temporarily:** Set env `DB_MAX_CONNECTIONS=50` and redeploy
5. **Long-term:** Implement connection pool monitoring with PgBouncer

### Stripe API Timeout
**Symptoms:** `TimeoutError: Stripe API request timed out after 30s`, payment creation failures.

**Resolution:**
1. Check Stripe status page: https://status.stripe.com
2. Enable retry logic: Set `STRIPE_MAX_RETRIES=3` in config
3. Implement circuit breaker pattern for external API calls
4. Fallback: Queue failed payments for retry via Celery

### Redis Connection Failure
**Symptoms:** `ConnectionRefusedError: Redis connection refused`, cache miss spikes.

**Resolution:**
1. Check Redis health: `redis-cli -h redis-payments ping`
2. Check memory: `redis-cli info memory`
3. If OOM: `redis-cli FLUSHDB` (caution: clears cache)
4. Restart Redis: `kubectl rollout restart statefulset/redis-payments -n payments`

## Monitoring
- Grafana Dashboard: https://grafana.internal/d/payment-service
- PagerDuty Escalation: L1 (On-call SRE) → L2 (Payment Team Lead) → L3 (VP Engineering)
- SLO: 99.95% availability, p99 latency < 500ms

## Contacts
- Team Lead: Sarah Chen (sarah.chen@company.com)
- DB Admin: Mike Rodriguez (mike.r@company.com)
- On-call Slack: #payments-oncall
