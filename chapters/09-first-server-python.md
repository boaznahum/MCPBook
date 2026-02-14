# Chapter 9: Your First MCP Server — Python (Primary)

---

## 9.1 Setting Up the Python Development Environment

Before building an MCP server, you need a properly configured Python development environment.

### Prerequisites

- **Python 3.10 or later**: MCP's Python SDK uses modern Python features including type hints, async/await, and dataclasses
- **uv** (recommended) or **pip**: `uv` is a fast Python package manager that handles virtual environments and dependency resolution. It is the recommended tool for MCP development.

### Installing uv

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with pip
pip install uv
```

### Creating a Project

```bash
# Create a new project directory
mkdir my-mcp-server
cd my-mcp-server

# Initialize a Python project with uv
uv init

# Add the MCP SDK as a dependency
uv add "mcp[cli]"
```

The `mcp[cli]` extra installs the MCP command-line tools, which include the MCP Inspector for testing and debugging.

Alternatively, with pip:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install "mcp[cli]"
```

### Project Structure

A minimal MCP server project looks like:

```
my-mcp-server/
├── pyproject.toml
├── server.py          # Your MCP server
└── README.md
```

---

## 9.2 The Python MCP SDK: Overview and Installation

The Python MCP SDK (`mcp`) provides everything you need to build MCP servers and clients. It is the official SDK maintained by Anthropic alongside the TypeScript SDK.

### Key Components

| Component | Purpose |
|-----------|---------|
| `FastMCP` | High-level API for building servers with decorators |
| `Server` | Low-level server API for advanced use cases |
| `ClientSession` | Client for connecting to MCP servers |
| Transports | stdio, SSE, and Streamable HTTP transport implementations |
| Types | Type definitions for all MCP messages |

### Installation

```bash
uv add "mcp[cli]"
```

This installs:
- `mcp` — the core SDK with server and client classes
- `mcp` CLI — command-line tools including `mcp dev` for the Inspector

### Verifying the Installation

```bash
# Check that the SDK is installed
python -c "import mcp; print(mcp.__version__)"

# Check that the CLI is available
mcp --help
```

---

## 9.3 FastMCP: The High-Level Pythonic API

`FastMCP` is the recommended way to build MCP servers in Python. It provides a clean, decorator-based API that feels natural to Python developers — similar to how FastAPI or Flask work for web applications.

### Creating a Server

```python
from mcp.server.fastmcp import FastMCP

# Create a server instance
mcp = FastMCP("my-server")
```

The string argument is the server's name, which is reported during the initialization handshake.

### The Minimal Server

Here is the absolute simplest MCP server — it has no tools, resources, or prompts, but it is a valid MCP server that can connect and respond to initialization:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("minimal-server")

if __name__ == "__main__":
    mcp.run()
```

Run it:

```bash
python server.py
```

This starts the server using the stdio transport, reading from stdin and writing to stdout. It will wait for an MCP client to connect.

### 9.3.1 Creating a Server with `FastMCP`

Let us build a more useful server — a weather service that provides a tool to get weather data:

```python
from mcp.server.fastmcp import FastMCP

# Create server with a descriptive name
mcp = FastMCP("weather-server")

@mcp.tool()
async def get_weather(city: str, units: str = "celsius") -> str:
    """Get the current weather for a city.

    Args:
        city: The city name (e.g., "San Francisco", "London")
        units: Temperature units - "celsius" or "fahrenheit" (default: celsius)
    """
    # In a real server, you would call a weather API here
    return f"The weather in {city} is 22°{'C' if units == 'celsius' else 'F'}, partly cloudy."

if __name__ == "__main__":
    mcp.run()
```

That is it. With just a few lines of code, you have a working MCP server that:

- Declares a tool named `get_weather`
- Automatically generates a JSON Schema for its input from the type annotations
- Uses the docstring as the tool description
- Handles the MCP protocol (initialization, tool discovery, tool invocation)

### 9.3.2 Defining Tools with `@mcp.tool()`

The `@mcp.tool()` decorator turns a Python function into an MCP tool. FastMCP uses Python's type system to automatically generate the tool's input schema.

#### Basic Tool

```python
@mcp.tool()
async def add(a: int, b: int) -> str:
    """Add two numbers together."""
    return str(a + b)
