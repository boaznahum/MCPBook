# Chapter 5: Tools — Giving AI the Power to Act

---

## 5.1 What Are MCP Tools?

Tools are the most important primitive in MCP. They are the mechanism by which AI models **take action** — executing code, calling APIs, manipulating data, interacting with external systems. If MCP is the protocol that connects AI to the real world, tools are the verbs of that connection.

An MCP tool is conceptually simple: it is a named function with a defined input schema and a structured output format. The AI model sees a list of available tools, decides when to use one, provides the input arguments, and receives the result. From the model's perspective, a tool is like a function it can call.

But from the protocol's perspective, there is more going on. Tools have:

- **A name**: A unique identifier (e.g., `"query_database"`, `"create_github_issue"`)
- **A description**: A natural language explanation of what the tool does, which helps the AI model decide when to use it
- **An input schema**: A JSON Schema that defines what arguments the tool accepts
- **Annotations**: Metadata hints about the tool's behavior (read-only? destructive? idempotent?)
- **A handler**: The server-side code that executes when the tool is called

Tools are the primary way MCP servers expose *actions* (as opposed to *data*, which is exposed through Resources, or *interaction patterns*, which are exposed through Prompts).

---

## 5.2 Tool Definition and JSON Schema

Every tool is defined by a name, a description, and an input schema. The input schema uses **JSON Schema** (specifically, the subset that is compatible with most JSON Schema validators) to define the structure of the tool's arguments.

Here is a complete tool definition as it appears in a `tools/list` response:

```json
{
  "name": "create_issue",
  "description": "Create a new issue in a GitHub repository. The issue will be created with the specified title and body in the given repository.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "owner": {
        "type": "string",
        "description": "The owner (user or organization) of the repository"
      },
      "repo": {
        "type": "string",
        "description": "The repository name"
      },
      "title": {
        "type": "string",
        "description": "The title of the issue"
      },
      "body": {
        "type": "string",
        "description": "The body/description of the issue (supports Markdown)"
      },
      "labels": {
        "type": "array",
        "items": {
          "type": "string"
        },
        "description": "Labels to apply to the issue"
      },
      "assignees": {
        "type": "array",
        "items": {
          "type": "string"
        },
        "description": "GitHub usernames to assign to the issue"
      }
    },
    "required": ["owner", "repo", "title"]
  },
  "annotations": {
    "readOnlyHint": false,
    "destructiveHint": false,
    "idempotentHint": false,
    "openWorldHint": true
  }
}
```

### The Input Schema

The `inputSchema` is a JSON Schema object that defines:

- **`type`**: Always `"object"` for tool inputs — tools take named parameters
- **`properties`**: The individual parameters, each with a type, description, and optional constraints
- **`required`**: An array of parameter names that must be provided

The AI model uses this schema to understand what arguments a tool needs and how to format them. The description fields are particularly important — they help the model understand the *purpose* and *constraints* of each parameter, not just its type.

**Best practices for input schemas:**

1. Always include `description` for every property. The AI model relies on descriptions to understand how to use parameters correctly.
2. Use `required` to mark mandatory parameters. Do not make everything required — let the model omit optional parameters.
3. Use `enum` for parameters with a fixed set of valid values.
4. Use `default` to indicate default values, so the model knows it can omit the parameter.
5. Keep schemas as simple as possible. Deeply nested objects and complex constraints make it harder for the model to construct valid arguments.

---

## 5.3 Tool Discovery: `tools/list`

Before an AI model can use tools, the host must discover what tools are available. This is done with the `tools/list` request:

```json
// Request
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}

// Response
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "query",
        "description": "Execute a SQL query",
        "inputSchema": { ... }
      },
      {
        "name": "list_tables",
        "description": "List all tables in the database",
        "inputSchema": { ... }
      }
    ]
  }
}
```

The response contains an array of tool definitions. Each tool has its name, description, input schema, and optional annotations.

### Pagination

If a server has many tools, it can paginate the response using cursors:

