# Chapter 22: Testing MCP Servers and Agents

---

## 22.1 Unit Testing Tool Handlers

Tool handlers are regular async functions, making them straightforward to unit test:

```python
import pytest
import pytest_asyncio
from server import mcp  # Import your FastMCP server

@pytest.mark.asyncio
async def test_add_tool():
    """Test the add tool directly."""
    # Call the underlying function
    result = await mcp._tool_handlers["add"](a=2, b=3)
    assert result == "5"

@pytest.mark.asyncio
async def test_query_validation():
    """Test that non-SELECT queries are rejected."""
    result = await mcp._tool_handlers["query"](sql="DROP TABLE users")
    assert "Error" in result
    assert "SELECT" in result

@pytest.mark.asyncio
async def test_search_no_results():
    """Test search with no matches."""
    result = await mcp._tool_handlers["search_files"](
        pattern="*.nonexistent",
        directory="/tmp"
    )
    assert "No files found" in result
```

For tools that depend on external services, use mocking:

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_github_list_issues():
    mock_response = AsyncMock()
    mock_response.json.return_value = [
        {"number": 1, "title": "Bug fix", "labels": []},
        {"number": 2, "title": "Feature request", "labels": [{"name": "enhancement"}]}
    ]
    mock_response.status_code = 200

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        result = await list_issues("owner", "repo")
        assert "#1" in result
        assert "#2" in result
        assert "enhancement" in result
```

---

## 22.2 Integration Testing with the MCP Inspector

The MCP Inspector is the official tool for interactive testing:

```bash
# Python server
mcp dev server.py

# TypeScript server
npx @modelcontextprotocol/inspector node dist/index.js
```

The Inspector provides:
- **Tool testing**: List tools, fill in arguments, execute, and see results
- **Resource testing**: Browse resources, read content
- **Prompt testing**: List prompts, fill arguments, see expanded messages
- **Message inspection**: View raw JSON-RPC messages between client and server
- **Notification monitoring**: See server notifications in real-time

### Automated Inspector Testing

You can also drive the Inspector programmatically for CI:

```python
import subprocess
import json

def test_server_starts():
    """Verify the server starts and responds to initialization."""
    proc = subprocess.Popen(
        ["python", "server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Send initialize request
    init_request = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"}
        }
    }) + "\n"

    proc.stdin.write(init_request.encode())
    proc.stdin.flush()

    # Read response
    response_line = proc.stdout.readline()
    response = json.loads(response_line)

    assert response["id"] == 1
    assert "result" in response
    assert "serverInfo" in response["result"]

    proc.terminate()
```

---

## 22.3 End-to-End Testing with a Client

Full end-to-end tests use the SDK's client:

```python
import pytest
import pytest_asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

