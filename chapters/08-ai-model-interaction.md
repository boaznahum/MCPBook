# Chapter 8: How AI Models Interact with MCP

---

## 8.1 The AI Model's Perspective: What It Sees

An AI model does not directly interact with MCP servers. It never sends JSON-RPC messages, never opens transport connections, never negotiates capabilities. From the model's perspective, MCP is invisible — what it sees are **tools it can call** and **results from those calls**.

Here is what happens behind the scenes:

1. The host application connects to MCP servers and discovers their capabilities
2. The host translates MCP tool definitions into the AI model's native tool format
3. The host includes these tools in the API request to the AI model
4. The model decides whether to use a tool, and if so, which one and with what arguments
5. The host translates the model's tool use request into an MCP `tools/call` message
6. The host sends the result back to the model as a tool result

The model sees tools, not MCP. This is by design — the model should not need to understand the protocol. It should focus on understanding the user's intent and deciding which tools to use.

---

## 8.2 System Prompt Integration: How Tools/Resources/Prompts Appear

When a host connects to MCP servers and discovers tools, it needs to present them to the AI model. How this happens depends on the AI provider's API.

### Claude API (Anthropic)

In the Claude API, tools are passed in the `tools` parameter of the API request:

```python
import anthropic

client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=1024,
    tools=[
        {
            "name": "query_database",
            "description": "Execute a read-only SQL query against the PostgreSQL database",
            "input_schema": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "The SQL query to execute"
                    }
                },
                "required": ["sql"]
            }
        },
        {
            "name": "read_file",
            "description": "Read the contents of a file",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The file path to read"
                    }
                },
                "required": ["path"]
            }
        }
    ],
    messages=[
        {"role": "user", "content": "How many users signed up last month?"}
    ]
)
```

The host converts MCP tool definitions (with `inputSchema`) to Claude API tool format (with `input_schema`). The mapping is almost 1:1 — the field names differ slightly, but the JSON Schema structure is identical.

### Resources as Context

Resources are not directly exposed to the model as a separate concept. Instead, the host reads resource content and includes it in the conversation — either in the system prompt or as user messages:

```python
# Host reads MCP resources and includes them in the conversation
schema = await mcp_client.read_resource("db://main/schema")

response = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=1024,
    system=f"You have access to a database with the following schema:\n\n{schema}",
    tools=[...],
    messages=[
        {"role": "user", "content": "How many users signed up last month?"}
    ]
)
```

### Prompts as Message Sequences

MCP prompts expand into message sequences that the host inserts into the conversation:

```python
# Host retrieves an MCP prompt
prompt_result = await mcp_client.get_prompt("code_review", {"language": "python"})

# Insert the prompt's messages into the conversation
messages = []
for msg in prompt_result.messages:
    messages.append({"role": msg.role, "content": msg.content.text})

# Add the user's actual code
messages.append({"role": "user", "content": f"Here is the code to review:\n\n{code}"})

response = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=4096,
    messages=messages
)
```

---

## 8.3 The Decision Loop: When the AI Chooses to Use a Tool

The AI model decides to use a tool based on three factors:

1. **User intent**: What is the user trying to accomplish? Does it require external data or actions?
2. **Available tools**: What tools are available, and do any of them match the need?
3. **Tool descriptions**: Do the tool descriptions and parameter schemas suggest this tool is appropriate?

The model's decision process is roughly:

```
User message received
    ↓
Does answering require information I don't have?
    → YES → Is there a tool that can get this information?
        → YES → Use the tool
        → NO  → Ask the user or explain the limitation
    → NO  → Respond directly

Does answering require an action I can't perform?
    → YES → Is there a tool that can perform this action?
        → YES → Use the tool
        → NO  → Explain what needs to be done manually
    → NO  → Respond directly
```

The model's decision is influenced by:

- **Tool descriptions**: Clear, specific descriptions help the model understand when a tool is appropriate
- **Parameter schemas**: Well-defined schemas help the model construct valid arguments
- **Previous results**: If a tool call failed, the model may try a different approach
- **Conversation context**: The model considers the full conversation when deciding

### When the Model Should NOT Use a Tool

Models should avoid using tools when:

- They already have the information needed (from training data or conversation context)
- The tool does not match the user's request
- Using the tool would be unnecessarily risky or wasteful
- The user has explicitly asked the model not to use certain capabilities

