# Chapter 19: Composite Agents — Multi-Agent Orchestration

---

## 19.1 Why Multi-Agent Systems?

A single agent with many tools can handle a wide range of tasks, but there are scenarios where a **multi-agent architecture** is superior:

- **Specialization**: Different agents can be optimized for different domains (coding, research, data analysis, communication)
- **Complexity management**: Breaking a complex task into sub-tasks handled by specialist agents is more manageable than one agent handling everything
- **Parallelism**: Multiple agents can work on independent sub-tasks simultaneously
- **Model selection**: Different agents can use different AI models — a fast, cheap model for simple tasks and a powerful, expensive model for complex reasoning
- **Resource isolation**: Each agent has its own context window, preventing one sub-task from consuming all available context
- **Modularity**: Agents can be developed, tested, and updated independently

---

## 19.2 Orchestration Patterns

### 19.2.1 The Manager Pattern (Central Orchestrator)

A central "manager" agent receives the task, decomposes it into sub-tasks, delegates each to a specialist agent, and synthesizes the results.

```
                    ┌─────────────────┐
                    │  Manager Agent  │
                    │                 │
                    │ Decompose task, │
                    │ delegate, and   │
                    │ synthesize      │
                    └────┬──┬──┬──────┘
                         │  │  │
              ┌──────────┘  │  └──────────┐
              ▼             ▼             ▼
        ┌───────────┐ ┌───────────┐ ┌───────────┐
        │ Research  │ │  Coding   │ │  Review   │
        │  Agent    │ │  Agent    │ │  Agent    │
        └───────────┘ └───────────┘ └───────────┘
```

This is the most common pattern. It is clear, controllable, and easy to reason about.

### 19.2.2 The Pipeline Pattern (Sequential Handoff)

Agents form a pipeline where each agent processes the task and passes it to the next.

```
User Request → Agent A → Agent B → Agent C → Final Result
               (Research) (Draft)   (Review)
```

Each agent in the pipeline receives the output of the previous agent and contributes its expertise. This is natural for workflows with clear sequential stages.

### 19.2.3 The Delegation Pattern (Agents as Tools)

One agent has other agents available as tools. When it encounters a sub-task that requires specialized expertise, it "calls" the specialist agent just like it would call any other tool.

```python
from agents import Agent, Runner

# Specialist agents
researcher = Agent(
    name="researcher",
    instructions="You are a research specialist. Search for information and provide thorough analysis.",
    tools=[web_search, read_documents]
)

coder = Agent(
    name="coder",
    instructions="You are an expert programmer. Write clean, tested code.",
    tools=[read_file, write_file, run_tests]
)

# Main agent with specialists as tools
main_agent = Agent(
    name="project-manager",
    instructions="Coordinate research and coding tasks. Delegate to specialists.",
    tools=[
        researcher.as_tool(
            tool_name="research",
            tool_description="Delegate research tasks to the research specialist"
        ),
        coder.as_tool(
            tool_name="code",
            tool_description="Delegate coding tasks to the coding specialist"
        )
    ]
)
```

### 19.2.4 The Collaborative Pattern (Peer-to-Peer)

Multiple agents work together as peers, each contributing their expertise. They share a common workspace (through shared MCP resources) and communicate through a shared state.

This pattern is more complex and less common, but it can be effective for tasks that require genuine collaboration rather than delegation.

---

## 19.3 Implementing an Orchestrator Agent

### 19.3.1 Defining Sub-Agents

```python
from agents import Agent

# Define specialized agents
data_analyst = Agent(
    name="data-analyst",
    instructions="""You are a data analysis specialist.
    You can query databases, process data, and generate insights.
    Always provide statistical evidence for your conclusions.""",
    model="claude-sonnet-4-5-20250929",
    tools=[query_db, describe_table, list_tables]
)

report_writer = Agent(
    name="report-writer",
    instructions="""You are an expert report writer.
    You transform raw data and analysis into clear, structured reports.
    Use proper formatting, charts descriptions, and executive summaries.""",
    model="claude-sonnet-4-5-20250929",
    tools=[write_file, read_file]
)

code_reviewer = Agent(
    name="code-reviewer",
    instructions="""You are a senior code reviewer.
    You identify bugs, security issues, and style problems.
    Provide actionable feedback with code examples.""",
    model="claude-sonnet-4-5-20250929",
    tools=[read_file, search_files]
)
```

### 19.3.2 Routing Tasks to Specialists

