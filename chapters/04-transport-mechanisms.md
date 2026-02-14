# Chapter 4: Transport Mechanisms

---

## 4.1 What Is a Transport in MCP?

A **transport** is the mechanism by which JSON-RPC messages are physically delivered between an MCP client and an MCP server. The transport is the lowest layer of the MCP stack — it does not understand MCP semantics, tool definitions, or resource schemas. Its sole responsibility is to reliably deliver JSON strings from one endpoint to the other.

MCP's design cleanly separates the transport from the protocol. This means that the same MCP server logic can work over different transports without modification. A server that handles `tools/call` requests the same way regardless of whether the message arrived over stdio, HTTP+SSE, or Streamable HTTP.

The transport layer is responsible for:

1. **Message framing**: Determining where one JSON-RPC message ends and another begins
2. **Delivery**: Ensuring messages reach the other endpoint
3. **Connection management**: Establishing, maintaining, and closing the communication channel
4. **Bidirectionality**: Allowing both sides to send messages (not just request-response, but also notifications in both directions)

MCP defines three standard transports:

| Transport | Communication | Typical Use Case |
|-----------|--------------|------------------|
| **stdio** | Standard input/output streams | Local servers running as child processes |
| **HTTP + SSE** | HTTP POST + Server-Sent Events | Network-accessible servers (legacy) |
| **Streamable HTTP** | HTTP with optional SSE streams | Network-accessible servers (current) |

---

## 4.2 stdio Transport

The stdio transport is the simplest and most commonly used transport for local MCP servers. It uses the standard input (stdin) and standard output (stdout) streams of a process to exchange messages.

### 4.2.1 How It Works

The host application launches the MCP server as a **child process**. The two communicate through the child's stdin and stdout:

- **Client → Server**: The client writes JSON-RPC messages to the server's stdin
- **Server → Client**: The server writes JSON-RPC messages to its stdout

```
Host Application
    │
    │ spawns child process
    ▼
┌─────────────────────────────────────────┐
│              MCP Server Process          │
│                                         │
│  stdin  ← ─ ─ ─ JSON-RPC messages ─ ─ ─ ← Client writes
│  stdout → ─ ─ ─ JSON-RPC messages ─ ─ ─ → Client reads
│  stderr → ─ ─ ─ Logging/debug output ─ → Host captures
│                                         │
└─────────────────────────────────────────┘
```

### 4.2.2 Message Framing and Delimiters

Each JSON-RPC message is a single line of JSON text terminated by a newline character (`\n`). This is the message framing mechanism — the reader knows that each line is a complete message.

```
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{...}}\n
{"jsonrpc":"2.0","id":1,"result":{...}}\n
{"jsonrpc":"2.0","method":"notifications/initialized"}\n
```

Rules:
- Each message MUST be a single line (no embedded newlines in the JSON)
- Each message MUST be terminated by a newline (`\n`)
- Messages MUST be valid JSON
- The transport MUST NOT send any non-JSON content on stdout (use stderr for logging)

This last point is critical: **the server MUST NOT write anything to stdout except JSON-RPC messages.** If the server writes log messages, debug output, or any other text to stdout, it will corrupt the message stream. All non-protocol output should go to stderr, which the host can capture for debugging.

### 4.2.3 Process Lifecycle Management

The lifecycle of a stdio-based MCP server is tied to the lifecycle of the process:

1. **Startup**: The host launches the server process, typically with specific command-line arguments and environment variables
2. **Connection**: The client begins communicating via stdin/stdout immediately after the process starts
3. **Initialization**: The client sends the `initialize` request and the handshake proceeds
4. **Operation**: Normal request-response and notification exchange
5. **Shutdown**: The client closes the server's stdin stream. The server should detect this (EOF on stdin) and exit cleanly
6. **Cleanup**: The host reaps the child process

If the server process crashes unexpectedly, the host detects this through the process exit and can decide whether to restart it.

### 4.2.4 When to Use stdio

stdio is the right choice when:

- The server runs on the same machine as the host
- The server is a simple process that can be spawned on demand
- You want the simplest possible setup with no network configuration
- The server needs access to local resources (files, databases, processes)
- You are developing and testing a new server

stdio is used by Claude Desktop, Claude Code, and most other MCP hosts for local server connections.

### 4.2.5 Advantages and Limitations

**Advantages:**
- Simplest possible transport — no network configuration, no ports, no TLS
- No authentication needed — the host controls the process
- Natural security boundary — the server runs as a child process with inherited permissions
- Easy debugging — stderr is available for logging
- Cross-platform — works on every OS

