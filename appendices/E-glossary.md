# Appendix E: Glossary

---

**Agent**: An AI system that autonomously perceives its environment, reasons about goals, takes actions through tools, observes results, and iterates until the goal is achieved.

**Annotation**: Metadata attached to a tool definition that provides hints about its behavior (read-only, destructive, idempotent, open-world).

**Capability**: A feature that a client or server declares support for during initialization (e.g., tools, resources, sampling).

**Capability Negotiation**: The process during initialization where client and server declare which optional features they support.

**Client**: An MCP protocol component that maintains a 1:1 connection with a single MCP server, handling protocol communication on behalf of a host.

**Content Type**: The format of data in tool results and resource contents — text, image (base64), or embedded resource.

**Context Window**: The maximum amount of text (measured in tokens) that an AI model can process in a single interaction, including the conversation history and tool results.

**Cursor**: An opaque string used for pagination in list operations, allowing clients to retrieve results in pages.

**FastMCP**: The high-level Python API for building MCP servers, using decorators (`@mcp.tool()`, `@mcp.resource()`, `@mcp.prompt()`) for capability definitions.

**Function Calling**: The AI model's ability to output structured requests to invoke functions, which the host application then executes. The model-level primitive that MCP builds upon.

**Handoff**: In multi-agent systems, the transfer of full conversation control from one agent to another.

**Host**: The user-facing AI application that manages MCP clients, integrates with AI models, and enforces security policies. Examples: Claude Desktop, Claude Code, Cursor.

**Human-in-the-Loop**: A design pattern where the host requires user approval before executing certain AI-requested actions, particularly for sampling and destructive tools.

**Initialization**: The first phase of an MCP connection where client and server exchange capabilities and version information.

**JSON-RPC 2.0**: The message format used by MCP for all communication — requests, responses, and notifications.

**LLM (Large Language Model)**: The AI model (e.g., Claude, GPT) that provides the reasoning and language understanding capabilities. The "brain" of an AI agent.

**MCP (Model Context Protocol)**: An open protocol that standardizes how AI applications connect to external tools, data sources, and prompt templates.

**McpServer**: The high-level TypeScript API for building MCP servers, equivalent to Python's FastMCP.

**Notification**: A JSON-RPC message that does not expect a response (no `id` field). Used for events like progress updates and capability changes.

**Orchestrator**: An agent that coordinates multiple specialist agents, decomposing tasks, delegating work, and synthesizing results.

**Prompt (MCP)**: A reusable interaction template that expands into a sequence of messages. Prompts can accept arguments and embed resources.

**Protocol Version**: A date-based version string (e.g., `"2025-03-26"`) that identifies the MCP specification version.

**RAG (Retrieval-Augmented Generation)**: A technique where the AI retrieves relevant information from an external knowledge base before generating a response.

**Request**: A JSON-RPC message that expects a response, identified by an `id` field.

**Resource**: An MCP primitive for exposing read-only data, identified by a URI. Resources provide context to AI models.

**Resource Template**: A URI pattern with variables (e.g., `db://{database}/{table}/schema`) that allows dynamic resource access.

**Response**: A JSON-RPC message sent in reply to a request, containing either a `result` (success) or an `error` (failure).

**Root**: A URI that defines a boundary within which an MCP server should operate, typically a file system path or workspace.

**Sampling**: An MCP feature that allows servers to request AI completions from the host, enabling bidirectional AI communication.

**Server**: An MCP component that exposes tools, resources, and/or prompts to clients. Servers are lightweight programs that wrap external capabilities.

**Session**: A logical connection between a client and server, identified by a session ID in HTTP transports or by the process lifetime in stdio.

**SSE (Server-Sent Events)**: A web standard for server-to-client push messaging over HTTP, used in MCP's HTTP+SSE and Streamable HTTP transports.

**Streamable HTTP**: MCP's modern network transport that uses a single HTTP endpoint with optional SSE streaming, supporting both stateful and stateless server modes.

**stdio**: MCP's simplest transport, using standard input/output streams of a child process for communication.

**Tool**: An MCP primitive for exposing actions that the AI model can invoke. Tools have a name, description, input schema, and optional annotations.

**Tool Annotation**: See Annotation.

**Transport**: The mechanism for delivering JSON-RPC messages between client and server (stdio, HTTP+SSE, or Streamable HTTP).

**URI Template**: See Resource Template.

**Zod**: A TypeScript-first schema validation library used by the TypeScript MCP SDK for defining tool input schemas.