```python
orchestrator = Agent(
    name="orchestrator",
    instructions="""You are a project orchestrator. Your job is to:
    1. Understand the user's request
    2. Break it into sub-tasks
    3. Delegate each sub-task to the appropriate specialist
    4. Synthesize the results into a cohesive response

    Available specialists:
    - data_analyst: For database queries and data analysis
    - report_writer: For creating formatted reports
    - code_reviewer: For reviewing code quality

    Delegate efficiently — use the right specialist for each sub-task.""",
    tools=[
        data_analyst.as_tool("analyze_data", "Send a data analysis task to the specialist"),
        report_writer.as_tool("write_report", "Send a report writing task to the specialist"),
        code_reviewer.as_tool("review_code", "Send a code review task to the specialist"),
    ]
)
```

### 19.3.3 Aggregating Results

The orchestrator naturally aggregates results through its conversation flow. Each specialist returns results that the orchestrator incorporates into its reasoning:

```
User: "Analyze our Q4 revenue data and produce an executive report"

Orchestrator thinks: I need to:
1. Have the data analyst query and analyze revenue data
2. Have the report writer format the findings

Orchestrator → data_analyst: "Query the revenue table for Q4 data.
    Calculate totals by product line, month-over-month growth,
    and identify top performers."

data_analyst → Orchestrator: "Q4 revenue was $12.3M, up 15% from Q3.
    Product A led with $5.1M..."

Orchestrator → report_writer: "Create an executive report with
    these findings: [data analyst's results]"

report_writer → Orchestrator: "Report saved to /reports/q4-revenue.md"

Orchestrator → User: "I've analyzed the Q4 revenue data and produced
    an executive report. Key findings: ..."
```

### 19.3.4 Handling Failures and Fallbacks

```python
orchestrator = Agent(
    name="resilient-orchestrator",
    instructions="""You are a project orchestrator.

    Error handling guidelines:
    - If a specialist fails, try to rephrase the task or break it down further
    - If a specialist is unavailable, attempt the task yourself using basic tools
    - Always inform the user if a sub-task could not be completed
    - Never silently swallow errors — report them clearly

    Fallback strategy:
    1. Try the specialist agent
    2. If it fails, retry with a simplified request
    3. If it still fails, attempt the task yourself
    4. If you cannot complete it, report what you accomplished and what remains""",
    tools=[...]
)
```

---

## 19.4 Inter-Agent Communication via MCP

MCP can serve as the communication layer between agents. There are several patterns:

### 19.4.1 Agents as MCP Servers

An agent can expose itself as an MCP server, allowing other agents (or hosts) to invoke it through the standard MCP protocol:

```python
from mcp.server.fastmcp import FastMCP

# Agent wrapped as an MCP server
agent_server = FastMCP("research-agent-server")

@agent_server.tool()
async def research(topic: str, depth: str = "normal") -> str:
    """Conduct research on a topic.

    Args:
        topic: The topic to research
        depth: Research depth - "quick", "normal", or "thorough"
    """
    # This tool internally runs an agent
    agent = create_research_agent(depth=depth)
    result = await agent.run(f"Research: {topic}")
    return result

if __name__ == "__main__":
    agent_server.run()
```

### 19.4.2 Agents as MCP Clients

An agent can connect to other agent-servers as MCP clients:

```python
class OrchestratorAgent:
    async def setup(self):
        # Connect to specialist agents via MCP
        self.research = await self.connect_mcp("python", ["research_agent.py"])
        self.coding = await self.connect_mcp("python", ["coding_agent.py"])

    async def run(self, task: str):
        # Use specialist agents through MCP tool calls
        research = await self.research.call_tool("research", {"topic": task})
        code = await self.coding.call_tool("implement", {"spec": research})
        return code
```

### 19.4.3 Bidirectional Agent Communication

Using sampling, agents can create truly bidirectional communication. An agent-server can use sampling to ask the host's AI for clarification or additional reasoning:

```python
@agent_server.tool()
async def collaborative_analysis(data: str, ctx: Context) -> str:
    """Analyze data collaboratively with the host AI."""

    # Do initial analysis
    initial_analysis = await analyze(data)

    # Ask the host AI for its perspective via sampling
    host_perspective = await ctx.session.create_message(
        messages=[{
            "role": "user",
            "content": {
                "type": "text",
                "text": f"I analyzed this data and found: {initial_analysis}\n\nDo you see any additional patterns or concerns?"
            }
        }],
        max_tokens=1000
    )

    # Combine perspectives
    combined = f"My analysis: {initial_analysis}\n\nAdditional insights: {host_perspective.content.text}"
    return combined
```

---

## 19.5 State Sharing Between Agents

Agents in a multi-agent system often need to share state. MCP provides natural mechanisms:

**Shared MCP resources**: A shared server that agents can both read from and write to:

```python
# Shared state server
state_server = FastMCP("shared-state")
shared_data = {}

@state_server.tool()
async def set_state(key: str, value: str) -> str:
    """Set a shared state value."""
    shared_data[key] = value
    return f"Set {key}"

@state_server.resource("state://{key}")
async def get_state(key: str) -> str:
    """Read a shared state value."""
    return shared_data.get(key, "")

@state_server.resource("state://all")
async def get_all_state() -> str:
    """Read all shared state."""
    return json.dumps(shared_data, indent=2)
```

**Shared file system**: Agents write intermediate results to files that other agents can read.

**Shared database**: Agents read and write to a shared database for structured state.

---

## 19.6 Using Handoffs in the Agent SDK

The Anthropic Agent SDK provides a **handoff** mechanism for transferring control between agents:

```python
from agents import Agent, handoff

# Define agents
triage = Agent(
    name="triage",
    instructions="Determine the type of request and hand off to the appropriate specialist.",
    handoffs=[
        handoff(
            agent=data_analyst,
            tool_name="transfer_to_data_analyst",
            tool_description="Transfer the conversation to the data analysis specialist"
        ),
        handoff(
            agent=coder,
            tool_name="transfer_to_coder",
            tool_description="Transfer the conversation to the coding specialist"
        ),
    ]
)

# When triage calls transfer_to_data_analyst,
# the conversation is handed off to data_analyst
# which continues with its own tools and instructions
```

Handoffs transfer the full conversation context to the target agent, allowing it to continue where the previous agent left off. This is different from delegation (where the orchestrator calls an agent as a tool) — in a handoff, the target agent takes over completely.

---

## 19.7 Complete Example: A Composite Agent System

```python
"""
A composite agent system for software development tasks.

Architecture:
- Orchestrator: Coordinates the overall task
- Researcher: Gathers information and context
- Developer: Writes code
- Reviewer: Reviews code quality
- Tester: Runs and validates tests
"""

from agents import Agent, Runner

# ─── Specialist Agents ────────────────────────

researcher = Agent(
    name="researcher",
    instructions="""You research codebases and gather context.
    Use file reading and search tools to understand existing code.
    Provide comprehensive summaries of relevant code and patterns.""",
    tools=[read_file, search_files, list_directory, query_db]
)

developer = Agent(
    name="developer",
    instructions="""You write high-quality code.
    Follow existing patterns in the codebase.
    Write clean, tested, documented code.
    Consider edge cases and error handling.""",
    tools=[read_file, write_file, search_files]
)

reviewer = Agent(
    name="reviewer",
    instructions="""You review code for quality, security, and correctness.
    Check for: bugs, security issues, performance problems, style violations.
    Provide specific, actionable feedback.""",
    tools=[read_file, search_files]
)

tester = Agent(
    name="tester",
    instructions="""You write and run tests.
    Ensure comprehensive coverage of happy paths, edge cases, and error cases.
    Fix any failing tests.""",
    tools=[read_file, write_file, run_command]
)

# ─── Orchestrator ────────────────────────────

orchestrator = Agent(
    name="tech-lead",
    instructions="""You are a tech lead coordinating a software development team.

    For any development task:
    1. First, delegate research to understand the codebase context
    2. Then, delegate coding with clear specifications
    3. Then, delegate code review
    4. Finally, delegate testing
    5. Iterate if the reviewer or tester finds issues

    Always ensure quality before marking a task complete.""",
    tools=[
        researcher.as_tool("research", "Research codebase context"),
        developer.as_tool("develop", "Write or modify code"),
        reviewer.as_tool("review", "Review code quality"),
        tester.as_tool("test", "Write and run tests"),
    ]
)

# ─── Run ─────────────────────────────────────

async def develop_feature(description: str) -> str:
    result = await Runner.run(
        orchestrator,
        f"Implement the following feature: {description}"
    )
    return result.final_output
```

---

## Summary

Multi-agent systems distribute complex tasks across specialized agents, enabling better quality, parallelism, and maintainability.

Key takeaways:

- **Orchestration patterns** include Manager (central coordinator), Pipeline (sequential), Delegation (agents as tools), and Collaborative (peer-to-peer)
- **The Manager pattern** is most common — one agent decomposes tasks and delegates to specialists
- **Agents as MCP servers** allow agents to be accessed through the standard protocol
- **Sampling enables bidirectional communication** between agent-servers and the host
- **State sharing** via shared MCP resources, files, or databases enables inter-agent coordination
- **Handoffs** transfer full conversation control from one agent to another
- **Error handling** in multi-agent systems requires retry strategies and fallback plans

In the next chapter, we will explore agent capabilities in depth — how agents acquire knowledge, whether they can learn, and how knowledge is packaged and deployed.
