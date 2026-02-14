# Chapter 17: Understanding AI Agents

---

## 17.1 What Is an AI Agent?

An AI agent is an AI system that can **autonomously perceive its environment, reason about goals, take actions, and learn from outcomes**. Unlike a simple chatbot that responds to prompts, an agent pursues objectives over multiple steps, making decisions along the way about what actions to take and how to adapt when things do not go as expected.

The defining characteristics of an agent are:

1. **Autonomy**: The agent makes decisions without human intervention for each step
2. **Tool use**: The agent can interact with external systems through tools
3. **Reasoning**: The agent plans multi-step approaches to solve problems
4. **Observation**: The agent examines the results of its actions and adapts
5. **Persistence**: The agent continues working until it achieves its goal or determines it cannot

An AI agent is built on top of a large language model, but it is more than just the model. The model provides the reasoning and language understanding; the agent framework provides the structure — the loop, the tools, the memory, and the decision-making scaffolding.

---

## 17.2 Agent vs. Chatbot vs. Assistant vs. Copilot

These terms are often used loosely, but they describe meaningfully different system architectures:

| System | Interaction | Autonomy | Actions | Multi-step |
|--------|------------|----------|---------|------------|
| **Chatbot** | Respond to messages | None | None | No |
| **Assistant** | Answer questions, with tools | Low | Limited, human-approved | Limited |
| **Copilot** | Suggest actions alongside human | Medium | Suggestions, human executes | Yes |
| **Agent** | Pursue goals autonomously | High | Executes actions directly | Yes |

**Chatbot**: Responds to individual messages. No tool use, no memory beyond the conversation, no autonomous action. Example: a basic customer service chat.

**Assistant**: Has access to tools but uses them conservatively, often with human approval for each action. Example: Claude Desktop with MCP tools, where the user approves each tool call.

**Copilot**: Works alongside a human, suggesting actions and drafts. The human retains control and makes final decisions. Example: GitHub Copilot suggesting code completions.

**Agent**: Given a goal, works autonomously through multiple steps, invoking tools, handling errors, and adapting its approach without waiting for human input at each step. Example: Claude Code operating in autonomous mode, writing code, running tests, fixing errors, and committing.

MCP is the protocol that powers tool use across all of these system types. But it truly shines in the agent paradigm, where the AI's ability to chain tool calls and react to results enables complex, multi-step workflows.

---

## 17.3 The Agent Loop: Perceive → Think → Act → Observe

Every AI agent follows a fundamental loop:

```
┌──────────────────────────────────────────────┐
│                                              │
│  ┌───────────┐    ┌───────────┐              │
│  │ PERCEIVE  │───→│   THINK   │              │
│  │           │    │           │              │
│  │ Read tools│    │ Plan next │              │
│  │ results,  │    │ step,     │              │
│  │ context   │    │ select    │              │
│  │           │    │ tool      │              │
│  └───────────┘    └─────┬─────┘              │
│       ▲                 │                    │
│       │                 ▼                    │
│  ┌────┴──────┐    ┌───────────┐              │
│  │  OBSERVE  │←───│    ACT    │              │
│  │           │    │           │              │
│  │ Examine   │    │ Call tool,│              │
│  │ results,  │    │ execute   │              │
│  │ errors    │    │ action    │              │
│  └───────────┘    └───────────┘              │
│                                              │
│              ┌───────────┐                   │
│              │   DONE?   │                   │
│              │           │──→ YES → Return   │
│              │           │                   │
│              └─────┬─────┘                   │
│                    │ NO                      │
│                    └────────→ Continue loop   │
└──────────────────────────────────────────────┘
```

1. **Perceive**: The agent takes in information — the user's goal, tool results from previous steps, error messages, conversation context.

2. **Think**: The AI model reasons about what to do next. This is where the LLM's intelligence is applied — analyzing the situation, planning the next step, selecting which tool to use and with what arguments.

