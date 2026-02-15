# Chapter 7: Prompts — Reusable Interaction Templates

---

## 7.1 What Are MCP Prompts?

Prompts are the third of MCP's three core primitives, alongside tools and resources. While tools provide *actions* and resources provide *data*, prompts provide **reusable interaction templates** — pre-crafted message sequences that encode best practices, domain expertise, and common workflows.

An MCP prompt is a parameterized template that, when retrieved, expands into one or more messages that can be inserted into a conversation with the AI model. Think of prompts as recipes — they package a proven way to ask the AI to perform a specific task, complete with the right framing, instructions, and context.

For example, a code review prompt might expand into a message that says: "You are an expert code reviewer. Analyze the following code for bugs, security issues, performance problems, and style violations. Provide specific, actionable feedback with line references." This is more effective than a user typing "review this code" — the prompt encodes domain expertise about what makes a good code review.

Key characteristics of prompts:

- **User-controlled**: Unlike tools (which the AI decides to use), prompts are typically selected by the user or host application
- **Parameterized**: Prompts can accept arguments that customize the output
- **Expand to messages**: A prompt expands into one or more messages with `"user"` or `"assistant"` roles that are inserted into the conversation
- **Can embed resources**: Prompts can include resource content, bringing data and instructions together
- **Reusable**: The same prompt can be used in different conversations with different arguments

---

## 7.2 Prompt Discovery: `prompts/list`

Like tools and resources, prompts are discovered dynamically:

```json
// Request
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "prompts/list"
}

// Response
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "prompts": [
      {
        "name": "code_review",
        "description": "Review code for bugs, security issues, and best practices",
        "arguments": [
          {
            "name": "language",
            "description": "The programming language of the code",
            "required": false
          },
          {
            "name": "focus",
            "description": "Specific area to focus on: security, performance, style, or all",
            "required": false
          }
        ]
      },
      {
        "name": "explain_error",
        "description": "Explain an error message and suggest fixes",
        "arguments": [
          {
            "name": "error_message",
            "description": "The error message to explain",
            "required": true
          },
          {
            "name": "context",
            "description": "Additional context about where the error occurred",
            "required": false
          }
        ]
      },
      {
        "name": "generate_tests",
        "description": "Generate unit tests for a given function or class",
        "arguments": [
          {
            "name": "framework",
            "description": "Testing framework to use (pytest, unittest, jest, etc.)",
            "required": false
          }
        ]
      }
    ]
  }
}
```

Each prompt in the list has:
- **`name`**: A unique identifier for the prompt
- **`description`** (optional): A human-readable description of what the prompt does
- **`arguments`** (optional): A list of arguments the prompt accepts, each with a name, description, and required flag

---

## 7.3 Prompt Retrieval: `prompts/get`

To get a prompt's expanded content, the client sends a `prompts/get` request with the prompt name and any arguments:

```json
// Request
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "prompts/get",
  "params": {
    "name": "code_review",
    "arguments": {
      "language": "python",
      "focus": "security"
    }
  }
}

// Response
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "description": "Security-focused Python code review",
    "messages": [
      {
        "role": "user",
        "content": {
          "type": "text",
          "text": "You are an expert Python security reviewer. Analyze the following code with a focus on security vulnerabilities.\n\nLook for:\n- SQL injection vulnerabilities\n- Command injection\n- Path traversal attacks\n- Insecure deserialization\n- Hardcoded secrets or credentials\n- Improper input validation\n- Insecure use of cryptographic functions\n- SSRF vulnerabilities\n\nFor each issue found, provide:\n1. The specific line or code section\n2. The vulnerability type (CWE if applicable)\n3. The potential impact\n4. A concrete fix with code example\n\nIf no security issues are found, state that explicitly and mention any security best practices the code follows well."
        }
      }
    ]
  }
}
```

The response contains:
- **`description`** (optional): A description of the expanded prompt (may differ from the listing description based on arguments)
- **`messages`**: An array of messages to insert into the conversation

---

## 7.4 Step by Step: What Happens When You Use a Prompt

MCP prompts involve three participants — the **server** (defines the prompt), the **client/host** (manages the UI and the LLM conversation), and the **user** (picks the prompt). Here is exactly what happens, from start to finish.

### The Scenario

