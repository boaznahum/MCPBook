# Chapter 6: Resources — Exposing Data and Context

---

## 6.1 What Are MCP Resources?

While tools allow AI models to *act*, resources allow AI models to *know*. Resources are the MCP primitive for exposing data — files, database schemas, configuration values, API documentation, live system metrics, or any other information that the AI might need to make informed decisions.

A resource is a piece of data identified by a URI. The AI model (or more precisely, the host application) can read resources to gather context, understand systems, and inform its reasoning. Resources are fundamentally **read-only** from the protocol's perspective — you read a resource, but you do not write to it through the resource interface (that is what tools are for).

Think of resources as the AI's "eyes" — they let it see the state of the world — while tools are its "hands" — they let it change the world.

Key characteristics of resources:

- **Identified by URIs**: Each resource has a unique URI (e.g., `file:///path/to/file`, `db://main/schema`, `config://app/settings`)
- **Read-only access**: Resources are read through `resources/read`, not modified
- **Multiple content types**: Resources can contain text or binary data (base64-encoded)
- **Subscribable**: Clients can subscribe to resource changes and receive notifications when data updates
- **Discoverable**: Resources can be listed statically or through dynamic URI templates

---

## 6.2 Resource URIs and the URI Template System

Every resource is identified by a **URI** (Uniform Resource Identifier). MCP does not prescribe a specific URI scheme — servers can use any URI format that makes sense for their domain:

| URI | Domain | Meaning |
|-----|--------|---------|
| `file:///home/user/project/src/main.py` | File system | A specific file |
| `db://production/users/schema` | Database | The schema of the users table |
| `git://repo/HEAD/README.md` | Version control | A file at HEAD |
| `config://app/database` | Configuration | Database configuration |
| `metrics://cpu/usage` | Monitoring | Current CPU usage |
| `docs://api/v2/endpoints` | Documentation | API endpoint documentation |

The URI serves as both an identifier and a hint about what the resource contains. Well-chosen URIs help the AI model understand the resource's purpose without needing to read it.

### URI Templates

For resources that follow a pattern, MCP supports **URI templates** using RFC 6570 syntax. Templates contain variables enclosed in curly braces:

```
file:///{path}
db://{database}/{table}/schema
git://{repo}/{branch}/{filepath}
```

URI templates allow the AI model to construct resource URIs dynamically. For example, if the AI knows it wants to read the schema of the "orders" table in the "production" database, it can construct the URI `db://production/orders/schema` from the template `db://{database}/{table}/schema`.

---

## 6.3 Resource Discovery

Clients discover resources in two ways: listing concrete resources and listing resource templates.

### 6.3.1 Direct Resources: `resources/list`

The `resources/list` request returns a list of concrete, immediately-available resources:

```json
// Request
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "resources/list"
}

// Response
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "resources": [
      {
        "uri": "db://main/schema",
        "name": "Database Schema",
        "description": "Complete schema of the main database including all tables, columns, and relationships",
        "mimeType": "application/json"
      },
      {
        "uri": "config://app/settings",
        "name": "Application Settings",
        "description": "Current application configuration values",
        "mimeType": "application/json"
      },
      {
        "uri": "docs://api/overview",
        "name": "API Overview",
        "description": "High-level documentation of the REST API",
        "mimeType": "text/markdown"
      }
    ]
  }
}
```

Each resource in the list has:
- **`uri`**: The URI to use when reading the resource
- **`name`**: A human-readable name
- **`description`** (optional): A description of what the resource contains
- **`mimeType`** (optional): The MIME type of the resource content

Like `tools/list`, resource listing supports cursor-based pagination for large resource sets.

### 6.3.2 Resource Templates: `resources/templates/list`

Resource templates describe *patterns* of resources that can be accessed by filling in variables:

```json
// Request
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "resources/templates/list"
}

// Response
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "resourceTemplates": [
      {
        "uriTemplate": "db://{database}/{table}/schema",
        "name": "Table Schema",
        "description": "Get the schema of a specific table in a specific database",
        "mimeType": "application/json"
      },
      {
        "uriTemplate": "db://{database}/{table}/sample?rows={count}",
        "name": "Table Sample",
        "description": "Get a sample of rows from a table",
        "mimeType": "application/json"
      },
      {
        "uriTemplate": "file:///{path}",
        "name": "File Contents",
        "description": "Read any file by its absolute path",
        "mimeType": "application/octet-stream"
      }
    ]
  }
}
```