3. **Act**: The agent executes the chosen action — calling an MCP tool, reading a resource, sending a message.

4. **Observe**: The agent examines the result of its action. Did it succeed? Did it produce the expected output? Does the agent need to adjust its approach?

5. **Done?**: The agent decides whether its goal has been achieved. If yes, it returns the final result. If no, it loops back to Think with the new information.

This loop continues until the goal is achieved, an unrecoverable error occurs, or a maximum iteration limit is reached.

---

## 17.4 Demystifying the Agent: It Is One Model, Not Two

A common misconception when first encountering agents is that the "agent" is a separate AI model — a second brain sitting between the user and the tools. It is not. An agent is **one AI model called repeatedly by a simple code loop**.

Here is the complete agent, stripped to its essence:

```python
messages = [{"role": "user", "content": user_goal}]

while True:
    # Call the ONE model
    response = claude.call(messages, tools=mcp_tools)

    if response.wants_to_use_tool:
        # Execute tool via MCP (this is just regular code, not AI)
        result = mcp_client.call_tool(response.tool_name, response.tool_args)

        # Add both the model's request and the tool result to the conversation
        messages.append(response)
        messages.append(tool_result)
        # Loop back — call the SAME model again with the updated conversation

    else:
        # Model is done — return the answer to the user
        print(response.text)
        break
```

That is the entire agent. Three components, only one of which is AI:

| Component | What it is | AI? |
|-----------|-----------|-----|
| The `while` loop | Regular code (Python/TypeScript) | No |
| Claude API calls | The one AI model, called multiple times | Yes |
| MCP tool execution | Regular code calling MCP servers | No |

The "intelligence" comes entirely from the model. The loop is just plumbing — it takes the model's output, executes any requested tools, and feeds the results back. The model does not change between calls. It is the same Claude, called again and again with a growing conversation that includes all previous tool results.

### A Concrete Walkthrough

Suppose you ask an agent: *"How many Python files are in this project?"*

