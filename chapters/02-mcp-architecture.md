# Chapter 2: MCP Architecture — The Big Picture

---

## 2.1 The Three Roles: Hosts, Clients, and Servers

The MCP architecture is built around three distinct roles that work together to connect AI models with external capabilities. Understanding these roles — and the boundaries between them — is essential to understanding everything else in this book.

### 2.1.1 Hosts: The AI Application Layer

A **host** is the user-facing AI application. It is the program that the user interacts with directly — the chat interface, the coding assistant, the IDE plugin, the automation platform. The host is where the AI model lives, where conversations happen, and where the user's intent is expressed.

Examples of hosts include:

- **Claude Desktop** — Anthropic's desktop chat application
- **Claude Code** — Anthropic's command-line coding agent
- **Cursor** — An AI-powered code editor
- **Windsurf** — An AI development environment
- **A custom application** — Any application you build that integrates an AI model with MCP

The host has several critical responsibilities:

1. **Creating and managing MCP clients.** The host creates one MCP client for each MCP server it wants to connect to. The host is the only component that has visibility across all connected servers.

2. **Controlling security and consent.** The host is the trust boundary between the user and the AI. It decides which MCP servers to connect to, which capabilities to expose to the AI model, and whether to require user approval before executing certain actions.

3. **Aggregating capabilities for the AI model.** When the host connects to multiple MCP servers, it collects all available tools, resources, and prompts and presents them to the AI model as a unified set. The AI model does not know or care which server provides which tool — it sees a flat list of capabilities.

4. **Routing tool invocations.** When the AI model decides to use a tool, the host must determine which MCP server provides that tool and route the invocation to the correct client-server connection.

5. **Enforcing user policies.** The host may implement policies such as "always ask the user before executing destructive tools" or "never allow the AI to access server X without explicit permission." These policies are entirely the host's responsibility — the MCP protocol itself does not enforce them.

A key architectural principle: **the host is the only component with full visibility.** Each MCP server only knows about itself. Each client only knows about its connected server. But the host sees everything — all servers, all tools, all resources, all in-flight requests. This centralized visibility enables the host to coordinate, prioritize, and enforce security across the entire system.

### 2.1.2 Clients: The Protocol Bridge

An **MCP client** is a protocol-level component that maintains a one-to-one connection with a single MCP server. The client is responsible for:

1. **Establishing and maintaining the connection.** The client initiates the connection to the server, performs the initialization handshake, negotiates capabilities, and keeps the connection alive.

2. **Sending requests and receiving responses.** When the host needs to invoke a tool or read a resource, it tells the appropriate client, which formats the JSON-RPC request and sends it over the transport.

3. **Handling notifications.** The client listens for notifications from the server (e.g., tool list changes, resource updates, log messages) and forwards them to the host.

4. **Managing the protocol lifecycle.** The client handles initialization, capability negotiation, and graceful shutdown.

The critical constraint is: **each client connects to exactly one server.** This is a 1:1 relationship. If a host wants to connect to five MCP servers, it creates five separate client instances, each managing its own independent connection.

```
Host Application
├── MCP Client 1 ←→ MCP Server A (GitHub)
├── MCP Client 2 ←→ MCP Server B (Database)
├── MCP Client 3 ←→ MCP Server C (File System)
├── MCP Client 4 ←→ MCP Server D (Slack)
└── MCP Client 5 ←→ MCP Server E (Web Search)
```

This 1:1 design simplifies the protocol significantly. Each client-server pair can negotiate capabilities independently, manage its own state, and fail independently without affecting other connections.

### 2.1.3 Servers: The Capability Providers

An **MCP server** is a lightweight program that exposes specific capabilities to AI applications through the MCP protocol. A server does not contain an AI model — it provides *tools for* the AI model to use.

An MCP server can expose three types of capabilities:

- **Tools**: Actions the AI can perform (e.g., "run a database query," "create a GitHub issue," "send a Slack message")
- **Resources**: Data the AI can read (e.g., "contents of a file," "a database schema," "a configuration value")
- **Prompts**: Reusable interaction templates (e.g., "analyze this code for security issues," "generate a migration plan for this database")