A development team has built an MCP server with a `code_review` prompt. A developer is using Claude Desktop (the host application) connected to this server. The developer wants to review some Python code for security issues.

### Step 1: Server Defines the Prompt (Startup)

When the MCP server starts, it registers prompt templates — just like it registers tools:

```python
@mcp.prompt()
async def code_review(language: str = "any", focus: str = "all") -> list[Message]:
    return [
        UserMessage(
            f"You are an expert {language} code reviewer. "
            f"Analyze the following code with a focus on {focus}.\n\n"
            f"For each issue found, provide:\n"
            f"1. The specific line or code section\n"
            f"2. The severity (Critical / High / Medium / Low)\n"
            f"3. A concrete fix with code example"
        )
    ]
```

At this point, nothing has been sent anywhere. The server just has a function ready to call.

### Step 2: Client Discovers Available Prompts (Connection)

When Claude Desktop connects to the server, it calls `prompts/list`:

```
Client → Server:  prompts/list
Server → Client:  [{ name: "code_review", arguments: [language, focus] }]
```

Claude Desktop now knows this prompt exists. It might display it as a **slash command** (`/code_review`) in the UI, or list it in a menu.

### Step 3: User Selects the Prompt (Human Action)

The developer types `/code_review` in Claude Desktop, or picks it from a dropdown menu.

**This is a human action.** The AI model did not choose this — the developer did. This is the fundamental difference between prompts and tools:

| | Who decides to use it? |
|--|----------------------|
| **Tool** | The AI model (autonomously) |
| **Prompt** | The user (explicitly) |

### Step 4: Client Collects Arguments (UI)

Claude Desktop sees that `code_review` has two arguments (`language` and `focus`). It shows a form or asks the developer:

```
Language: python
Focus: security
```

The developer fills these in.

### Step 5: Client Calls `prompts/get` (Protocol)

Claude Desktop sends the request to the MCP server:

```json
{
  "jsonrpc": "2.0",
  "id": 42,
  "method": "prompts/get",
  "params": {
    "name": "code_review",
    "arguments": {
      "language": "python",
      "focus": "security"
    }
  }
}
```

### Step 6: Server Expands the Template (Server Code)

The server runs the `code_review` function with the given arguments. The function returns:

```json
{
  "jsonrpc": "2.0",
  "id": 42,
  "result": {
    "description": "Security-focused Python code review",
    "messages": [
      {
        "role": "user",
        "content": {
          "type": "text",
          "text": "You are an expert python code reviewer. Analyze the following code with a focus on security.\n\nFor each issue found, provide:\n1. The specific line or code section\n2. The severity (Critical / High / Medium / Low)\n3. A concrete fix with code example"
        }
      }
    ]
  }
}
```

Note: the server returns **messages with roles** — this is structured data, not raw text.

### Step 7: Client Injects Messages into the LLM Conversation (Client Code)

This is the step most people miss. Claude Desktop takes the returned messages and **inserts them into the conversation it sends to the AI model**. The developer may also paste their code into the conversation. The final API call to Claude looks something like this:

```json
{
  "model": "claude-sonnet-4-5-20250929",
  "messages": [
    {
      "role": "user",
      "content": "You are an expert python code reviewer. Analyze the following code with a focus on security.\n\nFor each issue found, provide:\n1. The specific line or code section\n2. The severity (Critical / High / Medium / Low)\n3. A concrete fix with code example"
    },
    {
      "role": "user",
      "content": "```python\ndef login(username, password):\n    query = f\"SELECT * FROM users WHERE name='{username}'\"\n    ...\n```"
    }
  ]
}
```

The first message came from the MCP prompt. The second came from the developer. Claude sees them all as a normal conversation.

### Step 8: The AI Responds (AI)

Claude processes the messages and responds with a detailed security review, exactly as instructed by the prompt template. It has no idea that the first message came from an MCP prompt rather than the developer typing it directly — it all looks the same to the model.

### The Complete Flow in One Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  ┌─────────┐         ┌──────────────┐         ┌──────────────┐      │
│  │  SERVER  │         │ CLIENT/HOST  │         │     USER     │      │
│  │         │         │ (Claude      │         │ (Developer)  │      │
│  │         │         │  Desktop)    │         │              │      │
│  └────┬────┘         └──────┬───────┘         └──────┬───────┘      │
│       │                     │                        │              │
│       │   1. prompts/list   │                        │              │
│       │←────────────────────│                        │              │
│       │────────────────────→│                        │              │
│       │  [code_review, ...] │  2. Shows /code_review │              │
│       │                     │───────────────────────→│              │
│       │                     │                        │              │
│       │                     │  3. User picks prompt  │              │
│       │                     │←───────────────────────│              │
│       │                     │                        │              │
│       │                     │  4. Asks for arguments │              │
│       │                     │───────────────────────→│              │
│       │                     │    language=python     │              │
│       │                     │    focus=security      │              │
│       │                     │←───────────────────────│              │
│       │                     │                        │              │
│       │   5. prompts/get    │                        │              │
│       │      (code_review,  │                        │              │
│       │       python,       │                        │              │
│       │       security)     │                        │              │
│       │←────────────────────│                        │              │
│       │                     │                        │              │
│       │   6. Returns        │                        │              │
│       │      expanded       │                        │              │
│       │      messages       │                        │              │
│       │────────────────────→│                        │              │
│       │                     │                        │              │
│       │                     │  7. Injects messages   │              │
│       │                     │     into conversation  │              │
│       │                     │     + sends to Claude  │              │
│       │                     │         API            │              │
│       │                     │                        │              │
│       │                     │  8. Claude responds    │              │
│       │                     │     with code review   │              │
│       │                     │───────────────────────→│              │
│       │                     │                        │              │
│  └────┴────┘         └──────┴───────┘         └──────┴───────┘      │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Key Insights

**The AI model never sees `prompts/get`.** It never knows a prompt was used. It just receives messages in its conversation — the same way it would if the user had typed the instructions manually.

**The client is the orchestrator.** The client discovers prompts, presents them to the user, collects arguments, calls the server, and injects the result into the conversation. The server just expands templates.

**Prompts are not tools.** The AI cannot invoke a prompt. Only the user (through the client UI) can select a prompt. This is a deliberate design choice — prompts shape how the AI thinks, so the user should be the one choosing them.

---

## 7.5 Allowed Roles: User and Assistant Only

MCP prompt messages support exactly **two roles**:

| Role | Allowed | Purpose |
|------|---------|---------|
| `"user"` | Yes | Messages that appear to come from the user |
| `"assistant"` | Yes | Messages that appear to come from the assistant |
| `"system"` | **No** | Not supported in MCP prompts |

There is no `"system"` role. This is a deliberate design choice.

**Why no system role?** System prompts control the AI's fundamental behavior — its personality, safety constraints, capabilities, and boundaries. These are the host application's responsibility. If an MCP server could inject system-level instructions, it could potentially override safety guardrails or change the AI's persona in ways the host application did not intend.

```
┌─────────────────────────────────────────────────┐
│ Host Application (Claude Desktop)               │
│                                                 │
│  System prompt: "You are a helpful assistant.   │
│  Never reveal confidential data..."             │  ← Host controls this
│                                                 │
│  ┌─────────────────────────────────────┐        │
│  │ MCP Prompt Messages                 │        │
│  │                                     │        │
│  │  role: "user" → ✓ Allowed           │        │  ← MCP server controls these
│  │  role: "assistant" → ✓ Allowed      │        │
│  │  role: "system" → ✗ NOT allowed     │        │
│  └─────────────────────────────────────┘        │
└─────────────────────────────────────────────────┘
```

### What Each Role Does in Practice

**`"user"` role messages** are the most common. They provide instructions and context to the AI:

```json
{
  "role": "user",
  "content": {
    "type": "text",
    "text": "Review the following code for security vulnerabilities..."
  }
}
```

When injected into the conversation, the AI treats this as if the user typed it.

**`"assistant"` role messages** are used in multi-turn prompts to pre-load the AI with a response pattern — showing it *how* to respond:

```json
[
  {
    "role": "user",
    "content": { "type": "text", "text": "I need help debugging an error." }
  },
  {
    "role": "assistant",
    "content": {
      "type": "text",
      "text": "I'll help you debug this. Let me ask a few clarifying questions first:\n1. When did this error start occurring?\n2. Can you reproduce it consistently?\n3. What have you already tried?"
    }
  }
]
```

The AI sees this exchange as if it already happened and continues in the same style — asking structured clarifying questions before diving in.

---

## 7.6 Prompt Arguments and Dynamic Content

Prompt arguments allow the same prompt to produce different output based on the input. Arguments are simple key-value pairs (both strings) that the server uses to customize the prompt's messages.

### Static vs. Dynamic Arguments

Some arguments are simple string substitutions:

```python
# Server-side prompt handler
@mcp.prompt()
async def greeting(name: str, language: str = "English") -> str:
    if language == "Spanish":
        return f"¡Hola, {name}! ¿Cómo puedo ayudarte hoy?"
    return f"Hello, {name}! How can I help you today?"
