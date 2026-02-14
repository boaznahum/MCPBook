# Chapter 23: Performance, Scaling, and Reliability

---

## 23.1 Latency Optimization in MCP Communication

MCP latency has several components:

```
Total Latency = Transport + Serialization + Handler + External API + Serialization + Transport
```

### Optimization Strategies

**Reduce serialization overhead:**
- Keep tool results concise — return only what the AI needs
- Avoid large JSON payloads — summarize instead of dumping raw data
- Use efficient data formats within text content

**Optimize handlers:**
```python
# Slow: synchronous database call
@mcp.tool()
async def query_slow(sql: str) -> str:
    import sqlite3
    conn = sqlite3.connect("db.sqlite")  # Blocking!
    result = conn.execute(sql).fetchall()
    conn.close()
    return format(result)

# Fast: async database call with connection pooling
@mcp.tool()
async def query_fast(sql: str) -> str:
    async with pool.acquire() as conn:  # Non-blocking, pooled
        rows = await conn.fetch(sql)
    return format(rows)
```

**Minimize external API calls:**
- Cache frequently-requested data
- Batch API calls where possible
- Use connection pooling for HTTP clients

---

## 23.2 Connection Pooling and Multiplexing

### Database Connection Pools

```python
import asyncpg

class DatabaseServer:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.pool = None

    async def startup(self):
        self.pool = await asyncpg.create_pool(
            self.db_url,
            min_size=5,    # Keep 5 connections ready
            max_size=20,   # Allow up to 20 concurrent connections
            command_timeout=30  # 30-second query timeout
        )

    async def query(self, sql: str):
        async with self.pool.acquire() as conn:
            return await conn.fetch(sql)
```

### HTTP Client Pools

```python
import httpx

# Reuse a single client with connection pooling
http_client = httpx.AsyncClient(
    timeout=30,
    limits=httpx.Limits(
        max_connections=20,
        max_keepalive_connections=10
    )
)

@mcp.tool()
async def api_call(endpoint: str) -> str:
    resp = await http_client.get(endpoint)
    return resp.text
```

---

## 23.3 Caching Strategies for Resources and Tool Results

### Resource Caching

Resources that do not change frequently can be cached:

```python
from functools import lru_cache
import time

class CachedResource:
    def __init__(self, ttl_seconds: int = 300):
        self.cache = {}
        self.ttl = ttl_seconds

    async def get(self, uri: str, fetch_fn):
        now = time.time()
        if uri in self.cache:
            data, timestamp = self.cache[uri]
            if now - timestamp < self.ttl:
                return data

        data = await fetch_fn()
        self.cache[uri] = (data, now)
        return data

cache = CachedResource(ttl_seconds=60)

@mcp.resource("db://schema")
async def get_schema() -> str:
    return await cache.get("db://schema", fetch_schema_from_db)
```

### Tool Result Caching

For idempotent tools, cache results:

```python
import hashlib

tool_cache = {}

@mcp.tool()
async def cached_query(sql: str) -> str:
    """Execute a cached SQL query. Results are cached for 5 minutes."""
    cache_key = hashlib.sha256(sql.encode()).hexdigest()

    if cache_key in tool_cache:
        result, timestamp = tool_cache[cache_key]
        if time.time() - timestamp < 300:
            return f"(cached) {result}"

    result = await execute_query(sql)
    tool_cache[cache_key] = (result, time.time())
    return result
```

---

## 23.4 Horizontal Scaling of MCP Servers

### Scaling Streamable HTTP Servers

```
                    ┌──────────────┐
                    │ Load Balancer│
                    │  (nginx/ALB) │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌───────────┐ ┌───────────┐ ┌───────────┐
        │ Instance 1│ │ Instance 2│ │ Instance 3│
        │ Port 3001 │ │ Port 3002 │ │ Port 3003 │
        └───────────┘ └───────────┘ └───────────┘
```

**Load balancer configuration (nginx):**

