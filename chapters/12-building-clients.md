# Chapter 12: Building MCP Clients

---

## 12.1 Why Build an MCP Client?

While most MCP development focuses on building servers, understanding the client side is essential for:

- **Building host applications**: If you are creating an AI-powered application that needs to connect to MCP servers, you need a client
- **Testing servers**: Writing client code is the most reliable way to test your servers programmatically
- **Building bridges**: Creating adapters that connect MCP servers to non-MCP systems
- **Understanding the protocol**: Building a client deepens your understanding of MCP's complete flow

---

## 12.2 The TypeScript Client SDK

### 12.2.1 Creating a Client Instance

```typescript
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const client = new Client(
  { name: "my-client", version: "1.0.0" },
  { capabilities: { sampling: {} } }
);
```

### 12.2.2 Connecting to Servers

**Connecting via stdio:**

```typescript
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const transport = new StdioClientTransport({
  command: "python",
  args: ["server.py"],
  env: { DB_PATH: "/data/mydb.sqlite" }
});

await client.connect(transport);
```

**Connecting via Streamable HTTP:**

```typescript
import { StreamableHTTPClientTransport } from
  "@modelcontextprotocol/sdk/client/streamableHttp.js";

const transport = new StreamableHTTPClientTransport(
  new URL("http://localhost:3000/mcp")
);

await client.connect(transport);
```

### 12.2.3 Discovering Capabilities

After connecting and initializing, you can discover what the server offers:

```typescript
// List available tools
const toolsResult = await client.listTools();
console.log("Tools:", toolsResult.tools.map(t => t.name));

// List resources
const resourcesResult = await client.listResources();
console.log("Resources:", resourcesResult.resources.map(r => r.uri));

// List prompts
const promptsResult = await client.listPrompts();
console.log("Prompts:", promptsResult.prompts.map(p => p.name));
```

### 12.2.4 Calling Tools and Reading Resources

```typescript
// Call a tool
const result = await client.callTool({
  name: "query",
  arguments: { sql: "SELECT COUNT(*) FROM users" }
});
console.log("Result:", result.content[0].text);

// Read a resource
const resource = await client.readResource({
  uri: "db://main/schema"
});
console.log("Schema:", resource.contents[0].text);

// Get a prompt
const prompt = await client.getPrompt({
  name: "code_review",
  arguments: { language: "python" }
});
console.log("Prompt messages:", prompt.messages);
```

---

## 12.3 The Python Client SDK

### 12.3.1 Creating a Client Session

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="python",
    args=["server.py"],
    env={"DB_PATH": "/data/mydb.sqlite"}
)
```

### 12.3.2 Using `ClientSession` with Transports

**stdio client:**

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(
        command="python",
        args=["server.py"]
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()

            # List tools
            tools = await session.list_tools()
            for tool in tools.tools:
                print(f"Tool: {tool.name} — {tool.description}")

            # Call a tool
            result = await session.call_tool(
                "query",
                arguments={"sql": "SELECT COUNT(*) FROM users"}
            )
            print(f"Result: {result.content[0].text}")

            # List resources
            resources = await session.list_resources()
            for resource in resources.resources:
                print(f"Resource: {resource.uri} — {resource.name}")

            # Read a resource
            content = await session.read_resource("db://main/schema")
            print(f"Schema: {content.contents[0].text}")

            # Get a prompt
            prompt = await session.get_prompt(
                "code_review",
                arguments={"language": "python"}
            )
            for msg in prompt.messages:
                print(f"[{msg.role}]: {msg.content.text}")

asyncio.run(main())
```

**Streamable HTTP client:**

```python
from mcp.client.streamable_http import streamablehttp_client

async def main():
    async with streamablehttp_client("http://localhost:3000/mcp") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            # ... use session as above ...
```

---

## 12.4 Building a Host Application

A host application manages multiple MCP clients and integrates them with an AI model. Here is a simplified host implementation in Python:

### 12.4.1 Managing Multiple Client Connections

```python
import asyncio
from dataclasses import dataclass
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

@dataclass
class ServerConnection:
    name: str
    session: ClientSession
    tools: list
    resources: list

class MCPHost:
    """A simplified MCP host that manages multiple server connections."""

    def __init__(self):
        self.connections: dict[str, ServerConnection] = {}
        self._tool_to_server: dict[str, str] = {}

    async def connect_server(self, name: str, command: str, args: list[str] = None):
        """Connect to an MCP server."""
        params = StdioServerParameters(command=command, args=args or [])

        read, write = await self._create_stdio_connection(params)
        session = ClientSession(read, write)
        await session.__aenter__()
        await session.initialize()

        # Discover capabilities
        tools_result = await session.list_tools()
        resources_result = await session.list_resources()

        conn = ServerConnection(
            name=name,
            session=session,
            tools=tools_result.tools,
            resources=resources_result.resources
        )
        self.connections[name] = conn

        # Build tool-to-server mapping
        for tool in tools_result.tools:
            self._tool_to_server[tool.name] = name

        print(f"Connected to {name}: {len(conn.tools)} tools, {len(conn.resources)} resources")

    def get_all_tools(self) -> list:
        """Get aggregated tool list from all connected servers."""
        all_tools = []
        for conn in self.connections.values():
            all_tools.extend(conn.tools)
        return all_tools

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Route a tool call to the correct server."""
        server_name = self._tool_to_server.get(tool_name)
        if not server_name:
            raise ValueError(f"Unknown tool: {tool_name}")

        session = self.connections[server_name].session
        result = await session.call_tool(tool_name, arguments)
        return result.content[0].text
```