Servers are intentionally designed to be **simple and focused**. A good MCP server does one thing well — it wraps a specific external system or capability in the MCP protocol. The GitHub server knows about GitHub. The database server knows about databases. The file system server knows about files. Each server is a self-contained unit.

Servers have several key characteristics:

1. **They are stateless with respect to the AI.** A server does not track conversations, remember previous tool invocations, or maintain any model of the AI's goals. It simply receives requests and returns results.

2. **They run as separate processes or services.** Servers can run as local processes (communicating via stdio), as HTTP services (communicating via SSE or Streamable HTTP), or in any other configuration that a transport supports.

3. **They declare their capabilities.** During initialization, a server tells the client what capabilities it supports — which tools it offers, which resources it exposes, which prompts it provides, and which optional protocol features it supports.

4. **They can request AI completions (sampling).** In a notable departure from simple request-response patterns, MCP servers can ask the host to generate an AI completion. This enables servers to leverage the AI model for tasks like content generation or analysis, creating a bidirectional relationship.

---

## 2.2 The Client–Server Relationship: 1:1 Connections

The 1:1 relationship between clients and servers is a deliberate architectural choice that deserves emphasis. Let us examine why this design was chosen and what it implies.

**Why 1:1?** A client could theoretically connect to multiple servers (1:N), or multiple clients could share a single server connection (N:1). But MCP chose 1:1 for several reasons:

- **Simplicity**: Each connection has exactly two endpoints. There is no routing, multiplexing, or fan-out within the protocol itself.
- **Isolation**: If one server crashes or becomes unresponsive, only its client is affected. Other client-server pairs continue operating normally.
- **Independent capability negotiation**: Each client-server pair negotiates capabilities independently. Server A might support sampling while Server B does not. This is handled naturally by the 1:1 model.
- **Independent lifecycle**: Each connection has its own initialization, operation, and shutdown phases. Servers can be added, removed, or restarted independently.
- **Security boundaries**: Each connection is a separate trust boundary. The host can apply different security policies to different servers.

**What about efficiency?** The 1:1 model means that if you have 20 MCP servers, you have 20 separate connections. This might seem wasteful, but in practice, MCP connections are lightweight. Each connection is a single process (for stdio) or a single HTTP session (for network transports). The overhead is negligible compared to the AI model inference that dominates the overall latency.

---

## 2.3 How Hosts Manage Multiple Clients and Servers

In a real-world deployment, a host typically connects to multiple MCP servers simultaneously. Managing these connections involves several responsibilities:

### Capability Aggregation

The host collects the tool lists from all connected servers and presents them as a unified set to the AI model. For example:

- Server A (GitHub) offers tools: `create_issue`, `list_repos`, `create_pr`
- Server B (Database) offers tools: `query`, `list_tables`, `describe_table`
- Server C (File System) offers tools: `read_file`, `write_file`, `search_files`

The AI model sees all nine tools as a flat list. It does not know or care that they come from different servers. When the model decides to use `query`, the host routes the invocation to Server B's client.

### Request Routing

When the AI model invokes a tool, the host must determine which server provides it. This requires maintaining a mapping of tool names to clients. The host must handle potential conflicts — what if two servers both provide a tool named `search`? — through namespacing, disambiguation, or configuration.

### Lifecycle Management

The host manages the lifecycle of all connections:

- Starting servers and establishing connections at launch
- Monitoring connection health
- Handling server crashes and restarts
- Gracefully shutting down all connections when the host exits

### Security Policy Enforcement

The host applies security policies across all servers. This might include:

- Requiring user approval for tools annotated as destructive
- Blocking certain tool invocations based on user configuration
- Rate-limiting requests to specific servers
- Auditing all tool invocations for compliance

---

## 2.4 The Protocol Stack: JSON-RPC 2.0 over Transports

MCP's protocol stack has two layers:

```
┌─────────────────────────────────────┐
│           MCP Protocol              │
│  (Tools, Resources, Prompts, etc.)  │
├─────────────────────────────────────┤
│          JSON-RPC 2.0               │
│   (Request/Response/Notification)   │
├─────────────────────────────────────┤
│           Transport                 │
│   (stdio / HTTP+SSE / Streamable)   │
└─────────────────────────────────────┘
```

