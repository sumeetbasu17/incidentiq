# API Gateway & Load Balancer — Incident Runbook
## NGINX Ingress + AWS ALB + Rate Limiting

### Overview
Traffic flow: CloudFront → ALB → NGINX Ingress Controller → Kubernetes Services. Rate limiting enforced at NGINX level. WAF rules on ALB. SSL termination at ALB.

---

## 5xx Error Spike

### Symptoms
- ALB target group health checks failing
- CloudWatch: `HTTPCode_Target_5XX_Count` spike
- Users reporting "Internal Server Error" or blank pages

### Investigation
```bash
# Check NGINX ingress logs
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --tail=100

# Check ALB target health
aws elbv2 describe-target-health --target-group-arn <arn>

# Check backend pod readiness
kubectl get pods -n prod -o wide | grep -v Running
```

### Common Causes
1. **Backend pods not ready**: Deployment in progress or crash loop
   - Check: `kubectl get events -n prod --sort-by=.metadata.creationTimestamp | tail -20`
   
2. **Upstream timeout**: Backend taking too long to respond
   - NGINX default proxy_timeout: 60s
   - Fix: Check backend service latency in Datadog APM

3. **Resource exhaustion**: NGINX ingress controller out of memory/CPU
   - Check: `kubectl top pods -n ingress-nginx`
   - Fix: Scale ingress controller HPA

4. **SSL certificate expired**: ALB cannot terminate TLS
   - Check: `aws acm describe-certificate --certificate-arn <arn> | grep Status`

---

## Rate Limiting Triggers

### Symptoms
- Users getting 429 Too Many Requests
- NGINX logs: `limiting requests, excess: X.XXX`
- Customer complaints about being blocked

### Investigation
```bash
# Check current rate limit config
kubectl get configmap -n ingress-nginx ingress-nginx-controller -o yaml | grep rate

# Check which IPs are being limited
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx | grep "limiting requests" | awk '{print $NF}' | sort | uniq -c | sort -rn | head -10
```

### Resolution
1. **Legitimate traffic spike**: Temporarily increase limits
   - Edit ingress annotation: `nginx.ingress.kubernetes.io/limit-rps: "50"` (default: 20)
   
2. **Bot/scraper traffic**: Add IP to WAF block list
   - `aws wafv2 update-ip-set --name blocked-ips --addresses <ip>/32`

3. **Single customer impact**: Add per-customer allowlist
   - Use `nginx.ingress.kubernetes.io/whitelist-source-range` annotation

### Rate Limit Config Reference
- Public API: 20 req/sec per IP
- Authenticated API: 100 req/sec per user
- Webhook endpoints: 50 req/sec per source
- Health checks: No limit

---

## DNS / CloudFront Issues

### Symptoms
- `nslookup` returns wrong IP or NXDOMAIN
- CloudFront returning stale content or 502
- SSL certificate mismatch errors

### Investigation
```bash
# Check DNS resolution
dig +trace api.company.com
nslookup api.company.com 8.8.8.8

# Check CloudFront distribution
aws cloudfront get-distribution --id <dist-id> | jq '.Distribution.DistributionConfig.Origins'

# Check origin health
curl -v -H "Host: api.company.com" https://<alb-dns>/health
```

### Resolution
1. **DNS propagation delay**: Wait 60s for Route53 changes (TTL: 60)
2. **CloudFront cache**: Invalidate with `aws cloudfront create-invalidation --distribution-id <id> --paths "/*"`
3. **Origin failover**: CloudFront origin group should auto-failover. Check origin group config.

---

## Monitoring
- **CloudWatch**: ALB metrics, 4xx/5xx counts, latency
- **NGINX Dashboard**: Grafana dashboard for ingress controller metrics
- **Alerts**:
  - 5xx rate > 1% for 2 min → Page
  - p99 latency > 2s → Warn
  - SSL cert expiry < 30 days → Warn
  - Rate limit triggers > 1000/min → Investigate