@pytest_asyncio.fixture
async def mcp_session():
    """Create a connected MCP session for testing."""
    params = StdioServerParameters(
        command="python",
        args=["server.py"],
        env={"DB_PATH": "test.db"}
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session

@pytest.mark.asyncio
async def test_list_tools(mcp_session):
    result = await mcp_session.list_tools()
    tool_names = [t.name for t in result.tools]
    assert "query" in tool_names
    assert "list_tables" in tool_names

@pytest.mark.asyncio
async def test_tool_call(mcp_session):
    result = await mcp_session.call_tool("list_tables", {})
    assert not result.isError
    assert "users" in result.content[0].text

@pytest.mark.asyncio
async def test_resource_read(mcp_session):
    result = await mcp_session.read_resource("db://schema")
    assert result.contents[0].mimeType == "application/json"
    content = json.loads(result.contents[0].text)
    assert "tables" in content

@pytest.mark.asyncio
async def test_tool_error_handling(mcp_session):
    result = await mcp_session.call_tool(
        "query",
        {"sql": "SELECT * FROM nonexistent_table"}
    )
    assert result.isError
    assert "Error" in result.content[0].text
```

---

## 22.4 Mocking MCP Servers for Agent Testing

When testing agents, mock the MCP server to control tool results:

```python
class MockMCPSession:
    """Mock MCP session for agent testing."""

    def __init__(self):
        self.tool_calls = []
        self.mock_results = {}

    async def initialize(self):
        pass

    async def list_tools(self):
        from types import SimpleNamespace
        return SimpleNamespace(tools=[
            SimpleNamespace(
                name="search",
                description="Search the web",
                inputSchema={"type": "object", "properties": {"query": {"type": "string"}}}
            )
        ])

    async def call_tool(self, name: str, arguments: dict):
        self.tool_calls.append({"name": name, "arguments": arguments})
        from types import SimpleNamespace

        if name in self.mock_results:
            return SimpleNamespace(
                content=[SimpleNamespace(text=self.mock_results[name])],
                isError=False
            )
        return SimpleNamespace(
            content=[SimpleNamespace(text=f"Mock result for {name}")],
            isError=False
        )

# Test
async def test_agent_uses_search():
    mock = MockMCPSession()
    mock.mock_results["search"] = "Found 5 results about AI safety..."

    agent = MCPAgent(session=mock)
    result = await agent.run("Search for AI safety research")

    # Verify the agent called the search tool
    assert len(mock.tool_calls) > 0
    assert mock.tool_calls[0]["name"] == "search"
```

---

## 22.5 Load Testing and Performance Benchmarking

```python
import asyncio
import time

async def load_test(server_command, num_requests=100, concurrency=10):
    """Load test an MCP server."""

    async def single_request(session):
        start = time.time()
        result = await session.call_tool("query", {"sql": "SELECT 1"})
        elapsed = time.time() - start
        return elapsed, not result.isError

    params = StdioServerParameters(command="python", args=[server_command])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Warm up
            await session.call_tool("query", {"sql": "SELECT 1"})

            # Run load test
            semaphore = asyncio.Semaphore(concurrency)
            async def limited_request():
                async with semaphore:
                    return await single_request(session)

            tasks = [limited_request() for _ in range(num_requests)]
            results = await asyncio.gather(*tasks)

            latencies = [r[0] for r in results]
            successes = sum(1 for r in results if r[1])

            print(f"Requests: {num_requests}")
            print(f"Successes: {successes}/{num_requests}")
            print(f"Avg latency: {sum(latencies)/len(latencies)*1000:.1f}ms")
            print(f"P95 latency: {sorted(latencies)[int(0.95*len(latencies))]*1000:.1f}ms")
            print(f"Max latency: {max(latencies)*1000:.1f}ms")
```

---

## 22.6 Testing Security Properties

```python
@pytest.mark.asyncio
async def test_sql_injection_prevention(mcp_session):
    """Verify SQL injection is prevented."""
    malicious_queries = [
        "SELECT 1; DROP TABLE users",
        "SELECT * FROM users WHERE id = 1 OR 1=1",
        "'; DROP TABLE users; --",
        "DELETE FROM users",
        "INSERT INTO users VALUES ('hacker', 'hacker@evil.com')",
    ]
    for sql in malicious_queries:
        result = await mcp_session.call_tool("query", {"sql": sql})
        # Should either error or be safely handled
        assert result.isError or "Error" in result.content[0].text or "SELECT" in result.content[0].text

@pytest.mark.asyncio
async def test_path_traversal_prevention(mcp_session):
    """Verify path traversal is prevented."""
    malicious_paths = [
        "../../etc/passwd",
        "/etc/shadow",
        "../../../root/.ssh/id_rsa",
    ]
    for path in malicious_paths:
        result = await mcp_session.call_tool("read_file", {"path": path})
        assert result.isError or "denied" in result.content[0].text.lower()
```

---

## 22.7 Continuous Integration for MCP Projects

```yaml
# .github/workflows/test.yml
name: MCP Server Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -e ".[test]"

      - name: Run unit tests
        run: pytest tests/unit/ -v

      - name: Run integration tests
        run: pytest tests/integration/ -v

      - name: Run security tests
        run: pytest tests/security/ -v

      - name: Type checking
        run: mypy server.py
```

---

## Summary

Testing MCP servers requires a layered approach: unit tests for tool logic, integration tests with real protocol communication, and security tests for vulnerability prevention.

Key takeaways:

- **Unit test** tool handlers as regular async functions with mocking for external dependencies
- **The MCP Inspector** is invaluable for interactive testing during development
- **End-to-end tests** use the SDK client to test the full protocol flow
- **Mock MCP sessions** enable testing agents without running real servers
- **Load testing** reveals performance characteristics under concurrent usage
- **Security testing** should cover injection, path traversal, and authorization
- **CI pipelines** should run all test categories automatically
