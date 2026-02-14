# Chapter 7: Prompts — Reusable Interaction Templates

---

## 7.1 What Are MCP Prompts?

Prompts are the third of MCP's three core primitives, alongside tools and resources. While tools provide *actions* and resources provide *data*, prompts provide **reusable interaction templates** — pre-crafted message sequences that encode best practices, domain expertise, and common workflows.

An MCP prompt is a parameterized template that, when retrieved, expands into one or more messages that can be inserted into a conversation with the AI model. Think of prompts as recipes — they package a proven way to ask the AI to perform a specific task, complete with the right framing, instructions, and context.

For example, a code review prompt might expand into a message that says: "You are an expert code reviewer. Analyze the following code for bugs, security issues, performance problems, and style violations. Provide specific, actionable feedback with line references." This is more effective than a user typing "review this code" — the prompt encodes domain expertise about what makes a good code review.

Key characteristics of prompts:

- **User-controlled**: Unlike tools (which the AI decides to use), prompts are typically selected by the user or host application
- **Parameterized**: Prompts can accept arguments that customize the output
- **Expand to messages**: A prompt expands into one or more messages (user, assistant, or system messages) that are inserted into the conversation
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

## 7.4 Prompt Arguments and Dynamic Content

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

## 7.5 Multi-Turn Prompt Structures

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

## 7.6 Embedded Resources in Prompts

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

## 7.7 Prompts vs. System Prompts vs. Tools

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

## 7.8 Designing Effective Prompt Templates

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

## 7.9 Real-World Prompt Examples

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
