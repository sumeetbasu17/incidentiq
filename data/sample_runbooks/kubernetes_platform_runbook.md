# Kubernetes Platform — Incident Runbook
## Service Mesh & Container Orchestration

### Overview
This runbook covers incident response for our Kubernetes-based microservices platform running on EKS (us-east-1, us-west-2). All production services run in the `prod` namespace with Istio service mesh.

---

## Pod CrashLoopBackOff

### Symptoms
- Pod status shows `CrashLoopBackOff` in `kubectl get pods`
- Exponential backoff delays between restart attempts
- Service health checks failing in Datadog

### Investigation
```bash
# Check pod events
kubectl describe pod <pod-name> -n prod

# Check container logs (current crash)
kubectl logs <pod-name> -n prod --previous

# Check resource limits
kubectl top pod <pod-name> -n prod
```

### Common Causes
1. **OOMKilled**: Container exceeds memory limit. Check `Last State: Terminated, Reason: OOMKilled`
   - Fix: Increase `resources.limits.memory` in deployment manifest
   - Temporary: `kubectl set resources deployment/<name> --limits=memory=2Gi -n prod`

2. **Liveness probe failure**: App starts but becomes unhealthy
   - Check probe config: `kubectl get deployment <name> -o yaml | grep -A10 livenessProbe`
   - Common fix: Increase `initialDelaySeconds` for slow-starting apps

3. **Config/secret missing**: App crashes on startup due to missing env vars
   - Check: `kubectl get events -n prod --field-selector involvedObject.name=<pod>`
   - Fix: Verify ConfigMap and Secret references exist

### Escalation
L1: Platform SRE on-call (#platform-oncall)
L2: Service owner (check service catalog in Backstage)

---

## High Latency / P99 Spike

### Symptoms
- Datadog APM shows p99 latency > SLO threshold (typically 500ms)
- Istio dashboard shows increased request duration
- Downstream services reporting timeouts

### Investigation
```bash
# Check Istio metrics
kubectl exec -it $(kubectl get pod -l app=istio-ingressgateway -n istio-system -o jsonpath='{.items[0].metadata.name}') -n istio-system -- curl localhost:15000/stats

# Check HPA status (is it scaling?)
kubectl get hpa -n prod

# Check node resource pressure
kubectl top nodes
kubectl describe node <node-name> | grep -A5 Conditions
```

### Common Causes
1. **Database slow queries**: Check RDS Performance Insights
   - `SELECT * FROM pg_stat_activity WHERE state = 'active' AND query_start < now() - interval '5 seconds';`

2. **Noisy neighbor**: Another pod on the same node consuming CPU
   - Check with: `kubectl top pods -n prod --sort-by=cpu`
   - Fix: Add pod anti-affinity rules or request guaranteed QoS

3. **Connection pool exhaustion**: Upstream service running out of connections
   - Check Envoy sidecar stats: `kubectl exec <pod> -c istio-proxy -- curl localhost:15000/clusters`

4. **Cold start after deployment**: New pods warming caches
   - Implement readiness gates and preStop hooks

### SLO Reference
- API Gateway: p99 < 200ms
- Core Services: p99 < 500ms
- Batch Processing: p99 < 5s

---

## Node Not Ready

### Symptoms
- `kubectl get nodes` shows `NotReady` status
- Pods being evicted from the affected node
- Cluster autoscaler may be replacing the node

### Investigation
```bash
# Check node conditions
kubectl describe node <node-name> | grep -A20 Conditions

# Check kubelet logs
kubectl logs -n kube-system $(kubectl get pods -n kube-system -l component=kube-proxy --field-selector spec.nodeName=<node-name> -o name)

# Check AWS instance status
aws ec2 describe-instance-status --instance-ids <instance-id>
```

### Resolution
1. **Disk pressure**: Kubelet marks node NotReady when disk usage > 85%
   - Clean up: Delete old container images, log rotation
   - `docker system prune -a` or `crictl rmi --prune`

2. **Network**: Node lost connectivity to API server
   - Check security groups, NACLs, VPC flow logs
   - Verify kube-proxy is running

3. **Instance degraded**: AWS hardware issue
   - Cordon and drain: `kubectl cordon <node> && kubectl drain <node> --ignore-daemonsets --delete-emptydir-data`
   - Terminate instance, let ASG replace it

---

## Deployment Rollback

### When to Rollback
- Error rate increases > 1% within 5 minutes of deploy
- P99 latency doubles compared to pre-deploy baseline
- Any 5xx errors on critical paths (checkout, auth, payment)

### Procedure
```bash
# Check rollout history
kubectl rollout history deployment/<name> -n prod

# Rollback to previous version
kubectl rollout undo deployment/<name> -n prod

# Rollback to specific revision
kubectl rollout undo deployment/<name> -n prod --to-revision=<N>

# Verify rollback
kubectl rollout status deployment/<name> -n prod
```

### Post-Rollback
1. Create incident in PagerDuty
2. Post in #incidents Slack channel with timeline
3. Tag the failed commit in Git
4. Schedule blameless post-mortem within 48 hours

---

## Monitoring & Alerting
- **Datadog**: APM traces, infrastructure metrics, log management
- **PagerDuty**: Incident routing and escalation
- **Grafana**: Custom dashboards for service-specific metrics
- **Slack**: #prod-alerts (automated), #incidents (manual)

## Contacts
- Platform SRE Lead: platform-sre@company.com
- On-call rotation: managed via PagerDuty
- Escalation: VP Engineering (for SEV-1 only)
