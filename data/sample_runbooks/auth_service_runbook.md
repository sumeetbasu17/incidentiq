# AuthService Runbook
## Service Overview
AuthService manages user authentication, JWT token issuance, OAuth2 flows, and session management. It is a critical-path service — if AuthService is down, no user can log in.

## Architecture
- **Language:** Java 17 (Spring Boot 3.x)
- **Database:** PostgreSQL 15 (user credentials, sessions)
- **Cache:** Redis 7.x (JWT blocklist, rate limiting)
- **External:** Google OAuth, GitHub OAuth, SAML providers

## Common Issues

### JWT Token Validation Failure
**Symptoms:** `io.jsonwebtoken.ExpiredJwtException`, mass user logouts, 401 errors across all services.

**Root Cause:** Usually:
1. Clock skew between auth-service pods and downstream services
2. JWT signing key rotation without proper grace period
3. Redis blocklist unavailable (false positive revocations)

**Resolution:**
1. **Check clock sync:** `kubectl exec -it auth-service-pod -- date` vs `date` on other service pods
2. **Verify signing key:** `curl -s http://auth-service:8080/actuator/health | jq .components.jwt`
3. **Redis check:** `redis-cli -h redis-auth GET jwt_signing_key_version`
4. **Emergency fix:** Set `JWT_CLOCK_SKEW_TOLERANCE=120` (seconds) and restart

### NullPointerException in UserService
**Symptoms:** `java.lang.NullPointerException at com.company.auth.service.UserService.getUserById`

**Root Cause:** 
1. Database query returns null for deleted/deactivated users
2. Missing null check in user lookup chain
3. Cache returns stale data after user deletion

**Resolution:**
1. **Identify affected user:** Check logs for user_id in the stack trace
2. **Check DB:** `SELECT * FROM users WHERE id = '<user_id>' AND deleted_at IS NULL;`
3. **Clear cache:** `redis-cli -h redis-auth DEL user:<user_id>`
4. **Hotfix:** Add null safety check — PR already exists: JIRA-4521

### Rate Limiting Triggering False Positives
**Symptoms:** Legitimate users getting 429 Too Many Requests, especially during peak hours.

**Resolution:**
1. Check current limits: `redis-cli -h redis-auth GET rate_limit:config`
2. Temporarily increase: Set `RATE_LIMIT_PER_MINUTE=200` (default: 60)
3. Check for bot traffic: Review access logs for suspicious patterns
4. Long-term: Implement adaptive rate limiting based on user tier

## Health Checks
- Readiness: `GET /actuator/health/readiness`
- Liveness: `GET /actuator/health/liveness`
- Metrics: `GET /actuator/prometheus`

## Monitoring
- Grafana: https://grafana.internal/d/auth-service
- Alerts: PagerDuty escalation policy "auth-critical"
- SLO: 99.99% availability (critical path)
