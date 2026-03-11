"""
IncidentIQ - Sample Error Logs for Demo
Pre-built realistic error scenarios for impressive live demos.
"""

SAMPLE_LOGS = {
    "🐍 Python — DB Connection Pool Exhaustion": """2024-01-15T03:42:15.892Z [PaymentService] INFO  - Processing payment request order_id=ORD-98234 amount=149.99
2024-01-15T03:42:16.105Z [PaymentService] INFO  - Acquiring database connection from pool...
2024-01-15T03:42:17.234Z [PaymentService] WARN  - Connection pool utilization at 95% (19/20 connections)
2024-01-15T03:42:18.001Z [PaymentService] ERROR - Payment processing failed for order_id=ORD-98234

Traceback (most recent call last):
  File "/app/services/payment_service.py", line 142, in process_payment
    result = await db_pool.execute(query, params)
  File "/app/db/connection.py", line 89, in execute
    conn = await self._get_connection()
  File "/app/db/connection.py", line 45, in _get_connection
    raise ConnectionError("Connection pool exhausted: max_connections=20, active=20, waiting=15")
sqlalchemy.exc.TimeoutError: QueuePool limit of size 20 overflow 10 reached, connection timed out, timeout 30.00

2024-01-15T03:42:18.234Z [PaymentService] ERROR - 47 requests queued waiting for DB connections
2024-01-15T03:42:18.235Z [PaymentService] CRITICAL - Circuit breaker OPEN for database connections
2024-01-15T03:42:19.001Z [HealthCheck] WARN  - Service health degraded: database_pool=CRITICAL
2024-01-15T03:42:20.003Z [MetricsCollector] ERROR - p99 latency exceeded SLO: current=12.4s, threshold=0.5s""",

    "☕ Java — NullPointerException in Auth": """2024-01-15T08:15:33.445Z ERROR [auth-service] [http-nio-8080-exec-12] c.c.auth.controller.AuthController - Authentication failed for request_id=REQ-445521

java.lang.NullPointerException: Cannot invoke "com.company.auth.model.User.getRoles()" because the return value of "com.company.auth.service.UserService.getUserById(java.lang.String)" is null
    at com.company.auth.service.AuthenticationService.authenticate(AuthenticationService.java:87)
    at com.company.auth.controller.AuthController.login(AuthController.java:45)
    at java.base/jdk.internal.reflect.NativeMethodAccessorImpl.invoke0(Native Method)
    at org.springframework.web.servlet.FrameworkServlet.service(FrameworkServlet.java:885)
    at org.apache.catalina.core.ApplicationFilterChain.internalDoFilter(ApplicationFilterChain.java:178)
    at org.apache.catalina.connector.CoyoteAdapter.service(CoyoteAdapter.java:357)
    at org.apache.coyote.http11.Http11Processor.service(Http11Processor.java:400)

2024-01-15T08:15:33.446Z WARN  [auth-service] c.c.auth.service.UserService - User lookup returned null for user_id=USR-88901
2024-01-15T08:15:33.450Z ERROR [auth-service] c.c.auth.filter.ExceptionFilter - Responding with 500 Internal Server Error
2024-01-15T08:15:34.001Z WARN  [auth-service] c.c.auth.cache.RedisCache - Cache miss for key=user:USR-88901, TTL expired
2024-01-15T08:15:35.112Z ERROR [api-gateway] - 15 consecutive 500 errors from auth-service in last 60 seconds""",

    "🟢 Node.js — Memory Leak in API Gateway": """[2024-01-15T14:22:01.334Z] [API-Gateway] [PID:2847] INFO: Request processed - endpoint=/api/v2/products, duration=234ms
[2024-01-15T14:22:45.112Z] [API-Gateway] [PID:2847] WARN: Heap usage elevated - used=1.2GB, total=1.5GB (80%)
[2024-01-15T14:23:30.001Z] [API-Gateway] [PID:2847] WARN: Heap usage critical - used=1.45GB, total=1.5GB (96.7%)
[2024-01-15T14:23:31.889Z] [API-Gateway] [PID:2847] ERROR: Event loop lag detected: 2340ms (threshold: 100ms)

FATAL ERROR: Reached heap limit Allocation failed - JavaScript heap out of memory
 1: 0xb7a140 node::Abort() [/usr/local/bin/node]
 2: 0xb7a1be  [/usr/local/bin/node]
 3: 0xd4c360 v8::Utils::ReportOOMFailure(v8::internal::Isolate*, char const*, v8::OOMDetails const&) [/usr/local/bin/node]
 4: 0xd4c5e7 v8::internal::V8::FatalProcessOutOfMemory(v8::internal::Isolate*, char const*, v8::OOMDetails const&) [/usr/local/bin/node]
 5: 0xf2a335  [/usr/local/bin/node]

<--- Last few GCs --->
[2847:0x5629c60]   145234 ms: Scavenge 1489.2 (1520.8) -> 1488.9 (1520.8) MB, 12.4 / 0.0 ms
[2847:0x5629c60]   145891 ms: Mark-sweep 1489.5 (1520.8) -> 1487.2 (1520.8) MB, 234.1 / 0.0 ms

[2024-01-15T14:23:32.001Z] [Kubernetes] WARN: Pod api-gateway-7d9f8b6c4-x2k4p OOMKilled - restarting (restart count: 4)
[2024-01-15T14:23:32.005Z] [AlertManager] CRITICAL: api-gateway crash loop detected - 4 restarts in 15 minutes""",

    "🔵 Go — Goroutine Deadlock": """2024-01-15T21:08:44.234Z [OrderService] INFO starting order processing pipeline workers=10
2024-01-15T21:08:44.567Z [OrderService] INFO connected to message queue broker=kafka topic=orders
2024-01-15T21:09:12.889Z [OrderService] WARN goroutine count elevated: current=4521 baseline=200
2024-01-15T21:09:15.001Z [OrderService] ERROR request timeout on /api/orders/ORD-77812 duration=30.001s

fatal error: all goroutines are asleep - deadlock!

goroutine 1 [chan receive]:
main.main()
    /app/cmd/server/main.go:45 +0x2bc

goroutine 234 [chan send]:
github.com/company/order-service/internal/processor.(*OrderProcessor).Process(0xc000234000, {0xc0004be000, 0x24})
    /app/internal/processor/order_processor.go:112 +0x1a8

goroutine 235 [chan receive]:
github.com/company/order-service/internal/processor.(*OrderProcessor).collectResults(0xc000234000)
    /app/internal/processor/order_processor.go:145 +0x94

goroutine 236 [sync.Mutex.Lock]:
github.com/company/order-service/internal/inventory.(*InventoryClient).CheckStock(0xc000198000, {0xc0004c2000, 0x12})
    /app/internal/inventory/client.go:67 +0x7c

2024-01-15T21:09:15.002Z [Kubernetes] ERROR pod order-service-5f4d8c9b7-m3k9p terminated: exit code 2
2024-01-15T21:09:15.003Z [PagerDuty] ALERT triggered: order-service crash - goroutine deadlock detected""",

    "📝 Plain Text — Describe Your Incident": "",
}
