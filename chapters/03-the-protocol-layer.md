# Chapter 3: The Protocol Layer — JSON-RPC 2.0 in Depth

---

## 3.1 Why JSON-RPC 2.0?

MCP needed a message format that was simple, well-understood, language-agnostic, and capable of supporting bidirectional request-response communication. JSON-RPC 2.0 met all of these requirements.

**Why not REST?** REST is designed for client-server interactions over HTTP where the client always initiates requests. MCP needs bidirectional communication — servers need to send requests to clients (for sampling) and unsolicited notifications. REST does not naturally support this.

**Why not gRPC?** gRPC uses Protocol Buffers (a binary format) and requires code generation. While gRPC is excellent for high-performance microservices, MCP prioritized simplicity and accessibility. Any language that can parse JSON and send strings over a transport can implement MCP. gRPC would have raised the barrier to entry significantly.

**Why not GraphQL?** GraphQL is designed for flexible data querying, not for invoking actions. MCP's primary use case — invoking tools and reading resources — maps naturally to the request-response pattern of JSON-RPC.

**Why not a custom format?** Using a well-known standard like JSON-RPC 2.0 means that developers do not need to learn a new wire format. Libraries for JSON-RPC exist in virtually every programming language. The format is human-readable, easy to debug, and well-documented.

JSON-RPC 2.0 provides exactly the primitives MCP needs:

- **Requests**: For operations that need a response (tool calls, resource reads)
- **Responses**: For returning results or errors
- **Notifications**: For events that do not need a response (progress updates, capability changes)
- **Error codes**: For standardized error reporting
- **Message IDs**: For correlating requests with responses
- **Batch support**: For sending multiple messages at once (though MCP does not commonly use this)

---

## 3.2 Request Message Format

A JSON-RPC 2.0 request in MCP has the following structure:

```json
{
  "jsonrpc": "2.0",
  "id": <string | integer>,
  "method": "<string>",
  "params": <object>
}
```

### Fields

**`jsonrpc`** (required): Must always be the string `"2.0"`. This identifies the message as a JSON-RPC 2.0 message. MCP does not use JSON-RPC 1.0.

**`id`** (required for requests): A unique identifier for this request. Can be a string or an integer. The response to this request will include the same `id`, allowing the sender to match responses to their requests. IDs must be unique within a session — do not reuse IDs.

**`method`** (required): A string identifying the MCP operation to perform. MCP defines a fixed set of method names:

| Method | Direction | Purpose |
|--------|-----------|---------|
| `initialize` | Client → Server | Start connection and negotiate capabilities |
| `ping` | Either direction | Health check |
| `tools/list` | Client → Server | Discover available tools |
| `tools/call` | Client → Server | Invoke a tool |
| `resources/list` | Client → Server | List available resources |
| `resources/templates/list` | Client → Server | List resource templates |
| `resources/read` | Client → Server | Read a resource's content |
| `resources/subscribe` | Client → Server | Subscribe to resource changes |
| `resources/unsubscribe` | Client → Server | Unsubscribe from resource changes |
| `prompts/list` | Client → Server | List available prompts |
| `prompts/get` | Client → Server | Get a prompt's content |
| `logging/setLevel` | Client → Server | Set the server's log level |
| `completion/complete` | Client → Server | Request argument autocompletion |
| `sampling/createMessage` | Server → Client | Request an AI completion |
| `roots/list` | Server → Client | Request the list of root URIs |

**`params`** (optional but usually present): An object containing the parameters for the method. The structure of `params` depends on the method. Some methods have no parameters (like `ping`).

### Examples

**Initialize request:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-03-26",
    "capabilities": {
      "sampling": {}
    },
    "clientInfo": {
      "name": "MyApp",
      "version": "1.0.0"
    }
  }
}
```

**Tool call request:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "get_weather",
    "arguments": {
      "city": "San Francisco",
      "units": "celsius"
    }
  }
}
```