**Transport Layer**: The bottom layer handles the physical delivery of bytes between client and server. MCP defines three standard transports — stdio, HTTP+SSE, and Streamable HTTP — but the protocol is transport-agnostic and custom transports can be implemented.

**JSON-RPC 2.0 Layer**: The middle layer provides the message framing. Every MCP message is a JSON-RPC 2.0 message — either a request (with an `id`), a response (referencing a request `id`), or a notification (no `id`, no response expected). JSON-RPC provides a clean, well-understood foundation for request-response communication.

**MCP Protocol Layer**: The top layer defines the actual semantics — the specific requests, responses, and notifications that make up MCP. This includes `initialize`, `tools/list`, `tools/call`, `resources/read`, `sampling/createMessage`, and all other MCP-specific operations.

This layered design means that the MCP protocol does not need to worry about transport details, and transports do not need to understand MCP semantics. They are cleanly separated.

---

## 2.5 Message Types: Requests, Responses, and Notifications

All communication in MCP falls into three message types, inherited from JSON-RPC 2.0:

### Requests

A request is a message that expects a response. It has four fields:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "query",
    "arguments": {
      "sql": "SELECT * FROM users LIMIT 10"
    }
  }
}
```

- `jsonrpc`: Always `"2.0"` — identifies this as a JSON-RPC 2.0 message
- `id`: A unique identifier (string or integer) for this request. The response will reference this ID.
- `method`: The name of the MCP operation to perform
- `params`: The parameters for the operation (optional, but usually present)

Either side can send requests. Clients send requests to servers (e.g., `tools/call`), and servers can send requests to clients (e.g., `sampling/createMessage`).

### Responses

A response is sent in reply to a request. It references the request's `id`:

**Success response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Query returned 10 rows..."
      }
    ]
  }
}
```

**Error response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32602,
    "message": "Invalid SQL syntax",
    "data": {
      "details": "Unexpected token at position 15"
    }
  }
}
```

A response contains either a `result` (on success) or an `error` (on failure), never both.

### Notifications

A notification is a message that does not expect a response. It has no `id` field:

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/tools/list_changed"
}
```

Notifications are used for events that the other side should know about but that do not require acknowledgment. Examples include:

- `notifications/initialized` — sent by the client after initialization is complete
- `notifications/tools/list_changed` — sent by the server when its tool list changes
- `notifications/resources/updated` — sent by the server when a subscribed resource changes
- `notifications/progress` — sent to report progress on a long-running operation
- `notifications/cancelled` — sent to cancel an in-progress request

Because notifications have no `id`, the sender cannot know whether the notification was received or processed. This is by design — notifications are fire-and-forget.

---

## 2.6 Capability Negotiation and Feature Discovery

Not all MCP servers support all features, and not all clients need all features. MCP handles this through **capability negotiation** during the initialization handshake.

When a client connects to a server, the very first exchange is the `initialize` request:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-03-26",
    "capabilities": {
      "roots": {
        "listChanged": true
      },
      "sampling": {}
    },
    "clientInfo": {
      "name": "MyAIApp",
      "version": "1.0.0"
    }
  }
}
```

The client declares:
- **Protocol version**: Which version of the MCP specification it implements
- **Client capabilities**: Which optional features the client supports. In this example, the client supports `roots` (with change notifications) and `sampling`.
- **Client info**: The name and version of the client application

The server responds with its own capabilities:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2025-03-26",
    "capabilities": {
      "tools": {
        "listChanged": true
      },
      "resources": {
        "subscribe": true,
        "listChanged": true
      },
      "prompts": {
        "listChanged": true
      },
      "logging": {}
    },
    "serverInfo": {
      "name": "DatabaseServer",
      "version": "2.1.0"
    }
  }
}
```