```

This creates a tool with:
- Name: `add` (from the function name)
- Description: "Add two numbers together." (from the docstring)
- Input schema: `{"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}}, "required": ["a", "b"]}`

#### Tool with Optional Parameters

```python
@mcp.tool()
async def search_files(
    pattern: str,
    directory: str = ".",
    max_results: int = 10
) -> str:
    """Search for files matching a glob pattern.

    Args:
        pattern: Glob pattern to match (e.g., "*.py", "**/*.md")
        directory: Directory to search in (default: current directory)
        max_results: Maximum number of results to return (default: 10)
    """
    import glob
    matches = glob.glob(pattern, root_dir=directory, recursive=True)
    results = matches[:max_results]
    return "\n".join(results) if results else "No files found."
```

Parameters with default values become optional in the schema. Parameters without defaults are required.

#### Tool with Custom Name

```python
@mcp.tool(name="execute_query")
async def run_database_query(sql: str, database: str = "main") -> str:
    """Execute a read-only SQL query against the database."""
    # The tool name in MCP will be "execute_query", not "run_database_query"
    ...
```

#### Tool with Annotations

```python
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
async def list_tables(database: str = "main") -> str:
    """List all tables in the database."""
    ...
```

#### Complex Input Types

FastMCP supports Pydantic models for complex input structures:

```python
from pydantic import BaseModel, Field

class IssueCreate(BaseModel):
    """Parameters for creating a GitHub issue."""
    owner: str = Field(description="Repository owner")
    repo: str = Field(description="Repository name")
    title: str = Field(description="Issue title")
    body: str = Field(default="", description="Issue body (Markdown)")
    labels: list[str] = Field(default_factory=list, description="Labels to apply")

@mcp.tool()
async def create_issue(params: IssueCreate) -> str:
    """Create a new GitHub issue."""
    # Use params.owner, params.repo, etc.
    ...
```

#### Returning Structured Content

Tools can return different content types using MCP's content objects:

```python
from mcp.types import TextContent, ImageContent

@mcp.tool()
async def generate_chart(data: str, chart_type: str = "bar") -> list:
    """Generate a chart from data."""
    import base64
    # ... generate chart image ...
    chart_bytes = generate_chart_image(data, chart_type)

    return [
        TextContent(type="text", text=f"Generated {chart_type} chart"),
        ImageContent(
            type="image",
            data=base64.b64encode(chart_bytes).decode(),
            mimeType="image/png"
        )
    ]
```

### 9.3.3 Defining Resources with `@mcp.resource()`

Resources are defined with the `@mcp.resource()` decorator:

```python
@mcp.resource("config://app/settings")
async def get_app_settings() -> str:
    """Current application settings."""
    import json
    settings = {
        "debug": False,
        "database_url": "postgresql://localhost/myapp",
        "max_connections": 20
    }
    return json.dumps(settings, indent=2)
```

The string argument is the resource URI. The function's return value becomes the resource content. The docstring becomes the resource description.

#### Dynamic Resources with URI Templates

```python
@mcp.resource("file:///{path}")
async def read_file(path: str) -> str:
    """Read a file from the filesystem."""
    with open(f"/{path}", "r") as f:
        return f.read()
```

The `{path}` in the URI is a template variable. When a client requests `file:///home/user/data.txt`, FastMCP extracts `path = "home/user/data.txt"` and passes it to the function.

#### Resources with MIME Types

```python
@mcp.resource("db://schema", mime_type="application/json")
async def get_database_schema() -> str:
    """Complete database schema."""
    ...
```

### 9.3.4 Defining Prompts with `@mcp.prompt()`

Prompts are defined with the `@mcp.prompt()` decorator:

```python
from mcp.server.fastmcp import FastMCP
from mcp.types import UserMessage, AssistantMessage

@mcp.prompt()
async def code_review(language: str = "python", focus: str = "all") -> list:
    """Review code for quality and potential issues.

    Args:
        language: The programming language being reviewed
        focus: Area to focus on - security, performance, style, or all
    """
    focus_instructions = {
        "security": "Focus specifically on security vulnerabilities including injection attacks, authentication issues, and data exposure.",
        "performance": "Focus specifically on performance issues including algorithmic complexity, memory usage, and I/O patterns.",
        "style": "Focus specifically on code style, readability, naming conventions, and adherence to language idioms.",
        "all": "Review comprehensively for security, performance, style, and correctness."
    }

    return [
        UserMessage(
            content=f"You are an expert {language} code reviewer. "
            f"{focus_instructions.get(focus, focus_instructions['all'])}\n\n"
            f"For each issue found, provide:\n"
            f"1. Severity (Critical/High/Medium/Low)\n"
            f"2. Line reference\n"
            f"3. Description\n"
            f"4. Suggested fix with code"
        )
    ]
```

#### Simple String Prompts

For simple prompts, you can return a string instead of a message list:

```python
@mcp.prompt()
async def explain_error(error_message: str) -> str:
    """Explain an error message and suggest fixes."""
    return (
        f"Please explain the following error message in plain language "
        f"and suggest how to fix it:\n\n```\n{error_message}\n```"
    )
```

FastMCP wraps the string in a `UserMessage` automatically.

---

## 9.4 Type Annotations and Automatic Schema Generation

One of FastMCP's most powerful features is automatic JSON Schema generation from Python type annotations. This eliminates the need to manually write schemas.

### How It Works

FastMCP inspects the function's type annotations and generates a JSON Schema:

| Python Type | JSON Schema |
|-------------|-------------|
| `str` | `{"type": "string"}` |
| `int` | `{"type": "integer"}` |
| `float` | `{"type": "number"}` |
| `bool` | `{"type": "boolean"}` |
| `list[str]` | `{"type": "array", "items": {"type": "string"}}` |
| `dict[str, int]` | `{"type": "object"}` |
| `Optional[str]` | `{"type": "string"}` (not required) |
| `Literal["a", "b"]` | `{"type": "string", "enum": ["a", "b"]}` |

### Descriptions from Docstrings

FastMCP extracts parameter descriptions from Google-style docstrings:

```python
@mcp.tool()
async def search(
    query: str,
    max_results: int = 10,
    include_archived: bool = False
) -> str:
    """Search for documents in the knowledge base.

    Args:
        query: The search query string. Supports boolean operators (AND, OR, NOT).
        max_results: Maximum number of results to return. Must be between 1 and 100.
        include_archived: Whether to include archived documents in results.
    """
    ...
```

This generates:

```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "The search query string. Supports boolean operators (AND, OR, NOT)."
    },
    "max_results": {
      "type": "integer",
      "description": "Maximum number of results to return. Must be between 1 and 100.",
      "default": 10
    },
    "include_archived": {
      "type": "boolean",
      "description": "Whether to include archived documents in results.",
      "default": false
    }
  },
  "required": ["query"]
}
```

### Pydantic Models for Complex Types

For complex parameter structures, use Pydantic models:

```python
from pydantic import BaseModel, Field
from typing import Literal

class QueryParams(BaseModel):
    sql: str = Field(description="The SQL query to execute")
    database: str = Field(default="main", description="Target database")
    timeout: int = Field(default=30, description="Query timeout in seconds", ge=1, le=300)
    format: Literal["table", "json", "csv"] = Field(
        default="table",
        description="Output format for the results"
    )

@mcp.tool()
async def query(params: QueryParams) -> str:
    """Execute a SQL query against the database."""
    ...
```

Pydantic's `Field` provides rich metadata including descriptions, defaults, and validation constraints (`ge`, `le`, `min_length`, etc.).

---

## 9.5 The `Context` Object

FastMCP provides a `Context` object that gives tool handlers access to MCP protocol features like progress reporting, logging, and request metadata.

To use it, add a parameter with the `Context` type:

```python
from mcp.server.fastmcp import FastMCP, Context

@mcp.tool()
async def long_running_task(data: str, ctx: Context) -> str:
    """Process a large dataset with progress reporting."""
    items = data.split("\n")
    total = len(items)

    results = []
    for i, item in enumerate(items):
        # Report progress
        await ctx.report_progress(i, total)

        # Process the item
        result = process_item(item)
        results.append(result)

    return "\n".join(results)
```

The `Context` parameter is automatically injected by FastMCP — it does not appear in the tool's input schema.

### 9.5.1 Progress Reporting

```python
await ctx.report_progress(current=50, total=100)
```

This sends a `notifications/progress` message to the client. The host can use this to show a progress bar or status update.

### 9.5.2 Logging

```python
await ctx.info("Processing started")
await ctx.debug("Processing item 42")
await ctx.warning("Approaching rate limit")
await ctx.error("Failed to process item 99")
```

These send `notifications/message` log entries to the client at the appropriate log level.

### 9.5.3 Accessing Request Metadata

```python
# Get the request ID
request_id = ctx.request_id

# Get the client's declared capabilities
client_capabilities = ctx.session.client_capabilities
```

---

## 9.6 Running and Testing Your Server

### Running with stdio

The simplest way to run your server is with stdio transport:

```python
if __name__ == "__main__":
    mcp.run()  # Defaults to stdio transport
```

```bash
python server.py
```

### Running with the MCP Inspector

The MCP Inspector is the best way to test your server during development:

```bash
mcp dev server.py
```

This launches a web-based interface where you can:
- See the server's capabilities
- List and invoke tools
- List and read resources
- List and retrieve prompts
- Inspect raw JSON-RPC messages
- View server logs

### Running with SSE Transport

For network-accessible servers:

```python
if __name__ == "__main__":
    mcp.run(transport="sse")
```

### Testing with a Python Script

You can also test your server programmatically by creating a client:

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_server():
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"]
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize
            await session.initialize()

            # List tools
            tools = await session.list_tools()
            print(f"Available tools: {[t.name for t in tools.tools]}")

            # Call a tool
            result = await session.call_tool(
                "get_weather",
                arguments={"city": "San Francisco"}
            )
            print(f"Result: {result.content[0].text}")

asyncio.run(test_server())
```

---

## 9.7 The Low-Level Python Server API

While FastMCP is the recommended approach, the Python SDK also provides a low-level `Server` class for cases where you need full control over request handling.

```python
from mcp.server import Server
from mcp.types import (
    Tool,
    TextContent,
    ListToolsResult,
    CallToolResult,
)

server = Server("low-level-server")

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="greet",
            description="Generate a greeting",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name to greet"
                    }
                },
                "required": ["name"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "greet":
        greeting = f"Hello, {arguments['name']}!"
        return [TextContent(type="text", text=greeting)]
    raise ValueError(f"Unknown tool: {name}")

async def main():
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### When to Use Low-Level vs. High-Level

**Use FastMCP when:**
- You want rapid development with minimal boilerplate
- Your tools have standard input/output patterns
- You appreciate automatic schema generation from type annotations
- You are building a new server from scratch

**Use the low-level Server when:**
- You need custom request handling logic
- You want to integrate with an existing server framework
- You need to handle protocol-level details that FastMCP abstracts away
- You are building middleware or proxies

---

## 9.8 Error Handling Patterns

### Tool-Level Errors

Return errors as tool results with `isError: true`:

```python
@mcp.tool()
async def query(sql: str) -> str:
    """Execute a SQL query."""
    try:
        result = execute_sql(sql)
        return format_results(result)
    except PermissionError:
        raise  # FastMCP catches and returns as isError: true
    except Exception as e:
        # You can also return error text manually
        return f"Error executing query: {e}"
```

When a tool function raises an exception, FastMCP catches it and returns the error message as a tool result with `isError: true`. This is the correct behavior — it signals to the AI model that the tool was invoked correctly but the operation failed.

### Input Validation

FastMCP validates inputs against the generated schema automatically. If a required parameter is missing or has the wrong type, the request fails before your function is called.

For additional validation, use Pydantic:

```python
from pydantic import BaseModel, Field, validator

class FileWriteParams(BaseModel):
    path: str = Field(description="File path to write to")
    content: str = Field(description="Content to write")

    @validator("path")
    def validate_path(cls, v):
        if ".." in v:
            raise ValueError("Path traversal not allowed")
        if not v.startswith("/allowed/"):
            raise ValueError("Can only write to /allowed/ directory")
        return v

@mcp.tool()
async def write_file(params: FileWriteParams) -> str:
    """Write content to a file."""
    with open(params.path, "w") as f:
        f.write(params.content)
    return f"Written {len(params.content)} bytes to {params.path}"
```

---

## 9.9 Complete Example: A Database Query MCP Server

Let us build a complete, production-quality MCP server that provides SQL query access to a SQLite database.

```python
"""
Database Query MCP Server

A complete MCP server that provides read-only SQL query access
to a SQLite database, along with schema exploration tools and resources.
"""

import sqlite3
import json
from pathlib import Path
from mcp.server.fastmcp import FastMCP, Context

# Create the server
mcp = FastMCP("database-server")

# Database path (configurable via environment variable)
import os
DB_PATH = os.environ.get("DB_PATH", "database.db")


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── Tools ───────────────────────────────────────────────────

@mcp.tool()
async def query(sql: str, ctx: Context) -> str:
    """Execute a read-only SQL query against the database.

    Only SELECT statements are allowed. Results are returned as a
    formatted table. Queries are limited to 1000 rows.

    Args:
        sql: The SQL SELECT query to execute
    """
    # Validate: only allow SELECT
    stripped = sql.strip().upper()
    if not stripped.startswith("SELECT"):
        return "Error: Only SELECT queries are allowed. Use read-only queries."

    await ctx.info(f"Executing query: {sql[:100]}...")

    try:
        conn = get_connection()
        cursor = conn.execute(sql)
        rows = cursor.fetchmany(1000)
        columns = [desc[0] for desc in cursor.description]
        conn.close()

        if not rows:
            return "Query returned no results."

        # Format as a table
        col_widths = [len(c) for c in columns]
        for row in rows:
            for i, val in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(val)))

        header = " | ".join(c.ljust(w) for c, w in zip(columns, col_widths))
        separator = "-+-".join("-" * w for w in col_widths)

        lines = [header, separator]
        for row in rows:
            line = " | ".join(str(v).ljust(w) for v, w in zip(row, col_widths))
            lines.append(line)

        result = "\n".join(lines)
        result += f"\n\n{len(rows)} row(s) returned."
        return result

    except sqlite3.Error as e:
        return f"SQL Error: {e}"


@mcp.tool()
async def list_tables() -> str:
    """List all tables in the database with their row counts."""
    conn = get_connection()
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row["name"] for row in cursor.fetchall()]

    results = []
    for table in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]
        results.append(f"  {table} ({count:,} rows)")

    conn.close()
    return "Tables in database:\n" + "\n".join(results)


@mcp.tool()
async def describe_table(table_name: str) -> str:
    """Show the schema of a specific table including columns, types, and constraints.

    Args:
        table_name: The name of the table to describe
    """
    conn = get_connection()
    cursor = conn.execute(f"PRAGMA table_info([{table_name}])")
    columns = cursor.fetchall()
    conn.close()

    if not columns:
        return f"Table '{table_name}' not found."

    lines = [f"Schema for table '{table_name}':", ""]
    lines.append(f"{'Column':<20} {'Type':<15} {'Nullable':<10} {'Default':<15} {'PK'}")
    lines.append("-" * 70)

    for col in columns:
        nullable = "YES" if not col["notnull"] else "NO"
        default = str(col["dflt_value"]) if col["dflt_value"] else ""
        pk = "YES" if col["pk"] else ""
        lines.append(
            f"{col['name']:<20} {col['type']:<15} {nullable:<10} {default:<15} {pk}"
        )

    return "\n".join(lines)


# ─── Resources ───────────────────────────────────────────────

@mcp.resource("db://schema", mime_type="application/json")
async def get_full_schema() -> str:
    """Complete database schema as JSON, including all tables and their columns."""
    conn = get_connection()
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row["name"] for row in cursor.fetchall()]

    schema = {"tables": []}
    for table_name in tables:
        cols = conn.execute(f"PRAGMA table_info([{table_name}])").fetchall()
        table = {
            "name": table_name,
            "columns": [
                {
                    "name": col["name"],
                    "type": col["type"],
                    "nullable": not col["notnull"],
                    "primary_key": bool(col["pk"]),
                    "default": col["dflt_value"]
                }
                for col in cols
            ]
        }
        schema["tables"].append(table)

    conn.close()
    return json.dumps(schema, indent=2)


@mcp.resource("db://{table_name}/schema", mime_type="application/json")
async def get_table_schema(table_name: str) -> str:
    """Schema for a specific table."""
    conn = get_connection()
    cols = conn.execute(f"PRAGMA table_info([{table_name}])").fetchall()
    conn.close()

    if not cols:
        return json.dumps({"error": f"Table '{table_name}' not found"})

    schema = {
        "table": table_name,
        "columns": [
            {
                "name": col["name"],
                "type": col["type"],
                "nullable": not col["notnull"],
                "primary_key": bool(col["pk"]),
            }
            for col in cols
        ]
    }
    return json.dumps(schema, indent=2)


# ─── Prompts ─────────────────────────────────────────────────

@mcp.prompt()
async def analyze_table(table_name: str) -> str:
    """Analyze a database table — provide insights on schema design,
    data distribution, and optimization opportunities.

    Args:
        table_name: The table to analyze
    """
    return (
        f"Please analyze the '{table_name}' table in the connected database. "
        f"Start by examining its schema (use the describe_table tool), "
        f"then run some exploratory queries to understand the data. "
        f"Provide insights on:\n"
        f"1. Schema design quality\n"
        f"2. Data distribution and potential anomalies\n"
        f"3. Missing indexes (if query patterns are apparent)\n"
        f"4. Suggested improvements"
    )


@mcp.prompt()
async def query_builder(goal: str) -> str:
    """Help construct an optimized SQL query.

    Args:
        goal: What data you want to retrieve, in plain English
    """
    return (
        f"I need help writing a SQL query. My goal is: {goal}\n\n"
        f"Please:\n"
        f"1. First examine the database schema (use list_tables and describe_table)\n"
        f"2. Write the SQL query\n"
        f"3. Explain the query step by step\n"
        f"4. Suggest any optimizations"
    )


# ─── Entry Point ─────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
```

### Testing This Server

1. **Create a test database:**

```python
import sqlite3

conn = sqlite3.connect("database.db")
conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.execute("""
    INSERT OR IGNORE INTO users (name, email) VALUES
    ('Alice', 'alice@example.com'),
    ('Bob', 'bob@example.com'),
    ('Charlie', 'charlie@example.com')
""")
conn.commit()
conn.close()
```

2. **Run with the MCP Inspector:**

```bash
mcp dev server.py
```

3. **Configure in Claude Desktop:**

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "database": {
      "command": "python",
      "args": ["/path/to/server.py"],
      "env": {
        "DB_PATH": "/path/to/database.db"
      }
    }
  }
}
```

---

## Summary

Building MCP servers in Python with FastMCP is remarkably straightforward. The decorator-based API, automatic schema generation from type annotations, and built-in transport handling mean you can focus on your server's logic rather than protocol mechanics.

Key takeaways:

- **FastMCP** is the recommended high-level API — it handles protocol details automatically
- **`@mcp.tool()`** creates tools with auto-generated JSON Schema from Python type hints
- **`@mcp.resource()`** exposes data via URIs, supporting both static and template-based resources
- **`@mcp.prompt()`** creates reusable interaction templates with arguments
- **Type annotations** are the source of truth for schemas — use `str`, `int`, `bool`, `list`, Pydantic models, and `Literal` types
- **The `Context` object** provides access to progress reporting, logging, and request metadata
- **Error handling** uses Python exceptions — FastMCP converts them to proper MCP error responses
- **Testing** is easy with the MCP Inspector (`mcp dev server.py`) or programmatic client scripts
- **The low-level `Server` API** is available for advanced use cases requiring full protocol control

In the next chapter, we will build the same concepts in TypeScript, showing how the TypeScript SDK approaches the same problems.