**Resource read request:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "resources/read",
  "params": {
    "uri": "file:///home/user/project/README.md"
  }
}
```

---

## 3.3 Response Message Format (Success and Error)

Every request gets exactly one response. The response references the request's `id` and contains either a `result` (on success) or an `error` (on failure).

### Success Response

```json
{
  "jsonrpc": "2.0",
  "id": <same id as the request>,
  "result": <object>
}
```

The `result` field contains the method-specific response data. Its structure depends on the method that was called.

**Example — tools/list response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "get_weather",
        "description": "Get the current weather for a city",
        "inputSchema": {
          "type": "object",
          "properties": {
            "city": {
              "type": "string",
              "description": "The city name"
            },
            "units": {
              "type": "string",
              "enum": ["celsius", "fahrenheit"],
              "description": "Temperature units"
            }
          },
          "required": ["city"]
        }
      }
    ]
  }
}
```

**Example — tools/call response:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "The current weather in San Francisco is 18°C, partly cloudy."
      }
    ]
  }
}
```

**Example — resources/read response:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "contents": [
      {
        "uri": "file:///home/user/project/README.md",
        "mimeType": "text/markdown",
        "text": "# My Project\n\nThis is a sample project..."
      }
    ]
  }
}
```

### Error Response

```json
{
  "jsonrpc": "2.0",
  "id": <same id as the request>,
  "error": {
    "code": <integer>,
    "message": <string>,
    "data": <any, optional>
  }
}
```

The `error` field has three sub-fields:

- **`code`**: An integer error code. JSON-RPC 2.0 defines standard error code ranges, and MCP adds its own.
- **`message`**: A human-readable description of the error.
- **`data`**: Optional additional data about the error. Can be any JSON value — a string, object, array, etc.