The server declares:
- **Protocol version**: The version it will use (must be compatible with the client's version)
- **Server capabilities**: Which primitives and features it supports
  - `tools` with `listChanged` — it provides tools and will notify when the list changes
  - `resources` with `subscribe` and `listChanged` — it provides resources, supports subscriptions, and will notify on changes
  - `prompts` with `listChanged` — it provides prompts and will notify when the list changes
  - `logging` — it supports the logging protocol
- **Server info**: The name and version of the server

After receiving the server's response, the client sends an `initialized` notification to signal that the handshake is complete:

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/initialized"
}
```

This three-step handshake (request → response → notification) establishes what each side can do. From this point forward, both sides know which features are available and can behave accordingly. For example:

- If the server did not declare `tools` in its capabilities, the client should not send `tools/list` requests
- If the client did not declare `sampling`, the server should not send `sampling/createMessage` requests
- If the server declared `resources.subscribe: true`, the client knows it can subscribe to resource changes

This negotiation ensures that clients and servers can interoperate even when they support different subsets of the protocol.

---

## 2.7 The Connection Lifecycle: Initialize → Operate → Shutdown

Every MCP connection follows a three-phase lifecycle:

### Phase 1: Initialization

The initialization phase establishes the connection and negotiates capabilities. The sequence is:

1. **Client sends `initialize` request** with its protocol version, capabilities, and client info
2. **Server responds** with its protocol version, capabilities, and server info
3. **Client sends `notifications/initialized`** to signal that initialization is complete

During this phase, no other requests or notifications should be sent. The connection is not considered operational until the `initialized` notification has been sent.

**Protocol version negotiation**: The client and server must agree on a protocol version. The client sends the version it supports, and the server responds with the version it will use. If they are incompatible, the server should respond with an error and the client should disconnect.

### Phase 2: Operation

Once initialized, the connection enters the operational phase. During this phase:

- The client can send requests to the server (`tools/list`, `tools/call`, `resources/list`, `resources/read`, `prompts/list`, `prompts/get`, `ping`, `logging/setLevel`, `completion/complete`)
- The server can send requests to the client (`sampling/createMessage`, `roots/list`)
- Either side can send notifications (`progress`, `cancelled`, tool/resource/prompt list changes, log messages)
- Multiple requests can be in flight simultaneously — MCP does not require requests to be serialized

This is the steady-state of the connection, where all useful work happens.

### Phase 3: Shutdown

When either side wants to end the connection, it should do so gracefully:

- For stdio transports: The client closes the server's stdin, and the server exits
- For HTTP transports: The client closes the HTTP connection
- Either side can simply close the transport without a protocol-level shutdown message

MCP does not define a formal `shutdown` request like some protocols do. The shutdown is handled at the transport level.

```
┌──────────┐                              ┌──────────┐
│  Client  │                              │  Server  │
└────┬─────┘                              └────┬─────┘
     │                                         │
     │  ──── initialize request ──────────→    │
     │  ←─── initialize response ─────────    │
     │  ──── initialized notification ────→    │
     │                                         │
     │         === OPERATIONAL PHASE ===       │
     │                                         │
     │  ──── tools/list request ──────────→    │
     │  ←─── tools/list response ─────────    │
     │  ──── tools/call request ──────────→    │
     │  ←─── tools/call response ─────────    │
     │  ←─── sampling/createMessage ──────    │
     │  ──── sampling response ───────────→    │
     │  ←─── log notification ────────────    │
     │                                         │
     │         === SHUTDOWN ===                │
     │                                         │
     │  ──── [close transport] ───────────→    │
     │                                         │