**Limitations:**
- Server must run on the same machine as the host
- Cannot be shared between multiple hosts or users
- Process overhead — each connection is a separate OS process
- No built-in reconnection — if the process dies, a new one must be started
- One client per server process — the 1:1 relationship is physical, not just logical

---

## 4.3 HTTP with Server-Sent Events (SSE)

The HTTP+SSE transport enables MCP communication over the network, allowing servers to run on remote machines or as shared services.

> **Note**: The HTTP+SSE transport is considered the **legacy** network transport. The newer Streamable HTTP transport (Section 4.4) is recommended for new implementations. However, HTTP+SSE remains widely deployed and understanding it is important.

### 4.3.1 How It Works: The Two-Endpoint Model

The HTTP+SSE transport uses two HTTP endpoints:

1. **SSE endpoint** (`GET /sse`): The client establishes a long-lived Server-Sent Events connection to receive messages from the server. This is the server-to-client channel.

2. **Message endpoint** (`POST /message`): The client sends JSON-RPC messages to the server via HTTP POST requests. This is the client-to-server channel.

```
Client                                     Server
  │                                           │
  │ ── GET /sse ──────────────────────────→   │
  │ ←── SSE stream (long-lived) ──────────   │  Server → Client
  │                                           │
  │ ── POST /message ─────────────────────→   │
  │ ←── HTTP 200 OK ─────────────────────    │  Client → Server
  │                                           │
  │ ── POST /message ─────────────────────→   │
  │ ←── HTTP 200 OK ─────────────────────    │  Client → Server
  │                                           │
  │ ←── SSE event (tool list changed) ────   │  Server → Client
  │                                           │
```

### 4.3.2 SSE for Server-to-Client Messages

Server-Sent Events (SSE) is a web standard (part of the HTML5 specification) that allows a server to push events to a client over a long-lived HTTP connection. The client opens the connection with a `GET` request, and the server holds it open, sending events as they occur.

SSE events have a simple text format:

```
event: message
data: {"jsonrpc":"2.0","id":1,"result":{"tools":[...]}}

event: message
data: {"jsonrpc":"2.0","method":"notifications/tools/list_changed"}

```

Each event has:
- An `event` field (the event type — MCP uses `"message"` for JSON-RPC messages)
- A `data` field (the JSON-RPC message as a string)
- Events are separated by blank lines

When the client first connects to the SSE endpoint, the server sends a special `endpoint` event that tells the client the URL to use for posting messages:

```
event: endpoint
data: /message?sessionId=abc123
```

The client then uses this URL for all subsequent POST requests. The session ID in the URL allows the server to correlate POST requests with the correct SSE connection.

### 4.3.3 HTTP POST for Client-to-Server Messages

When the client needs to send a JSON-RPC message (a request or notification) to the server, it sends an HTTP POST to the message endpoint:

```http
POST /message?sessionId=abc123 HTTP/1.1
Content-Type: application/json

{"jsonrpc":"2.0","id":2,"method":"tools/list"}
```

The server responds with HTTP 200 OK (with an empty body or a simple acknowledgment). The actual JSON-RPC response comes through the SSE stream.

This separation is important: **the HTTP response to the POST is not the JSON-RPC response.** The JSON-RPC response arrives asynchronously on the SSE stream. This allows the server to process requests asynchronously and return responses in any order.

### 4.3.4 Session Management

The HTTP+SSE transport uses session IDs to correlate SSE connections with POST requests. The session ID is typically generated by the server and communicated to the client via the SSE `endpoint` event.

Sessions have implications for state:
- If the SSE connection drops, the session may be lost
- The client must reconnect to the SSE endpoint and potentially re-initialize
- Session state (in-flight requests, subscriptions) may need to be rebuilt

### 4.3.5 When to Use HTTP+SSE

HTTP+SSE is appropriate when:

- The server needs to be accessible over the network
- Multiple clients may need to connect to the same server
- The server runs as a long-lived service (not a per-client process)
- You are working with existing infrastructure that supports SSE

### 4.3.6 Advantages and Limitations

**Advantages:**
- Works over the network — server and client can be on different machines
- Server can be shared between multiple clients
- Uses standard HTTP — works with existing proxies, load balancers, and firewalls
- SSE is well-supported in browsers and HTTP libraries

**Limitations:**
- More complex than stdio — requires HTTP server setup, CORS configuration, etc.
- SSE connections can be dropped by proxies and load balancers that do not support long-lived connections
- Two-endpoint model adds complexity
- Session management across reconnections is tricky
- Not all HTTP infrastructure handles SSE well (some proxies buffer SSE events)

---

## 4.4 Streamable HTTP Transport

