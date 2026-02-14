# Chapter 20: Agent Capabilities: Learning, Adaptation, and Knowledge

---

## 20.1 Static vs. Dynamic Capabilities

An AI agent's capabilities come from two sources:

**Static capabilities** are baked into the agent at design time:
- The AI model's training data and reasoning abilities
- The system prompt and instructions
- The hardcoded list of MCP servers to connect to
- The agent's architecture (loop structure, error handling, max turns)

**Dynamic capabilities** are discovered or acquired at runtime:
- Tools discovered from MCP servers during initialization
- Resources loaded as context
- Prompts retrieved for specific workflows
- New MCP servers connected mid-session
- Tool list changes from servers that add/remove tools dynamically

MCP's architecture naturally supports dynamic capabilities. Because tools, resources, and prompts are discovered at runtime through protocol messages (`tools/list`, `resources/list`, `prompts/list`) rather than hardcoded, an agent's capabilities are inherently extensible.

Consider a practical example: an agent connects to an MCP server that provides access to a company's internal tools. When a new tool is deployed to that server, the agent automatically discovers it on the next `tools/list` call — no agent code changes required.

---

## 20.2 How Agents Acquire Knowledge at Runtime

### 20.2.1 Tool Discovery and Dynamic Registration

MCP servers can dynamically change their tool offerings:

```python
# Server that adds tools based on what plugins are loaded
mcp = FastMCP("plugin-server")

loaded_plugins = {}

@mcp.tool()
async def load_plugin(plugin_name: str) -> str:
    """Load a plugin that adds new tools."""
    plugin = import_plugin(plugin_name)
    loaded_plugins[plugin_name] = plugin

    # Register the plugin's tools with the MCP server
    for tool in plugin.get_tools():
        mcp.add_tool(tool)

    # Notify the client that tools have changed
    # (FastMCP handles this automatically)
    return f"Plugin '{plugin_name}' loaded with {len(plugin.get_tools())} tools"
```

When the client receives `notifications/tools/list_changed`, it re-fetches the tool list and the agent gains new capabilities without restarting.

### 20.2.2 Resources as Dynamic Knowledge Sources

Resources allow agents to load knowledge on demand:

```python
# The agent's system prompt can reference resources
system_prompt = """You are a customer service agent.

Before answering any question:
1. Check the FAQ resource for existing answers
2. Check the policies resource for current policies
3. Check the customer's account via the customer lookup tool

Always cite which resource or tool informed your answer."""

# MCP resources provide live knowledge
@mcp.resource("kb://faq")
async def get_faq() -> str:
    """Current FAQ database."""
    return load_faq_from_database()

@mcp.resource("kb://policies")
async def get_policies() -> str:
    """Current company policies."""
    return load_policies()

@mcp.resource("kb://product/{product_id}")
async def get_product_info(product_id: str) -> str:
    """Product information."""
    return load_product(product_id)
```

This is a form of **runtime knowledge acquisition** — the agent does not have this knowledge in its training data, but it can access it when needed through MCP resources.

### 20.2.3 Retrieval-Augmented Generation (RAG) via MCP

RAG is a technique where the AI retrieves relevant information from an external knowledge base before generating a response. MCP provides a natural framework for RAG:

```python
# RAG server
mcp = FastMCP("rag-server")

@mcp.tool()
async def search_knowledge(query: str, top_k: int = 5) -> str:
    """Search the knowledge base for relevant documents.

    Args:
        query: Natural language search query
        top_k: Number of results to return
    """
    # Embed the query
    embedding = embed_text(query)

    # Search the vector database
    results = vector_db.search(embedding, limit=top_k)

    # Format results
    formatted = []
    for result in results:
        formatted.append(
            f"**{result.title}** (relevance: {result.score:.2f})\n"
            f"{result.content}\n"
            f"Source: {result.source}"
        )

    return "\n\n---\n\n".join(formatted)

@mcp.tool()
async def add_to_knowledge(title: str, content: str, source: str) -> str:
    """Add a new document to the knowledge base.

    Args:
        title: Document title
        content: Document content
        source: Where this information came from
    """
    embedding = embed_text(content)
    vector_db.insert(title=title, content=content, source=source, embedding=embedding)
    return f"Added '{title}' to knowledge base"
```