```nginx
upstream mcp_backend {
    # Sticky sessions based on Mcp-Session-Id
    hash $http_mcp_session_id consistent;

    server 127.0.0.1:3001;
    server 127.0.0.1:3002;
    server 127.0.0.1:3003;
}

server {
    listen 443 ssl;

    location /mcp {
        proxy_pass http://mcp_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # SSE support
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
    }
}
```

### Serverless Deployment

For stateless Streamable HTTP servers, deploy to serverless platforms:

```python
# AWS Lambda handler
from mangum import Mangum
from server import app  # Your Starlette/FastAPI app

handler = Mangum(app)
```

```python
# Cloudflare Workers (conceptual)
async def handle_request(request):
    transport = StreamableHTTPServerTransport(stateless=True)
    server = create_server()
    await server.connect(transport)
    return await transport.handle_request(request)
```

---

## 23.5 Fault Tolerance and Graceful Degradation

### Circuit Breaker Pattern

```python
import asyncio
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered

class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=30):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.last_failure_time = 0

    async def call(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception("Circuit breaker is open")

        try:
            result = await func(*args, **kwargs)
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
            raise

# Usage
github_breaker = CircuitBreaker()

@mcp.tool()
async def github_api(endpoint: str) -> str:
    try:
        return await github_breaker.call(fetch_github, endpoint)
    except Exception:
        return "GitHub API is currently unavailable. Please try again later."
```

### Graceful Degradation

```python
@mcp.tool()
async def get_data(source: str) -> str:
    """Get data with fallback sources."""
    # Try primary source
    try:
        return await fetch_from_primary(source)
    except Exception as primary_error:
        await ctx.warning(f"Primary source failed: {primary_error}")

    # Try secondary source
    try:
        return await fetch_from_cache(source)
    except Exception:
        pass

    # Return degraded response
    return f"Data temporarily unavailable for {source}. Using last known data."
```

---

## 23.6 Monitoring and Observability in Production

### Metrics Collection

```python
import time
from dataclasses import dataclass, field
from collections import defaultdict

@dataclass
class ServerMetrics:
    request_count: int = 0
    error_count: int = 0
    total_latency: float = 0
    tool_calls: dict = field(default_factory=lambda: defaultdict(int))
    tool_errors: dict = field(default_factory=lambda: defaultdict(int))
    tool_latencies: dict = field(default_factory=lambda: defaultdict(list))

metrics = ServerMetrics()

class MetricsMiddleware:
    async def on_tool_call(self, name: str, arguments: dict):
        metrics.request_count += 1
        metrics.tool_calls[name] += 1
        start = time.time()
        return start

    async def on_tool_result(self, name: str, start_time: float, is_error: bool):
        elapsed = time.time() - start_time
        metrics.total_latency += elapsed
        metrics.tool_latencies[name].append(elapsed)
        if is_error:
            metrics.error_count += 1
            metrics.tool_errors[name] += 1

@mcp.resource("metrics://server")
async def server_metrics() -> str:
    """Server performance metrics."""
    avg_latency = (metrics.total_latency / metrics.request_count * 1000
                   if metrics.request_count > 0 else 0)
    return json.dumps({
        "total_requests": metrics.request_count,
        "total_errors": metrics.error_count,
        "error_rate": metrics.error_count / max(metrics.request_count, 1),
        "avg_latency_ms": round(avg_latency, 1),
        "tools": dict(metrics.tool_calls)
    }, indent=2)
```

---

## Summary

Production MCP servers need the same operational rigor as any production service: performance optimization, scalability, fault tolerance, and observability.

Key takeaways:

- **Latency optimization**: Use async operations, connection pooling, and concise results
- **Caching**: Cache resources and idempotent tool results with appropriate TTLs
- **Horizontal scaling**: Use load balancers with sticky sessions for Streamable HTTP
- **Serverless**: Stateless Streamable HTTP servers deploy naturally to serverless platforms
- **Fault tolerance**: Circuit breakers and graceful degradation handle external service failures
- **Monitoring**: Track request counts, latencies, error rates, and per-tool metrics
