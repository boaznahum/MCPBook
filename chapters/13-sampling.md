# Chapter 13: Sampling — When Servers Need AI

---

## 13.1 What Is Sampling in MCP?

Sampling is one of MCP's most distinctive features. While the typical flow has the AI model calling tools on MCP servers, **sampling reverses the direction** — it allows MCP servers to request AI completions from the host's model.

This creates a bidirectional relationship: the AI model uses servers for tools and data, and servers use the AI model for intelligence. It is a powerful pattern that enables servers to perform tasks that require language understanding, generation, or reasoning — without embedding their own AI model.

Consider some scenarios where a server might need AI:

- A code analysis server that needs the AI to explain a complex code pattern
- A data processing server that needs the AI to classify or summarize records
- An email server that needs the AI to draft responses
- A monitoring server that needs the AI to interpret anomalous metrics

Without sampling, these servers would need their own AI integration — separate API keys, model configuration, billing, and context management. With sampling, they leverage the host's existing AI model through a standardized protocol.

---

## 13.2 The Sampling Flow: Server → Client → Host → AI → Response

Sampling follows a carefully controlled flow with the human user in the loop:

```
MCP Server                    MCP Client / Host              AI Model
    │                              │                           │
    │ ── sampling/createMessage ──→│                           │
    │                              │                           │
    │                              │── [User approval?] ──→ User
    │                              │←── [Approved] ────────    │
    │                              │                           │
    │                              │── API request ──────────→ │
    │                              │←── AI response ──────────│
    │                              │                           │
    │                              │── [Review/modify?] ──→ User
    │                              │←── [Accepted] ────────    │
    │                              │                           │
    │ ←── sampling response ───────│                           │
    │                              │                           │
```

The key steps:

1. **Server sends `sampling/createMessage`** to the client with the messages and model preferences
2. **Host may ask user for approval** before forwarding to the AI (human-in-the-loop)
3. **Host sends the request to the AI model** via the model's API
4. **Host may show the response to the user** for review/modification before returning it
5. **Host returns the AI response** to the server

The host has full control over the sampling process. It can:
- Reject the request entirely
- Modify the messages before sending to the AI
- Modify the AI's response before returning it to the server
- Apply its own model preferences (overriding the server's)
- Log all sampling requests for audit

This design ensures that the human user (through the host) retains control over all AI interactions, even those initiated by servers.

---

## 13.3 The `sampling/createMessage` Request

The server sends a `sampling/createMessage` request to the client:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "sampling/createMessage",
  "params": {
    "messages": [
      {
        "role": "user",
        "content": {
          "type": "text",
          "text": "Classify the following customer feedback as positive, negative, or neutral. Respond with only the classification.\n\nFeedback: 'The product works great but shipping was slow.'"
        }
      }
    ],
    "maxTokens": 50,
    "modelPreferences": {
      "hints": [
        { "name": "claude-haiku-4-5-20251001" }
      ],
      "speedPriority": 0.8,
      "costPriority": 0.9,
      "intelligencePriority": 0.3
    },
    "systemPrompt": "You are a sentiment classifier. Respond with exactly one word: positive, negative, or neutral.",
    "temperature": 0.0
  }
}
```

### Parameters

**`messages`** (required): An array of conversation messages for the AI. Each message has a `role` ("user" or "assistant") and `content`.

**`maxTokens`** (required): Maximum number of tokens in the AI's response.

**`modelPreferences`** (optional): Hints about what kind of model to use:
- `hints`: Specific model names/families the server prefers
- `speedPriority`: How much to prioritize speed (0.0 to 1.0)
- `costPriority`: How much to prioritize low cost (0.0 to 1.0)
- `intelligencePriority`: How much to prioritize intelligence (0.0 to 1.0)

The host is free to ignore these preferences entirely. They are advisory hints, not requirements.

**`systemPrompt`** (optional): A system prompt for the AI. The host may override or modify this.

**`temperature`** (optional): Sampling temperature for the AI response.

**`includeContext`** (optional): Whether to include context from the current conversation:
- `"none"`: Do not include any conversation context
- `"thisServer"`: Include context from this server's interactions
- `"allServers"`: Include context from all server interactions

---

## 13.4 Message Format and Model Preferences

### Messages

Sampling messages use the same content types as other MCP messages:

```json
{
  "messages": [
    {
      "role": "user",
      "content": {
        "type": "text",
        "text": "Summarize the following data..."
      }
    },
    {
      "role": "user",
      "content": {
        "type": "image",
        "data": "base64...",
        "mimeType": "image/png"
      }
    }
  ]
}
```

### Model Preferences

Model preferences use a priority system rather than hard requirements:

```json
{
  "modelPreferences": {
    "hints": [
      { "name": "claude-haiku-4-5-20251001" },
      { "name": "claude-sonnet-4-5-20250929" }
    ],
    "speedPriority": 0.8,
    "costPriority": 0.7,
    "intelligencePriority": 0.5
  }
}
```

The `hints` array lists preferred models in order of preference. The host selects the best available model based on these hints and the priority scores. The priorities help the host choose when hints are not available — high `costPriority` suggests using a cheaper model, high `intelligencePriority` suggests using the most capable model.

---

## 13.5 Human-in-the-Loop Controls for Sampling

Sampling is designed with human control as a core principle:

1. **Approval**: The host can require user approval before any sampling request is processed
2. **Visibility**: The user can see what the server is asking the AI to do
3. **Modification**: The user can modify the messages or the response
4. **Rejection**: The user can reject the sampling request entirely

This is crucial for trust and safety. A server could potentially misuse sampling to:
- Extract sensitive information from the conversation context
- Generate harmful content
- Waste API credits with unnecessary requests

The host's human-in-the-loop controls prevent these abuses.

---

## 13.6 Use Cases for Sampling

### 13.6.1 Agentic Behaviors Within Servers

A server can use sampling to implement intelligent behavior without embedding its own AI:

```python
@mcp.tool()
async def smart_query(question: str, ctx: Context) -> str:
    """Answer a question about the database using AI to generate SQL."""
    # Get the schema
    schema = get_database_schema()

    # Use sampling to generate SQL from the question
    result = await ctx.session.create_message(
        messages=[{
            "role": "user",
            "content": {
                "type": "text",
                "text": f"Given this schema:\n{schema}\n\nGenerate a SQL query for: {question}\nReturn only the SQL, no explanation."
            }
        }],
        max_tokens=500
    )

    sql = result.content.text.strip()

    # Execute the generated SQL
    return execute_query(sql)