The Streamable HTTP transport is the modern, recommended network transport for MCP. It addresses the limitations of the HTTP+SSE transport while maintaining compatibility with standard HTTP infrastructure.

### 4.4.1 The Evolution Beyond SSE

The HTTP+SSE transport, while functional, had several pain points:

- The two-endpoint model (one for SSE, one for POST) was complex
- SSE connections needed to be held open indefinitely, which is problematic for serverless environments
- Session management across reconnections was fragile
- Some infrastructure (CDNs, reverse proxies, serverless platforms) does not handle long-lived SSE connections well

Streamable HTTP addresses all of these by consolidating communication into a single endpoint with optional SSE streaming.

### 4.4.2 How It Works: Single-Endpoint Design

Streamable HTTP uses a single HTTP endpoint (typically `/mcp`) for all communication:

**Client → Server (sending messages):**

The client sends JSON-RPC messages as HTTP POST requests to the endpoint:

```http
POST /mcp HTTP/1.1
Content-Type: application/json
Mcp-Session-Id: session-abc-123

{"jsonrpc":"2.0","id":1,"method":"tools/list"}
```

**Server → Client (responses):**

The server can respond in two ways:

1. **Direct response**: The server returns the JSON-RPC response directly in the HTTP response body:

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"jsonrpc":"2.0","id":1,"result":{"tools":[...]}}
```

2. **SSE stream response**: For long-running operations or when the server needs to send multiple messages, the server can upgrade the response to an SSE stream:

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream

event: message
data: {"jsonrpc":"2.0","method":"notifications/progress","params":{"progressToken":"op-1","progress":50,"total":100}}

event: message
data: {"jsonrpc":"2.0","id":1,"result":{"tools":[...]}}

```

**Server-initiated messages (notifications and requests):**

When the server needs to send messages to the client without being asked (notifications, sampling requests), it uses the SSE stream established by a previous request. Alternatively, the client can open a dedicated SSE stream by sending a GET request to the endpoint:

```http
GET /mcp HTTP/1.1
Accept: text/event-stream
Mcp-Session-Id: session-abc-123
```

The server holds this connection open and sends events as they occur.

### 4.4.3 Server-Sent Events within HTTP Responses

The key innovation of Streamable HTTP is that SSE is used *within* regular HTTP responses, not as a separate endpoint. When the server detects that a response may take time or needs to include multiple messages, it sets `Content-Type: text/event-stream` and streams events:

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream

event: message
data: {"jsonrpc":"2.0","method":"notifications/progress","params":{"progressToken":"t1","progress":25,"total":100}}

event: message
data: {"jsonrpc":"2.0","method":"notifications/progress","params":{"progressToken":"t1","progress":75,"total":100}}

event: message
data: {"jsonrpc":"2.0","id":5,"result":{"content":[{"type":"text","text":"Operation complete"}]}}

```

The client knows to expect an SSE stream when the response's `Content-Type` is `text/event-stream`. Otherwise, it expects a regular JSON body.

### 4.4.4 Session Management with Mcp-Session-Id

Streamable HTTP uses the `Mcp-Session-Id` header for session management:

1. During initialization, the server generates a session ID and returns it in the `Mcp-Session-Id` response header
2. The client includes this header in all subsequent requests
3. The server uses the session ID to correlate requests with session state

```http
POST /mcp HTTP/1.1
Content-Type: application/json

{"jsonrpc":"2.0","id":1,"method":"initialize","params":{...}}
```

```http
HTTP/1.1 200 OK
Content-Type: application/json
Mcp-Session-Id: sess_abc123

{"jsonrpc":"2.0","id":1,"result":{...}}
```

All subsequent requests include the session ID:

```http
POST /mcp HTTP/1.1
Content-Type: application/json
Mcp-Session-Id: sess_abc123

{"jsonrpc":"2.0","id":2,"method":"tools/list"}
```

If the server receives a request with an unknown or expired session ID, it responds with HTTP 404, signaling the client to re-initialize.

### 4.4.5 Stateless vs. Stateful Servers

Streamable HTTP supports both stateful and stateless server designs:

**Stateful servers** maintain session state in memory. They assign a session ID during initialization and track all state (capabilities, subscriptions, in-flight requests) for each session. This is the simpler model and works well for single-instance servers.

**Stateless servers** do not maintain session state between requests. Each request is self-contained. This model works well for serverless environments (AWS Lambda, Cloudflare Workers) where there is no persistent process. Stateless servers:

- May not issue a session ID (since there is no session)
- Cannot support features that require state (like SSE streams for server-initiated messages)
- Process each request independently

The choice between stateful and stateless depends on the deployment environment and the features the server needs to support.

### 4.4.6 Resumability and Event Replay

Streamable HTTP supports **resumability** — the ability to pick up where you left off after a connection interruption. This uses the standard SSE `id` field:

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream

id: evt-001
event: message
data: {"jsonrpc":"2.0","method":"notifications/progress","params":{"progressToken":"t1","progress":25,"total":100}}

id: evt-002
event: message
data: {"jsonrpc":"2.0","method":"notifications/progress","params":{"progressToken":"t1","progress":50,"total":100}}
```