Templates are powerful because they allow a server to expose a potentially infinite number of resources through a finite set of patterns. A file system server does not need to list every file — it can provide the template `file:///{path}` and let the AI construct URIs as needed.

---

## 6.4 Reading Resources: `resources/read`

To read a resource's content, the client sends a `resources/read` request with the resource's URI:

```json
// Request
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "resources/read",
  "params": {
    "uri": "db://main/schema"
  }
}

// Response
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "contents": [
      {
        "uri": "db://main/schema",
        "mimeType": "application/json",
        "text": "{\n  \"tables\": [\n    {\n      \"name\": \"users\",\n      \"columns\": [\n        {\"name\": \"id\", \"type\": \"INTEGER\", \"primaryKey\": true},\n        {\"name\": \"name\", \"type\": \"TEXT\", \"nullable\": false},\n        {\"name\": \"email\", \"type\": \"TEXT\", \"nullable\": false, \"unique\": true},\n        {\"name\": \"created_at\", \"type\": \"TIMESTAMP\", \"default\": \"NOW()\"}\n      ]\n    }\n  ]\n}"
      }
    ]
  }
}
```

The response contains a `contents` array (note the plural — a single resource read can return multiple content items). Each content item has:

- **`uri`**: The URI of the content (usually matches the requested URI)
- **`mimeType`** (optional): The MIME type of the content
- **`text`**: For text content (strings, JSON, Markdown, etc.)
- **`blob`**: For binary content (base64-encoded), used instead of `text`

---

## 6.5 Resource Content Types: Text vs. Binary (Base64)

Resources can contain two types of content:

### Text Content

For human-readable data — strings, JSON, XML, Markdown, code, etc.:

```json
{
  "uri": "file:///home/user/project/README.md",
  "mimeType": "text/markdown",
  "text": "# My Project\n\nThis is a sample project.\n\n## Getting Started\n..."
}
```

### Binary Content (Base64)

For binary data — images, PDFs, compiled files, etc.:

```json
{
  "uri": "file:///home/user/project/logo.png",
  "mimeType": "image/png",
  "blob": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
}
```

A content item has either `text` or `blob`, never both. The `mimeType` helps the client understand how to interpret the content. If no MIME type is provided, the client should assume `text/plain` for text content and `application/octet-stream` for binary content.

---

## 6.6 Resource Subscriptions and Change Notifications

MCP supports a subscription mechanism for resources that change over time. This is useful for live data — metrics, log files, database states — where the AI might need to stay informed of changes.

### Subscribing

The client subscribes to a resource by sending a `resources/subscribe` request:

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "resources/subscribe",
  "params": {
    "uri": "metrics://cpu/usage"
  }
}
```

The server acknowledges the subscription:

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {}
}
```

### Receiving Updates

When the subscribed resource changes, the server sends a notification:

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/resources/updated",
  "params": {
    "uri": "metrics://cpu/usage"
  }
}
```

The notification does not contain the new content — it only signals that the resource has changed. The client should call `resources/read` to get the updated content if it needs the new data.

### Unsubscribing

To stop receiving notifications:

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "resources/unsubscribe",
  "params": {
    "uri": "metrics://cpu/usage"
  }
}
```

### List Change Notifications