With this MCP server, any agent can perform RAG — searching for relevant knowledge before answering questions and even adding new knowledge as it learns.

---

## 20.3 Can MCP Agents Learn? Understanding the Boundaries

A common question: **can MCP agents learn?** The answer is nuanced.

### What Agents CAN Do

- **Accumulate knowledge within a session**: An agent can discover information through tools and use it in subsequent reasoning steps. This is "learning" within the session's context window.
- **Store knowledge persistently**: An agent can write findings to files, databases, or memory servers. This information persists beyond the session and can be retrieved later.
- **Adapt behavior dynamically**: Through tool discovery and resource loading, an agent can gain new capabilities at runtime.
- **Improve through feedback**: An agent can adjust its approach based on tool results and errors — if a query fails, it tries a different approach.

### What Agents CANNOT Do

- **Update the AI model's weights**: An agent cannot modify the underlying LLM's parameters. The model's knowledge is fixed at the point of its last training/fine-tuning.
- **Learn generalizable skills from experience**: An agent does not generalize from one session to the next. Each session starts fresh with the same model capabilities. However, persistent memory (files, databases) can bridge sessions.
- **Improve their own reasoning**: The quality of the agent's reasoning is determined by the LLM. The agent framework cannot make the LLM "smarter."

### The Practical Implication

Agents do not "learn" in the way humans do, but they can be *designed* to accumulate and use knowledge effectively:

```python
# A "learning" agent pattern
class LearningAgent:
    def __init__(self):
        self.memory_file = "agent_memory.json"

    async def run(self, task: str):
        # Load previous memories
        memories = self.load_memories()

        # Include memories in the system prompt
        system = f"""You are an AI assistant.

        Here are relevant notes from previous sessions:
        {memories}

        If you learn anything important during this session,
        use the 'remember' tool to save it for future sessions."""

        # Run the agent with memory-aware tools
        result = await run_agent(system, task, tools=[
            self.remember_tool,
            self.recall_tool,
            # ... other tools ...
        ])

        return result

    async def remember(self, key: str, value: str):
        """Save something for future sessions."""
        memories = self.load_memories()
        memories[key] = {
            "value": value,
            "timestamp": datetime.now().isoformat()
        }
        self.save_memories(memories)
```

---

## 20.4 Fine-Tuning and Retraining the Underlying AI Models

### 20.4.1 When and Why to Fine-Tune

Fine-tuning adjusts the AI model's weights on domain-specific data. Consider fine-tuning when:

- The model consistently struggles with your domain's terminology or conventions
- You need the model to follow specific output formats reliably
- You want to improve performance on a narrow, well-defined task
- You have high-quality training data specific to your use case

Fine-tuning is a **model-level operation** — it happens outside of MCP, at the AI provider level. The resulting fine-tuned model is then used by the host application, and MCP servers interact with it through the same protocol.

### 20.4.2 How Fine-Tuning Relates to MCP Capabilities

Fine-tuning and MCP are complementary:

- **Fine-tuning** improves the model's *reasoning and knowledge*
- **MCP** extends the model's *actions and data access*

A fine-tuned model that understands medical terminology better will use a medical database MCP server more effectively. But you cannot replace MCP tools with fine-tuning — a model fine-tuned on database knowledge still cannot execute SQL queries without a tool.

The relationship:

```
Fine-tuning → Better reasoning about when/how to use tools
MCP → The actual tools the model can use
Together → An agent that both understands the domain deeply
           AND can take effective action
```

---

## 20.5 Knowledge Packaging: Distributing Expertise as MCP Servers

