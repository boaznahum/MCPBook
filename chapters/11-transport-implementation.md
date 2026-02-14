# Chapter 11: Transport Implementation in Servers

---

## 11.1 stdio Server Implementation

The stdio transport is the default for local MCP servers. Let us examine how it is implemented in both SDKs.

### 11.1.1 TypeScript: `StdioServerTransport`

```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const server = new McpServer({ name: "my-server", version: "1.0.0" });
// ... define tools ...

const transport = new StdioServerTransport();
await server.connect(transport);
```

The `StdioServerTransport`:
- Reads JSON-RPC messages from `process.stdin` (one per line)
- Writes JSON-RPC messages to `process.stdout` (one per line)
- Handles message framing (newline delimiters)
- Detects EOF on stdin for shutdown

### 11.1.2 Python: `stdio_server()` and `mcp.run()`

With FastMCP:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("my-server")
# ... define tools ...

if __name__ == "__main__":
    mcp.run()  # Defaults to stdio
```

With the low-level API:

```python
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server

server = Server("my-server")
# ... set up handlers ...

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

asyncio.run(main())
```

The `stdio_server()` context manager:
- Sets up async readers/writers for stdin/stdout
- Handles message framing
- Ensures proper cleanup on exit

### 11.1.3 Process Management and Signal Handling

stdio servers should handle process signals gracefully:

```python
import signal
import asyncio

async def main():
    mcp = FastMCP("my-server")

    # Handle SIGINT and SIGTERM
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))

    async def shutdown():
        # Clean up resources
        await cleanup_database_connections()
        # The server will exit when stdin closes

    mcp.run()
```

Important considerations:

- **Never write to stdout** except for JSON-RPC messages. All logging must go to stderr.
- **Handle stdin EOF** — when the host closes the server's stdin, the server should exit cleanly.
- **Clean up resources** — close database connections, file handles, etc. on shutdown.

---

## 11.2 SSE Server Implementation

SSE (Server-Sent Events) transport allows MCP servers to be accessed over HTTP. This is the legacy network transport but remains widely deployed.

### 11.2.1 TypeScript: `SSEServerTransport` with Express

```typescript
import express from "express";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";

const app = express();
const server = new McpServer({ name: "sse-server", version: "1.0.0" });

// Define tools, resources, prompts...
server.tool("ping", "Check if the server is alive", {}, async () => ({
  content: [{ type: "text" as const, text: "pong" }]
}));

// Store transports by session
const transports = new Map<string, SSEServerTransport>();

// SSE endpoint — client connects here for server-to-client messages
app.get("/sse", async (req, res) => {
  const transport = new SSEServerTransport("/message", res);
  const sessionId = transport.sessionId;
  transports.set(sessionId, transport);

  res.on("close", () => {
    transports.delete(sessionId);
  });

  await server.connect(transport);
});

// Message endpoint — client sends messages here
app.post("/message", async (req, res) => {
  const sessionId = req.query.sessionId as string;
  const transport = transports.get(sessionId);

  if (!transport) {
    res.status(404).json({ error: "Unknown session" });
    return;
  }

  await transport.handlePostMessage(req, res);
});

app.listen(3000, () => {
  console.error("SSE MCP server listening on port 3000");
});
```

### 11.2.2 Python: SSE with Starlette/ASGI

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("sse-server")

# Define tools...
@mcp.tool()
async def ping() -> str:
    """Check if the server is alive."""
    return "pong"

if __name__ == "__main__":
    mcp.run(transport="sse")
```

For more control, use the low-level API with Starlette:

```python
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from mcp.server import Server
from mcp.server.sse import SseServerTransport

server = Server("sse-server")
# ... set up handlers ...

sse = SseServerTransport("/message")

async def handle_sse(request):
    async with sse.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await server.run(
            streams[0], streams[1],
            server.create_initialization_options()
        )

async def handle_message(request):
    await sse.handle_post_message(request.scope, request.receive, request._send)

app = Starlette(
    routes=[
        Route("/sse", handle_sse),
        Route("/message", handle_message, methods=["POST"]),
    ]
)

# Run with: uvicorn server:app --port 3000
```