```

Other arguments can trigger entirely different prompt structures:

```python
@mcp.prompt()
async def analyze_data(dataset: str, analysis_type: str = "summary") -> list[Message]:
    messages = []

    if analysis_type == "summary":
        messages.append(UserMessage(
            "Provide a statistical summary of the following dataset. "
            "Include mean, median, mode, standard deviation, and any notable patterns."
        ))
    elif analysis_type == "anomaly":
        messages.append(UserMessage(
            "Analyze the following dataset for anomalies and outliers. "
            "Use statistical methods to identify data points that deviate significantly "
            "from the expected distribution. Explain why each flagged point is anomalous."
        ))
    elif analysis_type == "forecast":
        messages.append(UserMessage(
            "Based on the following dataset, generate a forecast for the next 30 days. "
            "Identify trends, seasonal patterns, and provide confidence intervals."
        ))

    return messages
```

---

## 7.7 Multi-Turn Prompt Structures

Prompts can expand into multiple messages, including both user and assistant messages. This allows prompts to set up multi-turn interactions:

```json
{
  "messages": [
    {
      "role": "user",
      "content": {
        "type": "text",
        "text": "I want you to act as a database migration planner. I'll provide the current and desired schemas, and you'll create a step-by-step migration plan."
      }
    },
    {
      "role": "assistant",
      "content": {
        "type": "text",
        "text": "I'll help you plan a safe database migration. Please provide:\n\n1. The current schema (or a description of it)\n2. The desired schema\n3. Any constraints (zero-downtime requirement, data volume, etc.)\n\nI'll then create a detailed migration plan with rollback steps."
      }
    },
    {
      "role": "user",
      "content": {
        "type": "text",
        "text": "Here is the current schema:\n[The user will provide this]\n\nDesired schema:\n[The user will provide this]\n\nConstraints: Zero-downtime migration required."
      }
    }
  ]
}
```

Multi-turn prompts are useful for:
- Setting up a specific conversational dynamic
- Pre-loading the assistant with the right "mindset" by showing it how to respond
- Creating structured workflows where each turn has a specific purpose

---

## 7.8 Embedded Resources in Prompts

Prompts can include resource content directly, combining instructions with data:

```json
{
  "messages": [
    {
      "role": "user",
      "content": {
        "type": "text",
        "text": "Review the following database schema and suggest optimizations for query performance:"
      }
    },
    {
      "role": "user",
      "content": {
        "type": "resource",
        "resource": {
          "uri": "db://main/schema",
          "mimeType": "application/json",
          "text": "{\"tables\": [{\"name\": \"users\", ...}]}"
        }
      }
    }
  ]
}
```

This is powerful because the prompt server can dynamically fetch the latest resource content when the prompt is retrieved. The prompt does not contain stale data — it always reflects the current state.

A single message can also contain multiple content items:

```json
{
  "role": "user",
  "content": [
    {
      "type": "text",
      "text": "Compare these two configuration files and identify any differences that might cause issues:"
    },
    {
      "type": "resource",
      "resource": {
        "uri": "config://production/settings",
        "mimeType": "application/json",
        "text": "{...}"
      }
    },
    {
      "type": "resource",
      "resource": {
        "uri": "config://staging/settings",
        "mimeType": "application/json",
        "text": "{...}"
      }
    }
  ]
}
```

---

## 7.9 Prompts vs. System Prompts vs. Tools

Understanding the differences between MCP prompts, system prompts, and tools helps you choose the right mechanism:

| Aspect | MCP Prompts | System Prompts | Tools |
|--------|-------------|----------------|-------|
| **Who selects** | User/Application | Application (fixed) | AI Model |
| **When used** | On demand, per interaction | Always present | When the AI decides |
| **Purpose** | Structured interaction templates | Set AI behavior/persona | Perform actions |
| **Dynamic** | Yes (arguments, resources) | Usually static | Yes (arguments) |
| **Scope** | Specific task or workflow | Entire conversation | Single operation |

**Use MCP prompts when:**
- You want to package a proven interaction pattern
- The user should explicitly choose this mode of interaction
- The prompt needs dynamic content (embedded resources, argument-based customization)
- You want to share interaction patterns across applications

**Use system prompts when:**
- You want to set the AI's overall behavior for the entire conversation
- The behavior should be applied automatically, not by user choice

**Use tools when:**
- The AI should decide autonomously when to use the capability
- The operation has side effects or computes a result
- The capability is an action, not an interaction pattern

---

## 7.10 Designing Effective Prompt Templates

### Be Specific

Good prompts are specific about what they want. Instead of "analyze this code," a good prompt specifies what kind of analysis, what to look for, and how to format the output.

### Include Output Format

Tell the AI how you want the output structured:

```
Provide your analysis in the following format:

## Summary
[One paragraph overview]

## Issues Found
For each issue:
- **Severity**: Critical / High / Medium / Low
- **Location**: File and line number
- **Description**: What the issue is
- **Fix**: Suggested remediation

## Recommendations
[Numbered list of improvements]
```

### Use Arguments for Customization

Design prompts with arguments that allow customization without creating separate prompts for every variation:

```json
{
  "name": "code_review",
  "arguments": [
    {"name": "language", "description": "Programming language", "required": false},
    {"name": "focus", "description": "Focus area: security, performance, style, all", "required": false},
    {"name": "severity", "description": "Minimum severity to report: low, medium, high", "required": false}
  ]
}
```

### Leverage Embedded Resources

Use embedded resources to provide current, relevant context. A prompt that says "review this code" is more useful when it automatically includes the actual code from a resource.

---

## 7.11 Real-World Prompt Examples

### SQL Query Helper

```json
{
  "name": "sql_query_helper",
  "description": "Help construct an optimized SQL query for a specific database",
  "arguments": [
    {"name": "database", "required": true, "description": "The database to query"},
    {"name": "goal", "required": true, "description": "What data you want to retrieve"}
  ]
}
```

Expanded with the database schema embedded:

```json
{
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "I need to write a SQL query for the following database. Help me construct an optimized query.\n\nGoal: Find the top 10 customers by total order value in the last 30 days\n\nHere is the database schema:"
        },
        {
          "type": "resource",
          "resource": {
            "uri": "db://production/schema",
            "mimeType": "application/json",
            "text": "{\"tables\": [...]}"
          }
        }
      ]
    }
  ]
}
```

### Incident Response

```json
{
  "name": "incident_response",
  "description": "Guide through a production incident investigation",
  "arguments": [
    {"name": "service", "required": true, "description": "The affected service"},
    {"name": "symptom", "required": true, "description": "The observed symptom"}
  ]
}
```

### Git Commit Review

```json
{
  "name": "review_commits",
  "description": "Review recent git commits for quality and potential issues",
  "arguments": [
    {"name": "since", "required": false, "description": "Review commits since this date or ref"}
  ]
}
```

---

## Summary

Prompts are MCP's mechanism for packaging domain expertise and interaction best practices into reusable templates.

Key takeaways:

- **Prompts are user-controlled** interaction templates that expand into message sequences
- **Discovery** via `prompts/list` reveals available prompts and their arguments
- **Retrieval** via `prompts/get` expands a prompt with the given arguments into messages
- **Arguments** allow customization — the same prompt can produce different output for different inputs
- **Multi-turn structures** let prompts set up complex interaction patterns
- **Embedded resources** bring live data into prompts, keeping them current and contextual
- **Prompts vs. tools**: Prompts are interaction patterns selected by users; tools are actions selected by the AI
- **Effective design** means being specific, including output format expectations, using arguments for customization, and leveraging embedded resources

In the next chapter, we will step back and look at the complete picture: how AI models interact with MCP from their perspective — how they see tools, decide to use them, and process results.