Good tool descriptions help the model make these decisions. A description that says "Use this tool ONLY when you need to check real-time data" prevents the model from calling a tool for information it already knows.

---

## 8.4 Mapping AI Function Calls to MCP Tool Invocations

When the AI model decides to use a tool, it outputs a structured tool use request. The host then maps this to an MCP `tools/call` message.

### Claude's Tool Use Flow

**Step 1: Model returns a tool_use block**

```json
{
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "Let me check the database for last month's signups."
    },
    {
      "type": "tool_use",
      "id": "toolu_01A09q90qw90lq917835lks09",
      "name": "query_database",
      "input": {
        "sql": "SELECT COUNT(*) as signup_count FROM users WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month') AND created_at < DATE_TRUNC('month', CURRENT_DATE)"
      }
    }
  ]
}
```

**Step 2: Host maps to MCP tools/call**

```json
{
  "jsonrpc": "2.0",
  "id": 42,
  "method": "tools/call",
  "params": {
    "name": "query_database",
    "arguments": {
      "sql": "SELECT COUNT(*) as signup_count FROM users WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month') AND created_at < DATE_TRUNC('month', CURRENT_DATE)"
    }
  }
}
```

**Step 3: MCP server returns result**

```json
{
  "jsonrpc": "2.0",
  "id": 42,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "signup_count\n-----------\n2,847"
      }
    ]
  }
}
```

**Step 4: Host feeds result back to model**

```json
{
  "role": "user",
  "content": [
    {
      "type": "tool_result",
      "tool_use_id": "toolu_01A09q90qw90lq917835lks09",
      "content": "signup_count\n-----------\n2,847"
    }
  ]
}
```

**Step 5: Model generates final response**

```json
{
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "According to the database, 2,847 users signed up last month."
    }
  ]
}
```

The host acts as the translator between the AI model's tool use format and MCP's JSON-RPC format. The model never knows that MCP exists.

---

## 8.5 Handling Tool Results in the Conversation Context

Tool results become part of the conversation context. The AI model can reference previous tool results, use them to inform subsequent tool calls, and synthesize information from multiple tool invocations.

### Result Formatting

How the host formats tool results for the model matters:

- **Text results**: Passed directly as strings. The model reads and interprets the text.
- **Structured data**: JSON results are typically passed as formatted strings. The model can parse and reason about JSON.
- **Images**: Passed as base64-encoded images in the `image` content type. Multimodal models can interpret these visually.
- **Errors**: Passed with an `is_error` flag so the model knows something went wrong and can adapt.

### Context Window Considerations

Every tool result consumes tokens in the context window. Large results (such as full file contents or extensive database query results) can quickly fill the context. Hosts should consider:

- **Truncating large results**: Set reasonable limits on result sizes
- **Summarizing**: For very large datasets, summarize before passing to the model
- **Lazy loading**: Do not include all resource content upfront — let the model request what it needs via tools

---

## 8.6 Multi-Step Reasoning with MCP Tools (Agentic Loops)

The most powerful use of MCP tools is in **agentic loops** — multi-step workflows where the AI model makes multiple tool calls in sequence, using the results of each step to inform the next.

### The Agentic Loop

```
User query → Model thinks → Tool call 1 → Result 1
          → Model thinks → Tool call 2 → Result 2
          → Model thinks → Tool call 3 → Result 3
          → Model generates final response
```

### Example: Investigating a Bug

```
User: "Why is the checkout page showing a 500 error?"

Model: Let me investigate. First, let me check the error logs.
→ Tool call: read_file("/var/log/app/error.log")
← Result: "NullPointerException in PaymentService.processPayment line 47"

Model: The error is a NullPointerException in PaymentService. Let me read that file.
→ Tool call: read_file("/src/services/PaymentService.java")
← Result: [file contents]

Model: I can see the issue on line 47. The payment method is null when
the user hasn't selected one. Let me check if there's a validation step.
→ Tool call: query_database("SELECT * FROM checkout_sessions WHERE status = 'error' ORDER BY created_at DESC LIMIT 5")
← Result: [5 recent error sessions, all with payment_method = null]

Model: I've found the bug. The checkout page allows submission without
selecting a payment method. Line 47 of PaymentService.java tries to
call processPayment() on a null payment method reference. The fix is
to add validation in the checkout form and a null check in the service.
```

### Parallel Tool Calls

Some AI APIs (including Claude) support parallel tool calls — the model can request multiple tool invocations in a single response:

```json
{
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "Let me check both the database and the configuration."
    },
    {
      "type": "tool_use",
      "id": "call_1",
      "name": "query_database",
      "input": {"sql": "SELECT COUNT(*) FROM users"}
    },
    {
      "type": "tool_use",
      "id": "call_2",
      "name": "read_config",
      "input": {"key": "max_users"}
    }
  ]
}
```

The host can execute these MCP calls concurrently, reducing latency. Both results are returned to the model together.

---

## 8.7 Human-in-the-Loop: Approval Flows and Confirmation

The host can implement approval flows that require user confirmation before executing certain tool calls. This is a critical safety mechanism.

### How It Works

1. The AI model decides to use a tool
2. The host checks its approval policy for that tool
3. If approval is required, the host shows the user what the model wants to do
4. The user approves or denies
5. If approved, the host sends the MCP `tools/call` request
6. If denied, the host returns a denial message to the model

### Approval Policies

Hosts typically implement tiered approval:

- **Auto-approve**: Read-only tools, safe operations (`readOnlyHint: true`)
- **Notify**: Moderate-risk operations — show the user but auto-approve after a timeout
- **Require approval**: Destructive operations (`destructiveHint: true`), external communications (`openWorldHint: true`)
- **Block**: Operations that are never allowed

### Example in Claude Code

Claude Code implements a permission system where:
- File reads are auto-approved
- File writes require approval the first time
- Shell commands require approval
- Users can configure trust levels per tool

---

## 8.8 Context Window Management with Many Tools

When a host connects to many MCP servers, the total number of available tools can be large. Each tool definition (name, description, schema) consumes tokens in the model's context window. With dozens or hundreds of tools, this becomes a significant overhead.

### Strategies for Managing Tool Count

**Tool filtering**: Only include tools relevant to the current conversation or task. If the user is working on a database task, include database tools but not Slack tools.

**Tool grouping**: Group related tools and only expand the group when needed. Present "Database Tools" as a single high-level tool, and if the model selects it, expand it to show the specific database tools.

**Lazy loading**: Start with a minimal tool set and dynamically add tools as the conversation progresses and the user's needs become clearer.

**Tool descriptions**: Keep descriptions concise but informative. Every extra word in a description costs tokens across every API call.

**Pagination**: For servers with many tools, use `tools/list` pagination to only load what is needed.

---

## 8.9 How Different AI Providers Integrate MCP

While MCP is a universal protocol, different AI providers integrate with it in different ways:

### Anthropic (Claude)

Anthropic is the creator of MCP and has the deepest integration:
- **Claude Desktop** acts as a full MCP host with tool approval flows
- **Claude Code** is a sophisticated MCP host with multiple simultaneous server connections
- **Claude API** supports tool use that maps directly to MCP tool definitions

### Other Integrations

Many AI development tools have adopted MCP:
- **Cursor, Windsurf, Zed**: IDE-based hosts that connect to MCP servers for coding assistance
- **Sourcegraph Cody**: Uses MCP for code intelligence tools
- **Continue**: Open-source AI coding assistant with MCP support

The key insight is that MCP's value increases with adoption. Each new host that supports MCP gains access to all existing MCP servers, and each new server is immediately usable by all existing hosts.

---

## Summary

Understanding how AI models interact with MCP — even though they do not interact with MCP directly — is essential for building effective MCP-powered applications.

Key takeaways:

- **The AI model never sees MCP directly.** The host translates between the model's tool use format and MCP's JSON-RPC protocol.
- **Tools appear as native tool definitions** in the AI model's API request (e.g., Claude's `tools` parameter)
- **Resources become context** — included in system prompts or user messages
- **Prompts become message sequences** inserted into the conversation
- **The model decides when to use tools** based on user intent, tool descriptions, and parameter schemas
- **Agentic loops** enable multi-step reasoning where the model chains tool calls together
- **Human-in-the-loop approval** is the host's responsibility, not the model's or the server's
- **Context window management** is critical when many tools are available — filtering, grouping, and lazy loading help
- **MCP's value grows with adoption** — each new host and server strengthens the entire ecosystem

This concludes Part II: The Three Pillars. You now understand the complete protocol — the architecture, the message format, the transports, and the three core primitives (tools, resources, prompts). In Part III, we will put this knowledge into practice by building MCP servers from scratch, starting with Python.