### 11.2.3 CORS and Security Headers

For cross-origin access (e.g., browser-based clients), configure CORS:

```python
from starlette.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

---

## 11.3 Streamable HTTP Server Implementation

Streamable HTTP is the modern, recommended network transport.

### 11.3.1 TypeScript: `StreamableHTTPServerTransport`

```typescript
import express from "express";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from
  "@modelcontextprotocol/sdk/server/streamableHttp.js";

const app = express();
app.use(express.json());

const server = new McpServer({ name: "streamable-server", version: "1.0.0" });
// ... define tools ...

const transports = new Map<string, StreamableHTTPServerTransport>();

app.post("/mcp", async (req, res) => {
  const sessionId = req.headers["mcp-session-id"] as string | undefined;

  if (sessionId && transports.has(sessionId)) {
    // Existing session
    const transport = transports.get(sessionId)!;
    await transport.handleRequest(req, res);
  } else if (!sessionId) {
    // New session (initialization)
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: () => crypto.randomUUID(),
    });

    transport.onSessionCreated = (id) => {
      transports.set(id, transport);
    };

    transport.onclose = () => {
      if (transport.sessionId) {
        transports.delete(transport.sessionId);
      }
    };

    await server.connect(transport);
    await transport.handleRequest(req, res);
  } else {
    res.status(404).json({ error: "Unknown session" });
  }
});

// GET for server-initiated messages (SSE stream)
app.get("/mcp", async (req, res) => {
  const sessionId = req.headers["mcp-session-id"] as string;
  const transport = transports.get(sessionId);
  if (transport) {
    await transport.handleRequest(req, res);
  } else {
    res.status(404).json({ error: "Unknown session" });
  }
});

// DELETE for session termination
app.delete("/mcp", async (req, res) => {
  const sessionId = req.headers["mcp-session-id"] as string;
  const transport = transports.get(sessionId);
  if (transport) {
    await transport.handleRequest(req, res);
    transports.delete(sessionId);
  } else {
    res.status(404).json({ error: "Unknown session" });
  }
});

app.listen(3000, () => {
  console.error("Streamable HTTP MCP server on port 3000");
});
```

### 11.3.2 Python: Streamable HTTP Implementation

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("streamable-server")

@mcp.tool()
async def hello(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}!"

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=3000)
```

For the low-level API:

```python
from starlette.applications import Starlette
from starlette.routing import Route
from mcp.server import Server
from mcp.server.streamable_http import StreamableHTTPServerTransport

server = Server("streamable-server")
# ... handlers ...

sessions = {}

async def handle_mcp(request):
    session_id = request.headers.get("mcp-session-id")

    if session_id and session_id in sessions:
        transport = sessions[session_id]
    else:
        transport = StreamableHTTPServerTransport()
        session_id = transport.session_id
        sessions[session_id] = transport
        await server.connect(transport)

    return await transport.handle_request(request)

app = Starlette(routes=[
    Route("/mcp", handle_mcp, methods=["GET", "POST", "DELETE"]),
])
```

### 11.3.3 Session Management

Streamable HTTP sessions need lifecycle management:

```python
import asyncio

class SessionManager:
    def __init__(self, timeout_seconds: int = 3600):
        self.sessions: dict[str, tuple[StreamableHTTPServerTransport, float]] = {}
        self.timeout = timeout_seconds

    def add(self, session_id: str, transport: StreamableHTTPServerTransport):
        self.sessions[session_id] = (transport, time.time())

    def get(self, session_id: str) -> StreamableHTTPServerTransport | None:
        if session_id in self.sessions:
            transport, _ = self.sessions[session_id]
            self.sessions[session_id] = (transport, time.time())  # Touch
            return transport
        return None

    async def cleanup_expired(self):
        """Periodically remove expired sessions."""
        while True:
            now = time.time()
            expired = [
                sid for sid, (_, last_seen) in self.sessions.items()
                if now - last_seen > self.timeout
            ]
            for sid in expired:
                transport, _ = self.sessions.pop(sid)
                await transport.close()
            await asyncio.sleep(60)
```