```json
// First request
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}

// Response with cursor
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [ /* first page of tools */ ],
    "nextCursor": "page2token"
  }
}

// Follow-up request
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {
    "cursor": "page2token"
  }
}
```

### When Tool Discovery Happens

Typically, the host calls `tools/list` immediately after the initialization handshake completes. The discovered tools are then added to the AI model's system prompt or tool configuration, making them available for the model to use.

---

## 5.4 Tool Invocation: `tools/call`

When the AI model decides to use a tool, the host sends a `tools/call` request to the appropriate MCP server:

```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "method": "tools/call",
  "params": {
    "name": "query",
    "arguments": {
      "sql": "SELECT COUNT(*) as total FROM users WHERE active = true"
    }
  }
}
```

The `params` object contains:
- **`name`**: The name of the tool to invoke (must match a tool from `tools/list`)
- **`arguments`**: An object containing the tool's input arguments (must conform to the tool's `inputSchema`)

The server validates the arguments against the tool's schema, executes the tool's handler, and returns the result.

### Progress Reporting

For long-running tools, the client can request progress updates by including a progress token in the `_meta` field:

```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "method": "tools/call",
  "params": {
    "_meta": {
      "progressToken": "progress-123"
    },
    "name": "bulk_import",
    "arguments": {
      "file": "/data/records.csv"
    }
  }
}
```

The server can then send progress notifications:

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/progress",
  "params": {
    "progressToken": "progress-123",
    "progress": 500,
    "total": 10000,
    "message": "Imported 500 of 10000 records"
  }
}
```

---

## 5.5 Tool Results: Content Types and Structured Output

When a tool completes, the server returns a result containing one or more **content items**. Each content item has a type that determines how it should be interpreted.

The response structure:

```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "result": {
    "content": [
      { "type": "text", "text": "..." },
      { "type": "image", "data": "...", "mimeType": "image/png" }
    ],
    "isError": false
  }
}
```

### 5.5.1 Text Content

The most common content type. Contains plain text or formatted text (Markdown, JSON, etc.):

```json
{
  "type": "text",
  "text": "Found 3,847 active users in the database.\n\nTop 5 by activity:\n1. alice (2,341 actions)\n2. bob (1,892 actions)\n..."
}
```

Text content is passed directly to the AI model, which can read and reason about it.

### 5.5.2 Image Content

For tools that produce visual output (charts, screenshots, diagrams):

```json
{
  "type": "image",
  "data": "iVBORw0KGgoAAAANSUhEUgAA...",
  "mimeType": "image/png"
}
```

The `data` field contains the base64-encoded image data. The `mimeType` indicates the image format. This is useful for tools that generate charts, render web pages, or capture screenshots.

### 5.5.3 Embedded Resources

Tool results can include references to resources, allowing the tool to expose structured data that can be separately accessed:

```json
{
  "type": "resource",
  "resource": {
    "uri": "db://results/query-123",
    "mimeType": "application/json",
    "text": "{\"columns\": [\"name\", \"email\"], \"rows\": [[\"Alice\", \"alice@example.com\"]]}"
  }
}
```

Embedded resources allow tools to return data that is both immediately readable and addressable as a resource URI.

---

## 5.6 Tool Annotations: Hints for AI and Humans

Tool annotations provide metadata about a tool's behavior. They are *hints* — not enforced guarantees — that help AI models and human users make informed decisions about tool usage.

```json
{
  "name": "delete_file",
  "description": "Permanently delete a file from the filesystem",
  "inputSchema": { ... },
  "annotations": {
    "readOnlyHint": false,
    "destructiveHint": true,
    "idempotentHint": true,
    "openWorldHint": false
  }
}
```

### 5.6.1 readOnlyHint, destructiveHint, idempotentHint

**`readOnlyHint`** (boolean, default: `false`): When `true`, indicates that the tool does not modify any state. It only reads data. Examples: querying a database with SELECT, listing files, fetching a web page. This is useful for hosts that want to auto-approve read-only operations without user confirmation.

**`destructiveHint`** (boolean, default: `true`): When `true`, indicates that the tool may perform destructive or irreversible actions. Examples: deleting files, dropping tables, sending messages. Hosts typically require explicit user approval before executing destructive tools.

**`idempotentHint`** (boolean, default: `false`): When `true`, indicates that calling the tool multiple times with the same arguments produces the same result. Examples: setting a configuration value, creating a resource with a deterministic ID. Idempotent tools are safer to retry on failure.

### 5.6.2 openWorldHint

**`openWorldHint`** (boolean, default: `true`): When `true`, indicates that the tool interacts with external entities or systems beyond the server's control. Examples: making HTTP requests, sending emails, interacting with third-party APIs. When `false`, the tool operates in a closed, controlled environment. This hint helps AI models understand the potential blast radius of a tool invocation.

### 5.6.3 How AI Models Use Annotations

AI models and host applications can use annotations to:

- **Auto-approve safe operations**: If a tool is `readOnlyHint: true`, the host might skip user confirmation
- **Require confirmation for dangerous operations**: If a tool is `destructiveHint: true`, the host might always ask the user before executing
- **Implement retry logic**: If a tool is `idempotentHint: true`, the host can safely retry on transient failures
- **Assess risk**: The combination of annotations gives a risk profile. A tool that is `readOnlyHint: false`, `destructiveHint: true`, and `openWorldHint: true` is high-risk and should be treated with caution

Remember: annotations are *hints*, not guarantees. A malicious or buggy server could annotate a destructive tool as read-only. The host should treat annotations as advisory and maintain its own security policies.

---

## 5.7 Error Handling in Tool Calls

There are two types of errors in tool calls:

### Protocol Errors

The tool invocation itself failed at the protocol level — invalid tool name, missing arguments, etc. These are returned as JSON-RPC error responses:

```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "error": {
    "code": -32602,
    "message": "Unknown tool: nonexistent_tool"
  }
}
```

### Tool Execution Errors

The tool was invoked correctly at the protocol level, but the tool's logic encountered an error. These are returned as *successful* responses with `isError: true`:

```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Error: Permission denied. Cannot access /etc/shadow"
      }
    ],
    "isError": true
  }
}
```

This distinction is important for the AI model:

- A **protocol error** means the request was wrong — the model should fix the request
- A **tool error** means the operation failed — the model should try a different approach, use different arguments, or inform the user

When `isError` is `true`, the AI model knows the tool attempted to execute but failed, and it can use the error message to understand what went wrong.

---

## 5.8 Tool Change Notifications

MCP servers can dynamically add, remove, or modify tools during a session. When the tool list changes, the server sends a notification:

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/tools/list_changed"
}
```