If the connection drops after receiving `evt-001`, the client can reconnect and send the `Last-Event-ID` header:

```http
GET /mcp HTTP/1.1
Accept: text/event-stream
Mcp-Session-Id: sess_abc123
Last-Event-ID: evt-001
```

The server can then replay events starting after `evt-001`. This is particularly useful for long-running operations where you do not want to lose progress due to a network hiccup.

### 4.4.7 When to Use Streamable HTTP

Streamable HTTP is the recommended transport for all new network-accessible MCP servers. Use it when:

- The server needs to be accessible over the network
- You want a single endpoint for simplicity
- You need to support serverless deployments
- You want resumability for long-running operations
- You are building a new server and not constrained by legacy compatibility

---

## 4.5 Custom Transports: Building Your Own

MCP is transport-agnostic. While the three standard transports cover most use cases, you can build custom transports for specialized scenarios:

- **WebSocket transport**: For full-duplex communication without SSE
- **IPC transport**: For inter-process communication using shared memory or named pipes
- **In-process transport**: For testing, where client and server run in the same process
- **Message queue transport**: For integration with message brokers like RabbitMQ or Kafka

A custom transport must provide:

1. A way for the client to send JSON strings to the server
2. A way for the server to send JSON strings to the client
3. Message framing (knowing where one message ends and another begins)
4. Connection lifecycle management (open, close, detect disconnection)

Both the TypeScript and Python SDKs define transport interfaces that you can implement:

**Python example (conceptual):**
```python
from mcp.shared.transport import Transport

class CustomTransport(Transport):
    async def start(self):
        """Establish the connection."""
        ...

    async def send(self, message: str):
        """Send a JSON-RPC message."""
        ...

    async def receive(self) -> str:
        """Receive a JSON-RPC message."""
        ...

    async def close(self):
        """Close the connection."""
        ...
```

---

## 4.6 Transport Selection Decision Guide

Choosing the right transport depends on your deployment scenario. Here is a decision guide:

```
Is the server on the same machine as the host?
├── YES → Use stdio
│         - Simplest setup
│         - No network configuration
│         - Natural process isolation
│
└── NO → Does the server need to support serverless deployment?
         ├── YES → Use Streamable HTTP (stateless mode)
         │         - No persistent connections needed
         │         - Works with Lambda, Workers, etc.
         │
         └── NO → Use Streamable HTTP (stateful mode)
                   - Single endpoint
                   - Resumability support
                   - Modern and recommended
```

**Summary comparison:**

| Feature | stdio | HTTP+SSE | Streamable HTTP |
|---------|-------|----------|-----------------|
| Network support | No | Yes | Yes |
| Endpoints | N/A (process streams) | 2 (SSE + POST) | 1 |
| Serverless support | No | No | Yes |
| Resumability | No | No | Yes |
| Session management | Implicit (process) | Session ID in URL | Mcp-Session-Id header |
| Complexity | Very low | Medium | Low-Medium |
| Recommended for | Local servers | Legacy deployments | New network servers |
| Bidirectional | Yes | Yes | Yes |
| Multiple clients | No (1:1 with process) | Yes | Yes |

---

## Summary

The transport layer is the foundation upon which all MCP communication is built. While the transport is invisible to most of the protocol's functionality — tools, resources, and prompts work the same regardless of transport — choosing the right transport is an important architectural decision.

Key takeaways:

- **stdio** is the simplest transport, ideal for local servers. Messages flow over stdin/stdout with newline delimiters. The server runs as a child process of the host.
- **HTTP+SSE** (legacy) uses two endpoints: an SSE stream for server-to-client messages and HTTP POST for client-to-server messages. It works over the network but has complexity and compatibility issues.
- **Streamable HTTP** (recommended) consolidates everything into a single endpoint. It supports both direct JSON responses and SSE streaming, works in serverless environments, and supports resumability.
- **Custom transports** can be built by implementing the transport interface in the SDK. This enables MCP over WebSockets, message queues, or any other communication mechanism.
- The transport is **cleanly separated** from the protocol layer. Server logic does not need to change when switching transports.

In the next chapter, we will move up the stack to explore the first of MCP's three core primitives: **Tools** — the mechanism by which AI models take action in the world.