```

---

## 2.8 Architectural Diagram Walkthrough

Let us trace through a complete interaction to see how all the architectural pieces fit together. We will follow a scenario where a user asks Claude to check how many open issues exist in a GitHub repository.

### The Players

- **User**: A person using Claude Desktop
- **Host**: Claude Desktop application
- **AI Model**: Claude (running on Anthropic's servers)
- **MCP Client**: Created by Claude Desktop for the GitHub connection
- **MCP Server**: A GitHub MCP server running as a local process

### The Setup

Before the user even asks their question, the host (Claude Desktop) has already:

1. Read its configuration file, which lists the GitHub MCP server
2. Launched the GitHub server as a subprocess
3. Created an MCP client and connected it to the server via stdio
4. Completed the initialization handshake
5. Called `tools/list` to discover available tools
6. Added the GitHub tools to the AI model's system prompt

### The Interaction

**Step 1: User sends a message**

The user types: *"How many open issues are there in the anthropics/claude-code repository?"*

**Step 2: Host sends the message to the AI model**

Claude Desktop sends the user's message to the Claude API, along with the system prompt that includes the list of available tools. The tools include `github_list_issues` from the GitHub MCP server.

**Step 3: AI model decides to use a tool**

Claude analyzes the user's request and determines that it needs to call the `github_list_issues` tool. It responds with a tool use request:

```json
{
  "type": "tool_use",
  "name": "github_list_issues",
  "input": {
    "owner": "anthropics",
    "repo": "claude-code",
    "state": "open"
  }
}
```

**Step 4: Host routes the tool call to the correct MCP client**

Claude Desktop looks up which MCP server provides `github_list_issues`, finds that it is the GitHub server, and forwards the request to the corresponding MCP client.

**Step 5: MCP client sends the request to the MCP server**

The client sends a `tools/call` JSON-RPC request over the stdio transport:

```json
{
  "jsonrpc": "2.0",
  "id": 42,
  "method": "tools/call",
  "params": {
    "name": "github_list_issues",
    "arguments": {
      "owner": "anthropics",
      "repo": "claude-code",
      "state": "open"
    }
  }
}
```

**Step 6: MCP server executes the tool**

The GitHub MCP server receives the request, calls the GitHub API (`GET /repos/anthropics/claude-code/issues?state=open`), and collects the results.

**Step 7: MCP server returns the result**

The server sends back a JSON-RPC response:

```json
{
  "jsonrpc": "2.0",
  "id": 42,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Found 127 open issues in anthropics/claude-code. [list follows...]"
      }
    ]
  }
}
```

**Step 8: Client forwards the result to the host**

The MCP client receives the response and passes it back to the host.

**Step 9: Host feeds the result back to the AI model**

Claude Desktop takes the tool result and sends it back to the Claude API as a tool result message, continuing the conversation.

**Step 10: AI model generates the final response**

Claude processes the tool result and generates a natural language response: *"There are currently 127 open issues in the anthropics/claude-code repository."*

**Step 11: Host displays the response**

Claude Desktop shows the AI's response to the user.

### The Full Data Flow

```
User ──→ Host ──→ AI Model
                    │
                    │ (tool use decision)
                    ▼
         Host (routes to correct client)
                    │
                    ▼
         MCP Client ──→ MCP Server ──→ External API (GitHub)
                                          │
         MCP Client ←── MCP Server ←──────┘
                    │
                    ▼
         Host ──→ AI Model
                    │
                    │ (generates response)
                    ▼
User ←── Host ←── AI Model
```

This walkthrough illustrates several key architectural principles:

1. **The AI model never communicates directly with MCP servers.** All communication is mediated by the host and client.
2. **The host is the central coordinator.** It manages the AI model, the MCP clients, and the user interface.
3. **The MCP protocol is invisible to the user.** The user sees a natural language conversation. The MCP machinery operates behind the scenes.
4. **The server is a thin wrapper.** The GitHub MCP server's job is simply to translate MCP requests into GitHub API calls and translate the responses back.
5. **The protocol is synchronous at the request level.** Each request gets a response. But the overall interaction is asynchronous — the AI model can make multiple tool calls in sequence or even in parallel.

---

## Summary

The MCP architecture is built on a clean separation of concerns between three roles:

- **Hosts** are the AI applications users interact with. They manage AI models, MCP clients, and user interfaces. They are the central coordinators and security enforcers.
- **Clients** maintain 1:1 connections with servers. They handle the protocol-level communication, including initialization, capability negotiation, and message exchange.
- **Servers** provide capabilities (tools, resources, prompts) to AI applications. They are simple, focused programs that wrap external systems in the MCP protocol.

Key architectural principles:

- **1:1 client-server connections** provide simplicity, isolation, and independent lifecycle management
- **JSON-RPC 2.0** provides a clean, well-understood message format with requests, responses, and notifications
- **Capability negotiation** during initialization ensures that clients and servers can interoperate even when they support different subsets of the protocol
- **Three-phase lifecycle** (initialize → operate → shutdown) provides structure to every connection
- **The host is the trust boundary** — it controls what the AI can see and do, and it enforces security policies
- **Bidirectional communication** — servers can request AI completions from the host through sampling, not just respond to requests

In the next chapter, we will examine the JSON-RPC 2.0 protocol layer in detail, exploring the exact message formats, error handling, and MCP-specific extensions that make the protocol work.