This notification does not contain the new tool list — it simply signals that the list has changed. The client should respond by calling `tools/list` again to get the updated list.

This capability is declared during initialization:

```json
{
  "capabilities": {
    "tools": {
      "listChanged": true
    }
  }
}
```

If `listChanged` is `true`, the client should listen for `notifications/tools/list_changed` and update its tool list accordingly. If `false` or absent, the client can assume the tool list is static.

**Use cases for dynamic tools:**

- A database server that adds new query tools when new tables are created
- A plugin system that loads and unloads tools at runtime
- A server that adjusts available tools based on the user's permissions
- A development server that reloads tools when the code changes

---

## 5.9 Designing Effective Tools: Naming, Granularity, and Descriptions

The design of your tools significantly impacts how well AI models can use them. Poorly designed tools lead to confusion, errors, and frustration. Well-designed tools are intuitive, reliable, and composable.

### Naming

- Use clear, action-oriented names: `create_issue`, `query_database`, `send_message`
- Use snake_case for consistency (this is the convention in MCP, though not strictly required)
- Prefix tools with their domain when a server has many tools: `github_create_issue`, `github_list_repos`
- Avoid abbreviations that might be ambiguous: `del_f` is worse than `delete_file`
- Avoid generic names: `do_thing` or `process` tell the model nothing

### Granularity