**Example — error response:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": {
      "field": "city",
      "reason": "City name cannot be empty"
    }
  }
}
```

### Important Rules

1. A response MUST contain either `result` or `error`, never both, and never neither.
2. The `id` in the response MUST match the `id` of the request it is responding to.
3. If the request's `id` cannot be determined (e.g., due to a parse error), the response's `id` should be `null`.

---

## 3.4 Notification Messages (No Response Expected)

Notifications are messages that do not expect or receive a response. They are identified by the absence of an `id` field:

```json
{
  "jsonrpc": "2.0",
  "method": "<string>",
  "params": <object, optional>
}
```

Because there is no `id`, the sender cannot know whether the notification was received, processed, or even understood. Notifications are inherently fire-and-forget.

### MCP Notifications

| Notification | Direction | Purpose |
|-------------|-----------|---------|
| `notifications/initialized` | Client → Server | Client has finished initialization |
| `notifications/progress` | Either direction | Report progress on a request |
| `notifications/cancelled` | Either direction | Cancel a pending request |
| `notifications/tools/list_changed` | Server → Client | Tool list has changed |
| `notifications/resources/list_changed` | Server → Client | Resource list has changed |
| `notifications/resources/updated` | Server → Client | A subscribed resource has changed |
| `notifications/prompts/list_changed` | Server → Client | Prompt list has changed |
| `notifications/message` | Server → Client | Log message from the server |
| `notifications/roots/list_changed` | Client → Server | Root list has changed |

### Examples

**Initialized notification:**
```json
{
  "jsonrpc": "2.0",
  "method": "notifications/initialized"
}
```

**Progress notification:**
```json
{
  "jsonrpc": "2.0",
  "method": "notifications/progress",
  "params": {
    "progressToken": "op-123",
    "progress": 50,
    "total": 100,
    "message": "Processing records..."
  }
}
```

**Tool list changed notification:**
```json
{
  "jsonrpc": "2.0",
  "method": "notifications/tools/list_changed"
}
```

When a client receives `notifications/tools/list_changed`, it should call `tools/list` again to get the updated tool list. The notification itself does not contain the new tool list — it is simply a signal that the list has changed.

**Log message notification:**
```json
{
  "jsonrpc": "2.0",
  "method": "notifications/message",
  "params": {
    "level": "warning",
    "logger": "database",
    "data": "Connection pool is at 90% capacity"
  }
}
```

---

## 3.5 Batch Requests

JSON-RPC 2.0 supports sending multiple messages in a single batch by wrapping them in a JSON array:

```json
[
  {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
  {"jsonrpc": "2.0", "id": 2, "method": "resources/list"},
  {"jsonrpc": "2.0", "id": 3, "method": "prompts/list"}
]
```

The server would respond with an array of responses:

```json
[
  {"jsonrpc": "2.0", "id": 1, "result": {"tools": [...]}},
  {"jsonrpc": "2.0", "id": 2, "result": {"resources": [...]}},
  {"jsonrpc": "2.0", "id": 3, "result": {"prompts": [...]}}
]
```

While JSON-RPC 2.0 defines batch support, **MCP does not require or commonly use batch requests**. Most MCP interactions involve individual request-response pairs. Implementations may choose to support batching, but it is not required.

---

## 3.6 Error Codes and Error Handling

JSON-RPC 2.0 defines several standard error codes, and MCP adds its own:

### Standard JSON-RPC 2.0 Error Codes

| Code | Name | Meaning |
|------|------|---------|
| `-32700` | Parse error | Invalid JSON was received |
| `-32600` | Invalid Request | The JSON was valid but not a valid JSON-RPC request |
| `-32601` | Method not found | The requested method does not exist |
| `-32602` | Invalid params | The method parameters are invalid |
| `-32603` | Internal error | An internal error occurred in the handler |
| `-32000` to `-32099` | Server error | Reserved for implementation-defined server errors |

### MCP-Specific Error Codes

MCP uses the server error range (`-32000` to `-32099`) for protocol-specific errors:

| Code | Name | Meaning |
|------|------|---------|
| `-32001` | Resource not found | The requested resource URI does not exist |
| `-32002` | Tool not found | The requested tool name does not exist |

### Error Handling Best Practices

**For server implementers:**

1. Always return meaningful error messages. The `message` field should help the developer (or AI) understand what went wrong.
2. Use the `data` field to provide additional context — which field was invalid, what the valid options are, what the actual error was.
3. Do not expose internal implementation details (stack traces, database errors) in production. These can be security risks.
4. Use the appropriate error code. A missing tool should be `-32002`, not a generic `-32603`.

**For tool call errors vs. protocol errors:**

There is an important distinction between *protocol errors* and *tool execution errors*:

- **Protocol errors** are returned as JSON-RPC error responses. These indicate that the request itself was invalid — wrong method name, invalid parameters, etc.
- **Tool execution errors** are returned as *successful* responses with `isError: true` in the result. This means the protocol worked correctly, but the tool itself encountered an error.

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Error: Division by zero"
      }
    ],
    "isError": true
  }
}
```

This distinction is important because the AI model needs to handle tool errors differently from protocol errors. A tool error means "I tried to do what you asked, but it failed" — the AI can retry with different parameters or try a different approach. A protocol error means "your request was invalid" — the AI needs to fix the request format.

---

## 3.7 The MCP-Specific Extensions to JSON-RPC

While MCP uses standard JSON-RPC 2.0, it adds several conventions and structures on top:

### Meta Fields

MCP requests can include a `_meta` field within `params` to carry protocol-level metadata:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "_meta": {
      "progressToken": "op-abc-123"
    },
    "name": "long_running_query",
    "arguments": {
      "query": "SELECT * FROM large_table"
    }
  }
}
```

The `_meta` field can contain:

- **`progressToken`**: A token that the server can use to send progress notifications for this specific request. The server sends `notifications/progress` with this token to report progress.

### Content Types

MCP defines structured content types for tool results and resource contents:

**Text content:**
```json
{
  "type": "text",
  "text": "Hello, world!"
}
```

**Image content:**
```json
{
  "type": "image",
  "data": "<base64-encoded-image-data>",
  "mimeType": "image/png"
}
```

**Resource content (embedded):**
```json
{
  "type": "resource",
  "resource": {
    "uri": "file:///path/to/file.txt",
    "mimeType": "text/plain",
    "text": "File contents here"
  }
}
```

These content types allow tool results to carry rich data — not just text, but images, binary data, and references to resources.

### Pagination with Cursors

List operations (`tools/list`, `resources/list`, `prompts/list`) support cursor-based pagination:

**Request with cursor:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {
    "cursor": "eyJwYWdlIjogMn0="
  }
}
```