Separate from individual resource updates, servers can notify clients when the overall resource list changes:

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/resources/list_changed"
}
```

This signals that the set of available resources has changed — resources may have been added or removed. The client should call `resources/list` again.

Subscription support is optional and declared during capability negotiation:

```json
{
  "capabilities": {
    "resources": {
      "subscribe": true,
      "listChanged": true
    }
  }
}
```

---

## 6.7 Resources vs. Tools: When to Use Which

A common question when designing MCP servers is: should this be a resource or a tool? The answer depends on the nature of the interaction.

| Aspect | Resources | Tools |
|--------|-----------|-------|
| **Purpose** | Provide data/context | Perform actions |
| **Direction** | Read-only | Can read and write |
| **Identified by** | URI | Name |
| **Input** | URI (+ template variables) | Arbitrary JSON arguments |
| **Use case** | "What is the current state?" | "Change the state" or "Compute something" |
| **Side effects** | None | May have side effects |
| **Caching** | Safe to cache | Not necessarily safe to cache |
| **Discovery** | Application-controlled (explicit selection) | Model-controlled (AI decides) |

### Decision Guidelines

**Use a resource when:**
- The data is relatively static or changes predictably
- The data provides context for the AI's reasoning
- The data can be identified by a URI
- There are no side effects from reading the data
- The application (host) should decide when to read it

**Use a tool when:**
- The operation has side effects (writes, sends, creates)
- The operation requires complex input parameters
- The AI model should decide when to perform the operation
- The operation is computational (transforming data, not just reading it)
- The result depends on the specific arguments provided

**Examples:**
- Database schema → **Resource** (static context, no side effects)
- Run a SQL query → **Tool** (dynamic input, potential side effects)
- Current config values → **Resource** (read-only context)
- Update a config value → **Tool** (has side effects)
- File contents → **Resource** (read-only, identified by URI)
- Write to a file → **Tool** (has side effects)

An important subtlety: **who controls when the data is accessed?** Resources are typically loaded by the application (host) to provide context to the AI — the user might select them from a list, or the application might include them automatically. Tools are invoked by the AI model as part of its reasoning. This difference in control flow is often the deciding factor.

---

## 6.8 Designing Resource Hierarchies

When a server exposes many resources, organizing them into a logical hierarchy improves discoverability and usability.

### URI Scheme Design

Choose a URI scheme that reflects your domain's structure:

```
db://                          Database server
├── db://main/                 Main database
│   ├── db://main/schema       Full schema
│   ├── db://main/tables       Table list
│   ├── db://main/users/       Users table
│   │   ├── db://main/users/schema     Table schema
│   │   └── db://main/users/stats      Table statistics
│   └── db://main/orders/      Orders table
│       ├── db://main/orders/schema
│       └── db://main/orders/stats
└── db://analytics/            Analytics database
    └── ...
```

### Combining Resources and Templates

Use concrete resources for well-known, frequently-accessed data and templates for dynamic access:

**Concrete resources:**
- `db://main/schema` — the most commonly needed resource, always available
- `db://main/tables` — a quick overview of available tables

**Templates:**
- `db://{database}/{table}/schema` — access any table's schema
- `db://{database}/{table}/sample?rows={count}` — sample data from any table

This gives the AI both quick access to common data and flexible access to anything else.

---

## 6.9 Real-World Resource Examples

### File System Resources

```json
{
  "uri": "file:///home/user/project/package.json",
  "name": "package.json",
  "description": "Node.js project configuration and dependencies",
  "mimeType": "application/json"
}
```

### Git Repository Resources

```json
{
  "uri": "git://myrepo/status",
  "name": "Repository Status",
  "description": "Current git status including modified, staged, and untracked files",
  "mimeType": "text/plain"
}
```

### API Documentation Resources

```json
{
  "uri": "docs://api/v2/users",
  "name": "Users API Documentation",
  "description": "Complete documentation for the /users endpoint including request/response schemas, authentication requirements, and rate limits",
  "mimeType": "text/markdown"
}
```

### System Metrics Resources

```json
{
  "uri": "metrics://system/overview",
  "name": "System Overview",
  "description": "Current system metrics including CPU, memory, disk, and network usage",
  "mimeType": "application/json"
}
```

---

## Summary

Resources are MCP's primitive for providing data and context to AI models. They complement tools by providing the information the AI needs to make informed decisions about what actions to take.

Key takeaways:

- **Resources are identified by URIs** and provide read-only access to data
- **Discovery** happens through `resources/list` (concrete resources) and `resources/templates/list` (dynamic patterns)
- **Reading** is done through `resources/read`, which returns text or base64-encoded binary content
- **Subscriptions** allow clients to receive notifications when resources change, enabling live data scenarios
- **Resources vs. tools**: Resources are for context (read-only, URI-identified, application-controlled), tools are for actions (parameterized, AI-controlled, potentially with side effects)
- **Good resource design** uses logical URI hierarchies and combines concrete resources with templates

In the next chapter, we will explore the third pillar: Prompts — reusable interaction templates that package common workflows.