- **Prefer focused tools over Swiss-army-knife tools.** A tool that does one thing well is easier for the AI to understand and use than a tool with dozens of parameters and modes.
- **But avoid tools that are too fine-grained.** If the AI always needs to call three tools in sequence, consider combining them.
- **Consider the AI's decision-making.** Each tool the AI sees is a decision point. Too many tools overwhelm the model. Too few tools force complex workarounds.

**Too coarse:**
```
"name": "manage_database"
"description": "Do anything with the database — query, insert, update, delete, create tables, etc."
```

**Too fine:**
```
"name": "set_user_name"
"name": "set_user_email"
"name": "set_user_phone"
"name": "set_user_address"
```

**Just right:**
```
"name": "query"           — Read data with SQL
"name": "execute"         — Modify data with SQL
"name": "list_tables"     — See what tables exist
"name": "describe_table"  — See a table's schema
```

### Descriptions

The description is the most important part of a tool definition for the AI model. Write descriptions that:

1. **Explain what the tool does** in clear, natural language
2. **Explain when to use it** (and when not to)
3. **Mention important constraints** (rate limits, permissions, side effects)
4. **Provide examples** of typical usage

**Good description:**
```
"Execute a read-only SQL query against the PostgreSQL database. Returns results
as a formatted table. Use this for SELECT queries only — for INSERT, UPDATE, or
DELETE, use the 'execute' tool instead. Queries are limited to 10,000 rows.
Complex queries may time out after 30 seconds."
```

**Poor description:**
```
"Query the database"
```

---

## 5.10 Real-World Tool Examples

### File System Tools

```json
{
  "name": "read_file",
  "description": "Read the contents of a file at the given path. Returns the file content as text. For binary files, returns base64-encoded content.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Absolute path to the file to read"
      }
    },
    "required": ["path"]
  },
  "annotations": {
    "readOnlyHint": true,
    "destructiveHint": false,
    "idempotentHint": true,
    "openWorldHint": false
  }
}
```

### Web Search Tool

```json
{
  "name": "web_search",
  "description": "Search the web using a search engine. Returns a list of results with titles, URLs, and snippets. Use this when you need current information that may not be in your training data.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "The search query"
      },
      "num_results": {
        "type": "integer",
        "description": "Number of results to return (default: 10, max: 50)",
        "default": 10
      }
    },
    "required": ["query"]
  },
  "annotations": {
    "readOnlyHint": true,
    "destructiveHint": false,
    "openWorldHint": true
  }
}
```

### Slack Message Tool

```json
{
  "name": "send_slack_message",
  "description": "Send a message to a Slack channel. The message supports Slack's block kit formatting. This action is not reversible — once sent, the message will be visible to all channel members.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "channel": {
        "type": "string",
        "description": "The Slack channel name (without #) or channel ID"
      },
      "text": {
        "type": "string",
        "description": "The message text to send"
      },
      "thread_ts": {
        "type": "string",
        "description": "Optional: timestamp of a message to reply to in a thread"
      }
    },
    "required": ["channel", "text"]
  },
  "annotations": {
    "readOnlyHint": false,
    "destructiveHint": false,
    "idempotentHint": false,
    "openWorldHint": true
  }
}
```

---

## Summary

Tools are the primary action primitive in MCP. They transform AI models from conversational engines into agents that can interact with the real world.

Key takeaways:

- **Tools are named functions** with JSON Schema input definitions and structured output
- **Tool discovery** (`tools/list`) lets hosts dynamically learn what a server can do
- **Tool invocation** (`tools/call`) executes the tool with validated arguments
- **Tool results** can contain text, images, and embedded resources
- **Annotations** provide behavioral hints (read-only, destructive, idempotent, open-world) that help hosts and AI models make safe decisions
- **Tool errors** are distinguished from protocol errors — `isError: true` in a successful response signals a tool-level failure
- **Dynamic tool lists** allow servers to add and remove tools at runtime, with change notifications
- **Good tool design** — clear names, focused granularity, detailed descriptions — is critical for effective AI interaction

In the next chapter, we will explore Resources — MCP's primitive for exposing data and context to AI models.
