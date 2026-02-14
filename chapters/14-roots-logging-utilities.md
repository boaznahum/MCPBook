# Chapter 14: Roots, Logging, and Utilities

---

## 14.1 Roots: Defining File System Boundaries

### 14.1.1 What Are Roots?

Roots are URIs that define the boundaries within which an MCP server should operate. They tell the server "these are the locations you are expected to work with." Roots are typically file system paths or workspace URIs that indicate the scope of the current session.

For example, if a user is working on a project in `/home/user/myproject`, the host can communicate this as a root, and the server knows to focus its operations within that directory.

```json
// Root example
{
  "uri": "file:///home/user/myproject",
  "name": "My Project"
}
```

Roots are **informational, not enforcing**. The server is expected to respect roots, but the protocol does not prevent it from accessing resources outside the root boundaries. Enforcement is the server's responsibility.

### 14.1.2 How Clients Communicate Roots to Servers

Roots are communicated through the `roots/list` request. When a server wants to know its root boundaries, it sends:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "roots/list"
}
```

The client responds:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "roots": [
      {
        "uri": "file:///home/user/myproject",
        "name": "Main Project"
      },
      {
        "uri": "file:///home/user/shared-libs",
        "name": "Shared Libraries"
      }
    ]
  }
}
```

The client must declare `roots` in its capabilities during initialization:

```json
{
  "capabilities": {
    "roots": {
      "listChanged": true
    }
  }
}
```

### 14.1.3 Dynamic Root Changes

Roots can change during a session — for example, when the user opens a new workspace or adds a folder. The client notifies the server:

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/roots/list_changed"
}
```

The server should then call `roots/list` again to get the updated roots.

**Python server handling roots:**

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("root-aware-server")

@mcp.tool()
async def search_code(pattern: str, ctx: Context) -> str:
    """Search for code patterns within the project roots."""
    roots = await ctx.session.list_roots()

    results = []
    for root in roots.roots:
        path = root.uri.replace("file://", "")
        matches = search_in_directory(path, pattern)
        results.extend(matches)

    return "\n".join(results) if results else "No matches found."
```

---

## 14.2 Logging Framework

MCP includes a built-in logging framework that allows servers to send structured log messages to the client.

### 14.2.1 Log Levels and the `notifications/message` Format

Log messages are sent as notifications:

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/message",
  "params": {
    "level": "info",
    "logger": "database",
    "data": "Connected to PostgreSQL on localhost:5432"
  }
}
```

MCP defines the following log levels (from lowest to highest severity):

| Level | Purpose |
|-------|---------|
| `debug` | Detailed debugging information |
| `info` | General informational messages |
| `notice` | Normal but significant events |
| `warning` | Warning conditions |
| `error` | Error conditions |
| `critical` | Critical conditions |
| `alert` | Action must be taken immediately |
| `emergency` | System is unusable |

### 14.2.2 Setting Log Level from the Client

The client can control the minimum log level the server should send:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "logging/setLevel",
  "params": {
    "level": "warning"
  }
}
```

After this request, the server should only send log messages at `warning` level or above. This prevents flooding the client with debug messages during normal operation.

### 14.2.3 Structured Logging Best Practices

**Python logging with FastMCP:**

```python
@mcp.tool()
async def process_data(file_path: str, ctx: Context) -> str:
    """Process a data file with detailed logging."""
    await ctx.info(f"Starting to process {file_path}")

    try:
        data = read_file(file_path)
        await ctx.debug(f"Read {len(data)} bytes from file")

        results = transform_data(data)
        await ctx.info(f"Processed {len(results)} records successfully")

        return format_results(results)
    except FileNotFoundError:
        await ctx.error(f"File not found: {file_path}")
        return f"Error: File not found: {file_path}"
    except Exception as e:
        await ctx.error(f"Processing failed: {e}")
        raise
```

**Best practices:**

1. Use appropriate log levels — `debug` for internal details, `info` for progress, `warning` for concerns, `error` for failures
2. Include relevant context in log messages (file names, counts, identifiers)
3. Do not log sensitive information (passwords, API keys, personal data)
4. Log at the `info` level for operations the user might want to see
5. Log at `debug` level for information useful only during development

---

## 14.3 Progress Reporting

Progress reporting allows servers to communicate the status of long-running operations to the client.

### 14.3.1 Progress Tokens

Progress is tracked using **progress tokens** — opaque identifiers that link progress notifications to specific requests. The client includes a progress token in the request's `_meta` field:

```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "method": "tools/call",
  "params": {
    "_meta": {
      "progressToken": "progress-abc-123"
    },
    "name": "bulk_import",
    "arguments": { "file": "/data/large.csv" }
  }
}
```

### 14.3.2 The `notifications/progress` Message