```

### 13.6.2 Multi-Step Workflows

Servers can use sampling for iterative refinement:

```python
@mcp.tool()
async def refine_code(code: str, requirements: str, ctx: Context) -> str:
    """Iteratively refine code to meet requirements."""
    current_code = code

    for iteration in range(3):
        result = await ctx.session.create_message(
            messages=[{
                "role": "user",
                "content": {
                    "type": "text",
                    "text": f"Review this code against the requirements and suggest improvements.\n\nRequirements: {requirements}\n\nCode:\n```\n{current_code}\n```\n\nIf the code meets all requirements, respond with 'APPROVED'. Otherwise, provide the improved code."
                }
            }],
            max_tokens=2000
        )

        response = result.content.text
        if "APPROVED" in response:
            return current_code

        current_code = extract_code(response)

    return current_code
```

### 13.6.3 Content Generation and Transformation

```python
@mcp.tool()
async def translate_document(path: str, target_language: str, ctx: Context) -> str:
    """Translate a document to another language using AI."""
    with open(path) as f:
        content = f.read()

    result = await ctx.session.create_message(
        messages=[{
            "role": "user",
            "content": {
                "type": "text",
                "text": f"Translate the following document to {target_language}. Preserve formatting.\n\n{content}"
            }
        }],
        max_tokens=4000,
        model_preferences={
            "intelligencePriority": 0.9  # Need high quality for translation
        }
    )

    translated = result.content.text
    output_path = path.replace(".", f".{target_language}.")
    with open(output_path, "w") as f:
        f.write(translated)

    return f"Translated document saved to {output_path}"
```

---

## 13.7 Security Implications of Sampling

Sampling introduces unique security considerations:

- **Data exposure**: Sampling messages could contain sensitive data. The host should review what data is being sent.
- **Cost control**: Each sampling request costs API credits. Malicious or buggy servers could send excessive requests.
- **Prompt injection**: A server could craft sampling messages that attempt to manipulate the AI.
- **Context leakage**: If `includeContext` is set to `"allServers"`, one server could learn about other servers' interactions.

**Mitigations:**
- Always implement human-in-the-loop approval for sampling
- Set rate limits on sampling requests per server
- Review and sanitize sampling messages before forwarding to the AI
- Default `includeContext` to `"none"` unless explicitly needed
- Audit all sampling requests

---

## 13.8 Implementation Examples

### Python Server Requesting Sampling

```python
from mcp.server.fastmcp import FastMCP, Context

mcp = FastMCP("sampling-example")

@mcp.tool()
async def classify_text(text: str, ctx: Context) -> str:
    """Classify text using AI sampling."""
    result = await ctx.session.create_message(
        messages=[{
            "role": "user",
            "content": {
                "type": "text",
                "text": f"Classify this text into one category: news, opinion, tutorial, review.\n\n{text}"
            }
        }],
        max_tokens=10
    )
    return f"Classification: {result.content.text}"
```

### Client Handling Sampling Requests (Python)

```python
from mcp import ClientSession

async def sampling_handler(request):
    """Handle sampling requests from servers."""
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=request.params.maxTokens,
        messages=[
            {"role": m.role, "content": m.content.text}
            for m in request.params.messages
        ]
    )

    return {
        "role": "assistant",
        "content": {"type": "text", "text": response.content[0].text},
        "model": response.model
    }
```

---

## Summary

Sampling is a unique MCP feature that creates a bidirectional AI relationship — servers can leverage the host's AI model for intelligence tasks without maintaining their own model integration.

Key takeaways:

- **Sampling reverses the typical flow**: servers request AI completions from the host
- **Human-in-the-loop** is a core principle — the host controls all sampling interactions
- **Model preferences** are advisory hints, not requirements
- **Use cases** include SQL generation, content classification, translation, and multi-step refinement
- **Security** requires rate limiting, approval flows, and careful handling of context inclusion
- **Sampling must be declared** in client capabilities during initialization

In the next chapter, we will explore the supporting features that round out MCP: roots, logging, progress, cancellation, and pagination.