**Response with next cursor:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [...],
    "nextCursor": "eyJwYWdlIjogM30="
  }
}
```

If `nextCursor` is present in the response, there are more results available. The client can send another request with that cursor to get the next page. If `nextCursor` is absent, there are no more results.

The cursor is an opaque string — the client should not try to parse or interpret it. The server can encode whatever state it needs into the cursor (page number, offset, sort order, etc.).

---

## 3.8 Protocol Version Negotiation

MCP uses date-based versioning (e.g., `"2025-03-26"`) for the protocol specification. Version negotiation happens during the `initialize` handshake:

1. The client sends its supported protocol version in the `initialize` request
2. The server responds with the version it will use

**Compatible versions**: If the client and server support the same version, they use it. If they support different versions, the server should attempt to use the client's version if possible, or respond with the closest compatible version.

**Incompatible versions**: If the server cannot support the client's requested version, it should respond with an error, and the client should disconnect.

```json
// Client requests
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-03-26",
    ...
  }
}

// Server responds with compatible version
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2025-03-26",
    ...
  }
}
```

The use of date-based versions (rather than semantic versions like 1.2.3) reflects MCP's evolution as a specification — each version represents a snapshot of the protocol at a point in time, rather than a compatibility commitment via major/minor/patch numbering.

---

## 3.9 Full Message Exchange Examples

Let us walk through complete message exchanges for the most common MCP operations. These examples show the exact JSON that flows over the wire.

### 3.9.1 Initialization Handshake

```
Client → Server:
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
      "name": "Claude Desktop",
      "version": "1.5.0"
    }
  }
}

Server → Client:
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
      "logging": {}
    },
    "serverInfo": {
      "name": "database-server",
      "version": "2.0.0"
    }
  }
}

Client → Server:
{
  "jsonrpc": "2.0",
  "method": "notifications/initialized"
}
```

### 3.9.2 Tool Discovery and Invocation

```
Client → Server:
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list"
}

Server → Client:
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "query",
        "description": "Execute a read-only SQL query against the database",
        "inputSchema": {
          "type": "object",
          "properties": {
            "sql": {
              "type": "string",
              "description": "The SQL query to execute"
            },
            "database": {
              "type": "string",
              "description": "The database to query",
              "default": "main"
            }
          },
          "required": ["sql"]
        },
        "annotations": {
          "readOnlyHint": true,
          "openWorldHint": false
        }
      },
      {
        "name": "list_tables",
        "description": "List all tables in a database",
        "inputSchema": {
          "type": "object",
          "properties": {
            "database": {
              "type": "string",
              "description": "The database to list tables from",
              "default": "main"
            }
          }
        },
        "annotations": {
          "readOnlyHint": true,
          "openWorldHint": false
        }
      }
    ]
  }
}

Client → Server:
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "query",
    "arguments": {
      "sql": "SELECT name, email FROM users WHERE active = true LIMIT 5"
    }
  }
}