The server sends progress updates referencing the token:

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/progress",
  "params": {
    "progressToken": "progress-abc-123",
    "progress": 2500,
    "total": 10000,
    "message": "Imported 2,500 of 10,000 records"
  }
}
```

- **`progressToken`**: The token from the request
- **`progress`**: Current progress value
- **`total`** (optional): Total expected value (if known)
- **`message`** (optional): Human-readable progress description

### 14.3.3 Implementing Progress Bars and Status Updates

**Python implementation:**

```python
@mcp.tool()
async def bulk_process(items: list[str], ctx: Context) -> str:
    """Process a list of items with progress reporting."""
    total = len(items)
    results = []

    for i, item in enumerate(items):
        # Report progress
        await ctx.report_progress(i, total)

        # Process the item
        result = await process_single_item(item)
        results.append(result)

    # Report completion
    await ctx.report_progress(total, total)

    return f"Processed {total} items successfully."
```

---

## 14.4 Cancellation

MCP supports cancelling in-progress requests through the `notifications/cancelled` notification.

### 14.4.1 The `notifications/cancelled` Message

Either side can cancel a pending request:

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/cancelled",
  "params": {
    "requestId": 10,
    "reason": "User cancelled the operation"
  }
}
```

- **`requestId`**: The `id` of the request to cancel (must match a currently in-flight request)
- **`reason`** (optional): Human-readable reason for cancellation

### 14.4.2 Handling Cancellation in Long-Running Operations

Servers should check for cancellation during long-running operations:

```python
@mcp.tool()
async def long_running_search(query: str, ctx: Context) -> str:
    """Search through a large dataset."""
    results = []

    for chunk in get_data_chunks():
        # Check if the request has been cancelled
        if ctx.is_cancelled():
            return f"Search cancelled. Found {len(results)} results so far."

        matches = search_chunk(chunk, query)
        results.extend(matches)

        await ctx.report_progress(len(results), None)

    return format_results(results)
```

The receiver of a cancellation notification should:
1. Stop the in-progress work as soon as practical
2. Return any partial results if possible
3. Clean up any resources allocated for the operation
4. Send a response to the original request (either with partial results or an error)

Cancellation is **best-effort** — the notification may arrive after the operation has already completed.

---

## 14.5 Pagination

List operations in MCP support cursor-based pagination for handling large result sets.

### 14.5.1 Cursor-Based Pagination in List Operations

The following operations support pagination:
- `tools/list`
- `resources/list`
- `resources/templates/list`
- `prompts/list`

**First request (no cursor):**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "resources/list",
  "params": {}
}
```

**Response with next cursor:**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "resources": [ /* first 50 resources */ ],
    "nextCursor": "eyJvZmZzZXQiOiA1MH0="
  }
}
```

**Follow-up request:**

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "resources/list",
  "params": {
    "cursor": "eyJvZmZzZXQiOiA1MH0="
  }
}
```

When `nextCursor` is absent from the response, there are no more pages.

### 14.5.2 Implementing Pagination in Servers

```python
import base64
import json

PAGE_SIZE = 50

@server.list_resources()
async def handle_list_resources(cursor: str | None = None) -> dict:
    all_resources = get_all_resources()  # Your resource list

    # Decode cursor to get offset
    offset = 0
    if cursor:
        offset = json.loads(base64.b64decode(cursor))["offset"]

    # Get the current page
    page = all_resources[offset:offset + PAGE_SIZE]

    # Build response
    result = {"resources": page}

    # Add next cursor if there are more results
    if offset + PAGE_SIZE < len(all_resources):
        next_offset = offset + PAGE_SIZE
        result["nextCursor"] = base64.b64encode(
            json.dumps({"offset": next_offset}).encode()
        ).decode()

    return result
```

---

## 14.6 Ping/Pong: Connection Health Checks

MCP includes a simple `ping` mechanism for checking connection health:

```json
// Request (either direction)
{
  "jsonrpc": "2.0",
  "id": 99,
  "method": "ping"
}

// Response
{
  "jsonrpc": "2.0",
  "id": 99,
  "result": {}
}
```

The `ping` method can be sent by either the client or the server. The other side must respond with an empty result. This is useful for:

- Detecting dead connections
- Keeping connections alive (preventing timeout by proxies)
- Verifying that the other side is still responsive

---

## Summary

MCP's utility features provide the supporting infrastructure that production servers need.

Key takeaways:

- **Roots** define the boundaries for server operations, communicated via `roots/list` and change notifications
- **Logging** provides structured, level-aware log messages from server to client via `notifications/message`
- **Progress reporting** uses tokens to link progress updates to specific requests
- **Cancellation** allows either side to cancel in-flight requests via `notifications/cancelled`
- **Pagination** uses opaque cursors for efficient traversal of large list results
- **Ping/Pong** provides simple connection health checking

In the next chapter, we will tackle one of the most critical topics: Security and Trust in MCP.