### 11.3.4 Stateless Mode Configuration

For serverless environments (AWS Lambda, Cloudflare Workers), configure stateless mode:

```typescript
const transport = new StreamableHTTPServerTransport({
  sessionIdGenerator: undefined,  // No sessions
  enableSse: false,               // No streaming
});
```

In stateless mode:
- No session ID is generated or required
- Responses are direct JSON, not SSE streams
- Server-initiated messages are not supported
- Each request is independent

---

## 11.4 Building Custom Transports

Both SDKs define transport interfaces that you can implement for custom communication channels.

### Python Custom Transport

```python
from mcp.shared.transport import Transport
import asyncio

class WebSocketTransport(Transport):
    """Custom transport using WebSockets."""

    def __init__(self, websocket):
        self.ws = websocket
        self._read_queue = asyncio.Queue()

    async def connect(self):
        """Start receiving messages."""
        asyncio.create_task(self._reader())

    async def _reader(self):
        async for message in self.ws:
            await self._read_queue.put(message)

    async def read(self):
        return await self._read_queue.get()

    async def write(self, data: str):
        await self.ws.send(data)

    async def close(self):
        await self.ws.close()
```

### TypeScript Custom Transport

```typescript
import { Transport } from "@modelcontextprotocol/sdk/shared/transport.js";
import { JSONRPCMessage } from "@modelcontextprotocol/sdk/types.js";

class WebSocketTransport implements Transport {
  private ws: WebSocket;

  onclose?: () => void;
  onerror?: (error: Error) => void;
  onmessage?: (message: JSONRPCMessage) => void;

  constructor(ws: WebSocket) {
    this.ws = ws;
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      this.onmessage?.(message);
    };
    ws.onclose = () => this.onclose?.();
    ws.onerror = (e) => this.onerror?.(new Error("WebSocket error"));
  }

  async start(): Promise<void> {}

  async send(message: JSONRPCMessage): Promise<void> {
    this.ws.send(JSON.stringify(message));
  }

  async close(): Promise<void> {
    this.ws.close();
  }
}
```

---

## 11.5 Transport Testing Strategies

### Testing stdio Servers

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_stdio():
    params = StdioServerParameters(command="python", args=["server.py"])

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Test tool listing
            tools = await session.list_tools()
            assert len(tools.tools) > 0

            # Test tool invocation
            result = await session.call_tool("ping", {})
            assert result.content[0].text == "pong"
```

### Testing HTTP Servers

```python
import httpx

async def test_streamable_http():
    async with httpx.AsyncClient() as client:
        # Initialize
        resp = await client.post("http://localhost:3000/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"}
            }
        })
        session_id = resp.headers.get("mcp-session-id")

        # List tools
        resp = await client.post(
            "http://localhost:3000/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers={"mcp-session-id": session_id}
        )
        assert resp.status_code == 200
```

---

## Summary

Transport implementation determines how your MCP server is deployed and accessed. The SDKs handle most of the complexity, letting you focus on your server's logic.

Key takeaways:

- **stdio** is the simplest — just call `mcp.run()` or connect `StdioServerTransport`
- **SSE** requires two endpoints (GET for SSE stream, POST for messages) with session management
- **Streamable HTTP** uses a single endpoint with session management via the `Mcp-Session-Id` header
- **Stateless mode** enables serverless deployment but limits features
- **Custom transports** can be built by implementing the transport interface
- **Testing** should cover both the protocol layer (correct JSON-RPC) and the transport layer (connection management)
- Both SDKs abstract transport details — your tool/resource/prompt handlers work identically regardless of transport

In the next chapter, we will flip to the other side and explore building MCP clients.