### 12.4.2 Routing Requests to the Right Server

The host maintains a mapping from tool names to server connections. When the AI model requests a tool call, the host looks up the correct server and routes the request:

```python
async def handle_ai_tool_call(self, tool_name: str, arguments: dict):
    """Handle a tool call from the AI model."""
    # Find the right server
    server_name = self._tool_to_server.get(tool_name)
    if not server_name:
        return f"Error: Unknown tool '{tool_name}'"

    # Execute the call
    try:
        result = await self.connections[server_name].session.call_tool(
            tool_name, arguments
        )

        if result.isError:
            return f"Tool error: {result.content[0].text}"

        return result.content[0].text
    except Exception as e:
        return f"Error calling {tool_name}: {e}"
```

### 12.4.3 Aggregating Tool Lists for the AI Model

When presenting tools to an AI model, the host collects tools from all servers and converts them to the model's expected format:

```python
def get_tools_for_claude(self) -> list[dict]:
    """Convert MCP tools to Claude API format."""
    claude_tools = []
    for tool in self.get_all_tools():
        claude_tools.append({
            "name": tool.name,
            "description": tool.description or "",
            "input_schema": tool.inputSchema
        })
    return claude_tools
```

---

## 12.5 Handling Sampling Requests from Servers

When an MCP server sends a `sampling/createMessage` request, the client must forward it to the host, which sends it to the AI model. Here is how to handle sampling:

```python
from mcp.types import CreateMessageRequest, CreateMessageResult

# Set up sampling handler on the client session
async def handle_sampling_request(request: CreateMessageRequest) -> CreateMessageResult:
    """Handle a sampling request from the server."""
    import anthropic

    client = anthropic.Anthropic()

    # Convert MCP messages to Claude API format
    messages = [
        {"role": msg.role, "content": msg.content.text}
        for msg in request.messages
    ]

    response = client.messages.create(
        model=request.modelPreferences.hints[0].name if request.modelPreferences else "claude-sonnet-4-5-20250929",
        max_tokens=request.maxTokens,
        messages=messages
    )

    return CreateMessageResult(
        role="assistant",
        content={"type": "text", "text": response.content[0].text},
        model=response.model
    )

# Register the handler with the session
session.sampling_handler = handle_sampling_request
```

---

## 12.6 Client-Side Error Handling and Reconnection

### Error Handling

```python
from mcp.types import McpError

async def safe_call_tool(session, name, arguments):
    try:
        result = await session.call_tool(name, arguments)
        if result.isError:
            return None, f"Tool error: {result.content[0].text}"
        return result.content[0].text, None
    except McpError as e:
        return None, f"MCP error: {e.message} (code: {e.code})"
    except ConnectionError:
        return None, "Server connection lost"
    except Exception as e:
        return None, f"Unexpected error: {e}"
```

### Reconnection Strategy

```python
import asyncio

async def connect_with_retry(params, max_retries=3, base_delay=1.0):
    """Connect to an MCP server with exponential backoff."""
    for attempt in range(max_retries):
        try:
            read, write = await create_stdio_connection(params)
            session = ClientSession(read, write)
            await session.initialize()
            return session
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            print(f"Connection failed (attempt {attempt + 1}), retrying in {delay}s: {e}")
            await asyncio.sleep(delay)
```

---

## Summary

Building MCP clients gives you the other side of the protocol — the ability to connect to servers, discover capabilities, and invoke tools programmatically.

Key takeaways:

- **TypeScript `Client`** and **Python `ClientSession`** are the primary client classes
- **Transport options** mirror the server side: stdio, SSE, Streamable HTTP
- **Host applications** manage multiple client connections and route tool calls to the right server
- **Tool aggregation** collects tools from all servers into a unified list for the AI model
- **Sampling handlers** let the host respond to server-initiated AI completion requests
- **Error handling** should distinguish between protocol errors, tool errors, and connection errors
- **Reconnection** with exponential backoff provides resilience against transient failures

This concludes Part III: Building MCP Servers. You now have the practical skills to build both servers and clients in Python and TypeScript. In Part IV, we will explore advanced features — sampling, roots, logging, security, and deployment.