| Step | Who runs | What happens |
|------|----------|-------------|
| 1 | `while` loop (code) | Sends your message to Claude API |
| 2 | Claude (model, call #1) | Responds: *"I'll use Bash to count them"* + tool request |
| 3 | `while` loop (code) | Sees tool request → calls MCP → runs `find . -name "*.py" | wc -l` |
| 4 | `while` loop (code) | Adds tool result ("29") to conversation, loops back |
| 5 | Claude (model, call #2) | Responds: *"There are 29 Python files in this project."* |
| 6 | `while` loop (code) | No tool request → shows answer to user, exits loop |

Steps 2 and 5 are the **same model** — Claude. It was called twice, but the second call had more context (the tool result). The loop itself made zero decisions — it just followed a simple rule: "if the model asked for a tool, execute it and call the model again."

### Why This Matters

Understanding that the agent is one model in a loop has practical implications:

- **There is no "agent intelligence" separate from the model.** If the model makes a bad tool choice, the loop cannot fix it. The quality of the agent is the quality of the model.
- **The conversation grows with each iteration.** Every tool call adds messages to the context window. Long agent runs can exhaust the context.
- **The loop is cheap; the model calls are expensive.** Each iteration costs an API call. The `while` loop and MCP calls are nearly free by comparison.
- **You can build an agent in 20 lines of code.** There is no magic. The power comes from the model's reasoning, not from the loop's structure.

---

## 17.5 Subagents: Agents That Spawn Agents

Sometimes an agent encounters a subtask that is complex enough to warrant its own focused effort — with its own context window, possibly its own model, and its own set of tools. This is a **subagent**.

A subagent is structurally identical to the main agent — it is the same pattern: a loop calling a model with tools. The differences are organizational, not architectural:

| Aspect | Main Agent | Subagent |
|--------|-----------|----------|
| Started by | The user | The parent agent |
| Receives task from | The user | The parent agent |
| Returns result to | The user | The parent agent |
| Model | Could be the most capable (e.g., Opus) | Could be cheaper/faster (e.g., Haiku) |
| Context window | Shared with the full conversation | Fresh, isolated — only the subtask |
| Tools available | All tools | Possibly a subset |
| Lifetime | Entire session | Just the subtask |

```
User: "Refactor the authentication module and update the tests"
  │
  ▼
┌──────────────────────────────────────────────────┐
│ Main Agent (while loop + Claude Opus)            │
│                                                  │
│  Thinks: "This has two parts. Let me delegate    │
│          the research to a subagent while I      │
│          plan the refactoring."                  │
│         │                                        │
│         ▼                                        │
│  ┌─────────────────────────────────────────┐     │
│  │ Subagent (while loop + Claude Haiku)    │     │
│  │                                         │     │
│  │ Task: "Find all files that import from  │     │
│  │        the auth module and list them"   │     │
│  │                                         │     │
│  │ Uses: Grep tool, Read tool              │     │
│  │ Returns: "Found 12 files: ..."          │     │
│  └────────────────────┬────────────────────┘     │
│                       │                          │
│  Receives result, continues with full context    │
│  Now writes the refactored code...               │
└──────────────────────────────────────────────────┘
```

### Why Use Subagents?

**Context window isolation.** The main agent might be deep in a complex conversation. Spawning a subagent gives it a clean context window focused solely on the subtask. The subagent's intermediate steps (tool calls, partial results, dead ends) do not clutter the main agent's context.

**Model cost optimization.** A simple research task (searching files, reading documentation) does not need the most expensive model. The main agent can use Opus for complex reasoning while delegating simple tasks to Haiku, saving cost and improving speed.

**Parallelism.** Multiple subagents can work on independent subtasks simultaneously. The main agent does not need to wait for one search to complete before starting another.

### Subagents in Practice: Claude Code

Claude Code uses subagents extensively. When you see the `Task` tool being invoked, that is the main agent spawning a subagent:

- **Explore subagent**: Uses a fast model to search the codebase — grep, glob, read files — and returns a summary
- **Plan subagent**: Analyzes a task and produces an implementation plan
- **Bash subagent**: Runs commands and interprets results

Each subagent is the same pattern — a `while` loop calling a model with MCP tools. The only differences are the model choice, the available tools, and the fact that the result flows back to the parent agent instead of to the user.

### The Key Insight

An agent, a subagent, and the main loop are all the **same architecture**:

```python
while True:
    response = model.call(messages, tools)
    if response.wants_tool:
        result = execute_tool(response)
        messages.append(result)
    else:
        return response.text
```

The difference is only in **who starts it** and **who receives the result**. A main agent is started by the user and returns to the user. A subagent is started by another agent and returns to that agent. The code is the same.

---

## 17.6 Tool Use as the Foundation of Agency (MCP's Role)

Without tools, an AI model can only generate text. With tools, it can interact with the world. This is why tool use is the foundation of agency — tools are what transform reasoning into action.

MCP provides the standard protocol for this tool use. An agent's capabilities are defined by the MCP servers it is connected to:

- Connect a file system server → the agent can read and write files
- Connect a GitHub server → the agent can create issues, review PRs, manage repositories
- Connect a database server → the agent can query and analyze data
- Connect a web search server → the agent can research current information
- Connect a deployment server → the agent can deploy and manage services

The more tools an agent has access to, the more capable it becomes. But there is a tradeoff — more tools also means more decisions for the AI to make, more potential for errors, and more security surface area.

---

## 17.7 Memory and State in Agents

Agents need memory to function effectively across multiple steps.

### 17.7.1 Short-Term Memory (Context Window)

The most basic form of agent memory is the AI model's context window — the conversation history that includes all previous messages, tool calls, and results. This is "short-term" because it is limited by the context window size and is lost when the conversation ends.

Short-term memory enables:
- Referring to previous tool results ("use the data from the query I just ran")
- Building on previous reasoning ("now that I know the schema, I can write the query")
- Error recovery ("the last attempt failed, let me try a different approach")

The limitation: context windows are finite. As the agent makes more tool calls, the context grows, and eventually the oldest information must be compressed or dropped.

### 17.7.2 Long-Term Memory (External Storage)

For persistent memory across sessions, agents use external storage:

- **MCP resources**: A memory server that stores and retrieves key-value data
- **File-based memory**: Writing notes and findings to files
- **Database memory**: Storing structured data in a database
- **Vector databases**: Storing embeddings for semantic retrieval

```python
# Example: A memory MCP server
@mcp.tool()
async def remember(key: str, value: str) -> str:
    """Store information for later retrieval."""
    memory_store[key] = value
    return f"Remembered: {key}"

@mcp.tool()
async def recall(key: str) -> str:
    """Retrieve previously stored information."""
    if key in memory_store:
        return memory_store[key]
    return f"No memory found for: {key}"

@mcp.resource("memory://all")
async def get_all_memories() -> str:
    """All stored memories."""
    return json.dumps(memory_store, indent=2)
```

---

## 17.8 Planning and Reasoning Strategies

Agents use various strategies to plan their approach:

**Direct execution**: For simple tasks, the agent acts immediately without explicit planning. "Read file X" → read_file(X) → return contents.

**Sequential planning**: For multi-step tasks, the agent plans a sequence of steps: "First I'll list the tables, then examine each schema, then write the query."

**Iterative refinement**: The agent takes an action, evaluates the result, and adjusts: "That query returned too many results, let me add a filter."

**Backtracking**: When an approach fails, the agent tries alternatives: "The file isn't in /src, let me search in /lib."

**Decomposition**: The agent breaks a complex task into subtasks: "To deploy this feature, I need to: 1) write the code, 2) write tests, 3) run tests, 4) commit, 5) deploy."

Modern LLMs perform these strategies naturally as part of their reasoning. The agent framework's job is to provide the structure — the loop, the tools, the memory — that allows the LLM to exercise these strategies effectively.

---

## 17.9 How MCP Enables Agent Architectures

MCP enables agent architectures in several key ways:

1. **Standardized tool access**: Agents can use any MCP server without custom integration code
2. **Dynamic capability discovery**: Agents discover available tools at runtime, adapting to their environment
3. **Composable capabilities**: Multiple MCP servers can be combined to create rich agent environments
4. **Bidirectional AI access**: Through sampling, MCP servers can leverage the AI model for sub-tasks
5. **Security controls**: MCP's capability negotiation and human-in-the-loop patterns provide safety guardrails for autonomous agents
6. **Portable configurations**: An agent's tool configuration can be shared and reproduced across different deployments

MCP does not prescribe how agents should be built — it provides the protocol layer that agents use to interact with the world. The agent's reasoning, planning, and decision-making happen in the AI model and the agent framework. MCP is the bridge between the agent's decisions and the real-world actions.

---

## Summary

AI agents represent the highest level of AI autonomy — systems that can perceive, reason, act, and adapt in pursuit of goals. MCP is the protocol that connects these agents to the real world through tools, resources, and prompts.

Key takeaways:

- **Agents** are autonomous AI systems that pursue goals through multi-step tool use
- **The agent loop** (perceive → think → act → observe) is the fundamental execution model
- **Tool use is the foundation** — agents' capabilities are defined by their tools
- **Memory** comes in two forms: short-term (context window) and long-term (external storage)
- **Planning strategies** (direct, sequential, iterative, backtracking, decomposition) are exercised by the LLM
- **MCP enables agents** through standardized tool access, dynamic discovery, composability, and security controls

In the next chapter, we will build agents that use MCP — from simple single-purpose agents to sophisticated systems using the Anthropic Agent SDK.
