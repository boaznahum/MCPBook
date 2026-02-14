# Chapter 18: Building Agents with MCP

---

## 18.1 The Minimal Agent: An LLM + MCP Client Loop

At its core, an agent is surprisingly simple to build. You need three components:

1. An AI model API (e.g., Claude API)
2. An MCP client connected to one or more servers
3. A loop that runs until the task is complete

```python
# The simplest possible agent
async def simple_agent(goal: str, mcp_session, ai_client):
    messages = [{"role": "user", "content": goal}]

    while True:
        # Send messages to AI, including available tools
        response = ai_client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
            tools=get_tools_from_mcp(mcp_session),
            messages=messages
        )

        # Check if the AI wants to use a tool
        if response.stop_reason == "tool_use":
            # Execute each tool call
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await mcp_session.call_tool(
                        block.name, block.input
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result.content[0].text
                    })

            # Add assistant message and tool results to conversation
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            # AI is done — return the final response
            return response.content[0].text
```

This is the essence of an agent: a loop that alternates between AI reasoning and tool execution until the AI decides it has finished.

---

## 18.2 Building an Agent from Scratch

Let us build a complete, functional agent in Python.

### 18.2.1 The Core Loop: Query → Tool Selection → Execution → Response

```python
import asyncio
import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPAgent:
    """A complete AI agent powered by Claude and MCP."""

    def __init__(self, model: str = "claude-sonnet-4-5-20250929", max_turns: int = 20):
        self.model = model
        self.max_turns = max_turns
        self.ai_client = anthropic.Anthropic()
        self.sessions: list[ClientSession] = []
        self.tools: list[dict] = []
        self._tool_to_session: dict[str, ClientSession] = {}

    async def connect_server(self, command: str, args: list[str] = None):
        """Connect to an MCP server."""
        params = StdioServerParameters(command=command, args=args or [])
        read, write = await self._open_stdio(params)
        session = ClientSession(read, write)
        await session.__aenter__()
        await session.initialize()

        # Discover tools
        result = await session.list_tools()
        for tool in result.tools:
            tool_def = {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.inputSchema
            }
            self.tools.append(tool_def)
            self._tool_to_session[tool.name] = session

        self.sessions.append(session)

    async def run(self, goal: str) -> str:
        """Run the agent with a given goal."""
        messages = [{"role": "user", "content": goal}]

        for turn in range(self.max_turns):
            # Call the AI model
            response = self.ai_client.messages.create(
                model=self.model,
                max_tokens=8192,
                tools=self.tools,
                messages=messages
            )

            # Add the assistant's response to the conversation
            messages.append({
                "role": "assistant",
                "content": response.content
            })

            # Check if we're done
            if response.stop_reason == "end_turn":
                # Extract final text response
                for block in response.content:
                    if hasattr(block, "text"):
                        return block.text
                return "Task completed."

            # Process tool calls
            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = await self._execute_tool(
                            block.name, block.input
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result
                        })

                messages.append({
                    "role": "user",
                    "content": tool_results
                })

        return "Maximum turns reached without completion."

    async def _execute_tool(self, name: str, arguments: dict) -> str:
        """Execute a tool call through MCP."""
        session = self._tool_to_session.get(name)
        if not session:
            return f"Error: Unknown tool '{name}'"

        try:
            result = await session.call_tool(name, arguments)
            if result.isError:
                return f"Tool error: {result.content[0].text}"
            return result.content[0].text
        except Exception as e:
            return f"Error executing {name}: {e}"
```

### 18.2.2 Managing Conversation History

As the agent makes tool calls, the conversation history grows. Each tool call adds:
- The assistant's message (including the tool_use block)
- The tool result (as a user message)

For long-running agents, this can exceed the context window. Strategies include:

```python
def trim_conversation(messages: list, max_tokens: int) -> list:
    """Trim conversation to fit within token limit."""
    # Always keep the first message (the goal)
    # Always keep the last N messages
    # Summarize or remove middle messages

    if estimate_tokens(messages) <= max_tokens:
        return messages

    # Keep first and last messages, summarize middle
    first = messages[0]
    recent = messages[-10:]  # Keep last 10 messages

    summary = summarize_messages(messages[1:-10])
    summary_msg = {
        "role": "user",
        "content": f"[Previous conversation summary: {summary}]"
    }

    return [first, summary_msg] + recent
```

### 18.2.3 Deciding When to Stop

The agent stops when:

1. **The AI returns `end_turn`**: The model has generated a final response without requesting any tools
2. **Maximum turns reached**: A safety limit to prevent infinite loops
3. **Unrecoverable error**: A critical error that the agent cannot work around
4. **User cancellation**: The user explicitly stops the agent

---

## 18.3 Using the Anthropic Agent SDK

The Anthropic Agent SDK provides a higher-level framework for building agents. It handles the agent loop, tool execution, and orchestration patterns.

### 18.3.1 The `Agent` Class

```python
from agents import Agent, Runner

agent = Agent(
    name="research-agent",
    instructions="You are a research assistant. Use the available tools to find information and synthesize answers.",
    model="claude-sonnet-4-5-20250929",
    tools=[...]  # Tool definitions
)

# Run the agent
result = await Runner.run(agent, "What are the latest trends in AI safety?")
print(result.final_output)
```

### 18.3.2 Defining Agent Tools

The Agent SDK supports multiple tool types:

```python
from agents import Agent, function_tool

@function_tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression."""
    return str(eval(expression))

@function_tool
def get_current_time() -> str:
    """Get the current date and time."""
    from datetime import datetime
    return datetime.now().isoformat()

agent = Agent(
    name="calculator",
    instructions="You can perform calculations and check the time.",
    tools=[calculate, get_current_time]
)
```

### 18.3.3 Guardrails and Output Validation

The Agent SDK supports guardrails — checks that run before or after each step:

```python
from agents import Agent, GuardrailResult

async def check_safety(context, agent, input_text) -> GuardrailResult:
    """Guardrail that prevents unsafe operations."""
    unsafe_keywords = ["delete all", "drop table", "rm -rf"]
    for keyword in unsafe_keywords:
        if keyword.lower() in input_text.lower():
            return GuardrailResult(
                allow=False,
                message=f"Blocked: detected potentially unsafe operation '{keyword}'"
            )
    return GuardrailResult(allow=True)

agent = Agent(
    name="safe-agent",
    instructions="...",
    input_guardrails=[check_safety]
)
```

### 18.3.4 Tracing and Observability

The Agent SDK provides built-in tracing for monitoring agent behavior:

```python
from agents import Runner, trace

with trace("research-task"):
    result = await Runner.run(agent, "Analyze market trends for Q4")
    # Trace captures: all LLM calls, tool invocations, timing, token usage
```

---

## 18.4 Connecting an Agent to MCP Servers

Integrating MCP servers with an agent framework:

```python
from agents import Agent, Runner
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def create_mcp_agent():
    # Connect to MCP servers
    db_params = StdioServerParameters(command="python", args=["db_server.py"])
    fs_params = StdioServerParameters(command="python", args=["fs_server.py"])

    async with stdio_client(db_params) as (db_read, db_write):
        async with stdio_client(fs_params) as (fs_read, fs_write):
            db_session = ClientSession(db_read, db_write)
            fs_session = ClientSession(fs_read, fs_write)

            await db_session.initialize()
            await fs_session.initialize()

            # Collect tools from both servers
            db_tools = await db_session.list_tools()
            fs_tools = await fs_session.list_tools()

            # Convert MCP tools to agent tools
            all_tools = convert_mcp_tools(db_tools, fs_tools)

            agent = Agent(
                name="data-analyst",
                instructions="Analyze data using the database and file system tools.",
                tools=all_tools
            )

            result = await Runner.run(agent, "Find the top revenue customers and save a report")
            return result
```

---

## 18.5 Error Recovery and Retry Strategies

Robust agents handle errors gracefully:

```python
async def resilient_tool_call(session, name, arguments, max_retries=2):
    """Call a tool with retry logic."""
    for attempt in range(max_retries + 1):
        try:
            result = await session.call_tool(name, arguments)
            if not result.isError:
                return result.content[0].text

            error_msg = result.content[0].text
            if attempt < max_retries and is_retryable(error_msg):
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
            return f"Tool error after {attempt + 1} attempts: {error_msg}"

        except ConnectionError:
            if attempt < max_retries:
                await asyncio.sleep(2 ** attempt)
                continue
            return f"Connection error after {attempt + 1} attempts"

    return "Max retries exceeded"


def is_retryable(error: str) -> bool:
    """Determine if an error is likely transient."""
    retryable_patterns = ["timeout", "rate limit", "temporary", "connection"]
    return any(p in error.lower() for p in retryable_patterns)
```

---

## 18.6 Complete Example: A Research Agent with MCP

```python
"""
A research agent that can search the web, read files,
query databases, and produce a comprehensive report.
"""

import asyncio
import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def research_agent(question: str) -> str:
    """Run a research agent to answer a complex question."""

    # Connect to MCP servers
    servers = {
        "web": StdioServerParameters(command="python", args=["web_server.py"]),
        "files": StdioServerParameters(command="python", args=["file_server.py"]),
        "database": StdioServerParameters(command="python", args=["db_server.py"]),
    }

    agent = MCPAgent(model="claude-sonnet-4-5-20250929", max_turns=30)

    for name, params in servers.items():
        await agent.connect_server(params.command, params.args)

    # Run the agent with a research prompt
    prompt = f"""Research the following question thoroughly and produce a
comprehensive report.

Question: {question}

Instructions:
1. Search for relevant information using available tools
2. Cross-reference findings from multiple sources
3. Analyze data if databases are available
4. Structure your findings into a clear report
5. Include sources and confidence levels

Produce a well-structured report with sections, evidence, and conclusions."""

    return await agent.run(prompt)


# Run it
result = asyncio.run(research_agent(
    "What are the most effective strategies for reducing cloud infrastructure costs?"
))
print(result)
```

---

## Summary

Building agents with MCP follows a clear pattern: connect to servers, discover tools, and run the agent loop until the goal is achieved.

Key takeaways:

- **A minimal agent** is just an LLM + MCP client + loop — surprisingly simple to build
- **The core loop** alternates between AI reasoning and MCP tool execution
- **Conversation management** is critical — trim, summarize, and manage context as it grows
- **The Anthropic Agent SDK** provides higher-level abstractions: Agent class, guardrails, tracing
- **MCP integration** means connecting to servers, discovering tools, and routing tool calls
- **Error recovery** with retries and backoff makes agents more robust
- **Complete agents** can combine multiple MCP servers for rich, multi-capability workflows

In the next chapter, we will explore the most advanced agent pattern: composite agents that orchestrate other agents.