One of MCP's most powerful ideas is that **domain expertise can be packaged and distributed as MCP servers**. This creates a marketplace of capabilities:

### Expert Tools

A security expert can package their knowledge as an MCP server:

```python
mcp = FastMCP("security-scanner")

@mcp.tool()
async def scan_code_for_vulnerabilities(file_path: str) -> str:
    """Scan source code for common security vulnerabilities."""
    code = read_file(file_path)
    vulnerabilities = run_security_checks(code)
    return format_vulnerability_report(vulnerabilities)

@mcp.resource("security://owasp-top-10")
async def owasp_reference() -> str:
    """OWASP Top 10 vulnerability reference."""
    return load_owasp_reference()

@mcp.prompt()
async def security_audit(scope: str = "full") -> str:
    """Conduct a security audit of the codebase."""
    return f"""Conduct a {'comprehensive' if scope == 'full' else 'focused'} security audit.
    Use the scan_code_for_vulnerabilities tool on each source file.
    Reference the OWASP Top 10 resource for context.
    Produce a report with severity ratings and remediation guidance."""
```

Now any agent that connects to this server gains security expertise — the tools encode scanning logic, the resources provide reference knowledge, and the prompts encode the workflow.

### Domain Knowledge Servers

```python
# A legal compliance server
mcp = FastMCP("compliance-checker")

@mcp.tool()
async def check_gdpr_compliance(data_processing_description: str) -> str:
    """Check if a data processing activity is GDPR compliant."""
    ...

@mcp.resource("compliance://gdpr/articles")
async def gdpr_articles() -> str:
    """Full text of relevant GDPR articles."""
    ...

@mcp.resource("compliance://gdpr/checklist")
async def gdpr_checklist() -> str:
    """GDPR compliance checklist."""
    ...
```

---

## 20.6 Designing Agents for Extensibility

Design your agents to be extensible through MCP:

### Plugin Architecture

```python
class ExtensibleAgent:
    """An agent that gains capabilities from MCP servers."""

    def __init__(self):
        self.servers = {}
        self.tools = []

    async def add_capability(self, name: str, server_config: dict):
        """Add a capability by connecting to an MCP server."""
        session = await connect_mcp_server(server_config)
        self.servers[name] = session

        # Discover and add tools
        tools = await session.list_tools()
        self.tools.extend(tools.tools)

    async def remove_capability(self, name: str):
        """Remove a capability."""
        if name in self.servers:
            session = self.servers.pop(name)
            await session.close()
            # Re-build tool list without this server's tools
            self.tools = []
            for s in self.servers.values():
                tools = await s.list_tools()
                self.tools.extend(tools.tools)
```

### Self-Configuring Agents

An agent can even discover and connect to new MCP servers at runtime:

```python
@mcp.tool()
async def install_capability(server_package: str) -> str:
    """Install a new MCP server to gain additional capabilities.

    Args:
        server_package: The package name (e.g., 'mcp-server-github')
    """
    # Install the package
    subprocess.run(["pip", "install", server_package], check=True)

    # Connect to the new server
    await agent.add_capability(server_package, {
        "command": server_package,
        "args": []
    })

    return f"Installed and connected to {server_package}"
```

---

## Summary

Agent capabilities in MCP are fundamentally about composing knowledge, tools, and expertise at runtime.

Key takeaways:

- **Dynamic capabilities** through MCP tool/resource discovery make agents naturally extensible
- **RAG via MCP** provides a standard way to search and retrieve knowledge
- **Agents cannot learn** in the ML sense (they do not update model weights), but they can accumulate and persist knowledge across sessions
- **Fine-tuning improves reasoning**; MCP provides action — they are complementary
- **Knowledge packaging** as MCP servers allows domain expertise to be distributed and reused
- **Extensible agent design** uses MCP's dynamic discovery to gain capabilities at runtime

This concludes Part V: AI Agents and Multi-Agent Orchestration. In Part VI, we will explore real-world applications, testing, performance, and the future of MCP.