Server → Client:
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "| name       | email              |\n|------------|--------------------|\n| Alice      | alice@example.com  |\n| Bob        | bob@example.com    |\n| Charlie    | charlie@example.com|\n| Diana      | diana@example.com  |\n| Eve        | eve@example.com    |\n\n5 rows returned."
      }
    ]
  }
}
```

### 3.9.3 Resource Listing and Reading

```
Client → Server:
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "resources/list"
}

Server → Client:
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "resources": [
      {
        "uri": "db://main/schema",
        "name": "Database Schema",
        "description": "The complete schema of the main database",
        "mimeType": "application/json"
      },
      {
        "uri": "db://main/stats",
        "name": "Database Statistics",
        "description": "Current database performance statistics",
        "mimeType": "application/json"
      }
    ]
  }
}

Client → Server:
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "resources/read",
  "params": {
    "uri": "db://main/schema"
  }
}

Server → Client:
{
  "jsonrpc": "2.0",
  "id": 5,
  "result": {
    "contents": [
      {
        "uri": "db://main/schema",
        "mimeType": "application/json",
        "text": "{\"tables\": [{\"name\": \"users\", \"columns\": [{\"name\": \"id\", \"type\": \"INTEGER\"}, {\"name\": \"name\", \"type\": \"TEXT\"}, {\"name\": \"email\", \"type\": \"TEXT\"}, {\"name\": \"active\", \"type\": \"BOOLEAN\"}]}]}"
      }
    ]
  }
}
```

### 3.9.4 Error Scenarios

**Method not found:**
```
Client → Server:
{
  "jsonrpc": "2.0",
  "id": 6,
  "method": "nonexistent/method"
}

Server → Client:
{
  "jsonrpc": "2.0",
  "id": 6,
  "error": {
    "code": -32601,
    "message": "Method not found: nonexistent/method"
  }
}
```

**Invalid parameters:**
```
Client → Server:
{
  "jsonrpc": "2.0",
  "id": 7,
  "method": "tools/call",
  "params": {
    "name": "query"
  }
}

Server → Client:
{
  "jsonrpc": "2.0",
  "id": 7,
  "error": {
    "code": -32602,
    "message": "Invalid params: missing required field 'arguments'"
  }
}
```

**Tool execution error (not a protocol error):**
```
Client → Server:
{
  "jsonrpc": "2.0",
  "id": 8,
  "method": "tools/call",
  "params": {
    "name": "query",
    "arguments": {
      "sql": "SELECT * FROM nonexistent_table"
    }
  }
}

Server → Client:
{
  "jsonrpc": "2.0",
  "id": 8,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Error: Table 'nonexistent_table' does not exist"
      }
    ],
    "isError": true
  }
}
```

Note the crucial difference: the protocol-level response is *successful* (it has a `result`, not an `error`). The error is at the *tool level*, indicated by `isError: true`. This tells the AI model that the tool was invoked correctly but failed to produce the desired result.

---

## Summary

JSON-RPC 2.0 provides the foundation for all MCP communication. Its simplicity — just three message types (requests, responses, notifications) — belies the rich interactions it enables.

Key takeaways from this chapter:

- **Requests** have an `id`, a `method`, and optional `params`. They always receive a response.
- **Responses** reference the request's `id` and contain either a `result` (success) or an `error` (failure).
- **Notifications** have no `id` and no response. They are fire-and-forget.
- **Error codes** distinguish between protocol errors (JSON-RPC level) and tool execution errors (MCP level). Tool errors use `isError: true` in a successful response.
- **The `_meta` field** carries protocol metadata like progress tokens.
- **Content types** (text, image, resource) allow rich results.
- **Cursor-based pagination** supports large result sets without loading everything at once.
- **Protocol version negotiation** ensures client-server compatibility.
- All MCP methods have defined request and response schemas, making the protocol fully typed and predictable.

In the next chapter, we will examine the transport layer — how these JSON-RPC messages are actually delivered between clients and servers over stdio, HTTP+SSE, and Streamable HTTP.
