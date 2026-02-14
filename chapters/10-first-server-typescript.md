# Chapter 10: Your First MCP Server — TypeScript

---

## 10.1 Setting Up the Development Environment

TypeScript is the other officially supported language for MCP development. The TypeScript SDK was the first MCP SDK and is used extensively in the ecosystem.

### Prerequisites

- **Node.js 18 or later**: The TypeScript SDK requires a modern Node.js runtime
- **npm, yarn, or pnpm**: Any Node.js package manager works

### Creating a Project

```bash
mkdir my-mcp-server
cd my-mcp-server
npm init -y
npm install @modelcontextprotocol/sdk zod
npm install -D typescript @types/node tsx
```

Create a `tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "Node16",
    "moduleResolution": "Node16",
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*"]
}
```

### Project Structure

```
my-mcp-server/
├── package.json
├── tsconfig.json
└── src/
    └── index.ts       # Your MCP server
```

---

## 10.2 The TypeScript MCP SDK: Overview and Installation

The TypeScript SDK (`@modelcontextprotocol/sdk`) provides:

| Component | Purpose |
|-----------|---------|
| `McpServer` | High-level server API (recommended) |
| `Server` | Low-level server API |
| `Client` | Client for connecting to MCP servers |
| `StdioServerTransport` | stdio transport for servers |
| `SSEServerTransport` | SSE transport for servers |
| `StreamableHTTPServerTransport` | Streamable HTTP transport |
| `zod` integration | Schema validation using Zod |

```bash
npm install @modelcontextprotocol/sdk zod
```

---

## 10.3 The `McpServer` High-Level API

`McpServer` is the TypeScript equivalent of Python's `FastMCP`. It provides a clean API for defining tools, resources, and prompts.

```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const server = new McpServer({
  name: "my-server",
  version: "1.0.0"
});

// ... define tools, resources, prompts ...

const transport = new StdioServerTransport();
await server.connect(transport);
```

---

## 10.4 Building a Simple Tool Server

### 10.4.1 Defining Tools with `server.tool()`

```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer({
  name: "weather-server",
  version: "1.0.0"
});

server.tool(
  "get_weather",
  "Get the current weather for a city",
  {
    city: z.string().describe("The city name"),
    units: z.enum(["celsius", "fahrenheit"]).default("celsius")
      .describe("Temperature units")
  },
  async ({ city, units }) => {
    // In a real server, call a weather API
    const temp = units === "celsius" ? "22°C" : "72°F";
    return {
      content: [
        {
          type: "text" as const,
          text: `The weather in ${city} is ${temp}, partly cloudy.`
        }
      ]
    };
  }
);

const transport = new StdioServerTransport();
await server.connect(transport);
```

The `server.tool()` method takes:
1. **Tool name**: A string identifier
2. **Description**: What the tool does
3. **Schema**: A Zod schema object defining the parameters
4. **Handler**: An async function that receives the validated parameters

### 10.4.2 Input Validation with Zod Schemas

The TypeScript SDK uses **Zod** for schema definitions. Zod is a TypeScript-first schema validation library that generates JSON Schema automatically.

```typescript
// Simple types
{
  name: z.string(),
  age: z.number().int().min(0),
  active: z.boolean().default(true)
}

// Complex types
{
  query: z.string().describe("SQL query to execute"),
  database: z.string().default("main").describe("Target database"),
  timeout: z.number().min(1).max(300).default(30)
    .describe("Query timeout in seconds"),
  format: z.enum(["table", "json", "csv"]).default("table")
    .describe("Output format")
}

// Nested objects
{
  issue: z.object({
    title: z.string(),
    body: z.string().optional(),
    labels: z.array(z.string()).default([])
  })
}
```

Zod schemas are automatically converted to JSON Schema for the MCP tool definition.

### 10.4.3 Connecting via stdio Transport

```typescript
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const transport = new StdioServerTransport();
await server.connect(transport);
```

This is the most common setup for local MCP servers. The server reads from stdin and writes to stdout.

### 10.4.4 Testing Your Server

**With the MCP Inspector:**

```bash
npx @modelcontextprotocol/inspector node dist/index.js
```

Or during development with tsx:

```bash
npx @modelcontextprotocol/inspector npx tsx src/index.ts
```

---

## 10.5 Adding Resources

### 10.5.1 Static Resources with `server.resource()`

```typescript
server.resource(
  "app-config",
  "config://app/settings",
  "Current application configuration",
  "application/json",
  async () => ({
    contents: [
      {
        uri: "config://app/settings",
        mimeType: "application/json",
        text: JSON.stringify({
          debug: false,
          maxConnections: 20,
          logLevel: "info"
        }, null, 2)
      }
    ]
  })
);
```

Parameters:
1. **Resource key**: An internal identifier
2. **URI**: The resource URI
3. **Description**: What the resource provides
4. **MIME type**: Content type
5. **Handler**: Async function returning the resource content

### 10.5.2 Dynamic Resources with URI Templates

```typescript
server.resource(
  "table-schema",
  "db://{database}/{table}/schema",
  "Schema for a specific database table",
  "application/json",
  async (uri, { database, table }) => ({
    contents: [
      {
        uri: uri.href,
        mimeType: "application/json",
        text: JSON.stringify(await getTableSchema(database, table), null, 2)
      }
    ]
  })
);
```

The template variables are automatically extracted and passed to the handler.

---

## 10.6 Adding Prompts

```typescript
server.prompt(
  "code_review",
  "Review code for quality and potential issues",
  {
    language: z.string().default("typescript").describe("Programming language"),
    focus: z.enum(["security", "performance", "style", "all"]).default("all")
      .describe("Area to focus on")
  },
  async ({ language, focus }) => ({
    messages: [
      {
        role: "user" as const,
        content: {
          type: "text" as const,
          text: `You are an expert ${language} code reviewer. Focus on ${focus} issues. For each issue found, provide severity, location, description, and fix.`
        }
      }
    ]
  })
);
```

---

## 10.7 The Low-Level `Server` API

For advanced use cases, the low-level `Server` class provides direct access to request handlers:

```typescript
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  ListToolsRequestSchema,
  CallToolRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const server = new Server(
  { name: "low-level-server", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "greet",
      description: "Generate a greeting",
      inputSchema: {
        type: "object",
        properties: {
          name: { type: "string", description: "Name to greet" }
        },
        required: ["name"]
      }
    }
  ]
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name === "greet") {
    return {
      content: [
        { type: "text", text: `Hello, ${request.params.arguments?.name}!` }
      ]
    };
  }
  throw new Error(`Unknown tool: ${request.params.name}`);
});
```

### 10.7.1 Request Handlers

The low-level API uses `setRequestHandler` with typed schemas:

| Schema | Purpose |
|--------|---------|
| `ListToolsRequestSchema` | Handle `tools/list` |
| `CallToolRequestSchema` | Handle `tools/call` |
| `ListResourcesRequestSchema` | Handle `resources/list` |
| `ReadResourceRequestSchema` | Handle `resources/read` |
| `ListPromptsRequestSchema` | Handle `prompts/list` |
| `GetPromptRequestSchema` | Handle `prompts/get` |

### 10.7.2 When to Use Low-Level vs. High-Level

Same guidance as Python: use `McpServer` for most cases, use `Server` when you need full control over protocol handling, custom middleware, or integration with existing frameworks.

---

## 10.8 Error Handling and Logging

```typescript
server.tool(
  "query",
  "Execute a SQL query",
  { sql: z.string() },
  async ({ sql }) => {
    try {
      const results = await executeQuery(sql);
      return {
        content: [{ type: "text" as const, text: formatResults(results) }]
      };
    } catch (error) {
      return {
        content: [{ type: "text" as const, text: `Error: ${error.message}` }],
        isError: true
      };
    }
  }
);
```

For logging, use stderr (not stdout — stdout is reserved for MCP messages):

```typescript
console.error("Server started");  // Goes to stderr
```

---

## 10.9 Complete Example: A File System MCP Server

```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import * as fs from "fs/promises";
import * as path from "path";
import { glob } from "glob";

const server = new McpServer({
  name: "filesystem-server",
  version: "1.0.0"
});

// ─── Tools ───────────────────────────────────────────────

server.tool(
  "read_file",
  "Read the contents of a file at the given path",
  {
    path: z.string().describe("Absolute path to the file")
  },
  async ({ path: filePath }) => {
    try {
      const content = await fs.readFile(filePath, "utf-8");
      return {
        content: [{ type: "text" as const, text: content }]
      };
    } catch (error: any) {
      return {
        content: [{ type: "text" as const, text: `Error: ${error.message}` }],
        isError: true
      };
    }
  }
);

server.tool(
  "write_file",
  "Write content to a file (creates or overwrites)",
  {
    path: z.string().describe("Absolute path to the file"),
    content: z.string().describe("Content to write")
  },
  async ({ path: filePath, content }) => {
    try {
      await fs.mkdir(path.dirname(filePath), { recursive: true });
      await fs.writeFile(filePath, content, "utf-8");
      return {
        content: [{
          type: "text" as const,
          text: `Written ${content.length} characters to ${filePath}`
        }]
      };
    } catch (error: any) {
      return {
        content: [{ type: "text" as const, text: `Error: ${error.message}` }],
        isError: true
      };
    }
  }
);

server.tool(
  "search_files",
  "Search for files matching a glob pattern",
  {
    pattern: z.string().describe("Glob pattern (e.g., '**/*.ts')"),
    directory: z.string().default(".").describe("Root directory to search in")
  },
  async ({ pattern, directory }) => {
    try {
      const matches = await glob(pattern, { cwd: directory, absolute: true });
      const text = matches.length > 0
        ? matches.join("\n")
        : "No files found matching the pattern.";
      return {
        content: [{ type: "text" as const, text }]
      };
    } catch (error: any) {
      return {
        content: [{ type: "text" as const, text: `Error: ${error.message}` }],
        isError: true
      };
    }
  }
);

server.tool(
  "list_directory",
  "List contents of a directory",
  {
    path: z.string().describe("Absolute path to the directory")
  },
  async ({ path: dirPath }) => {
    try {
      const entries = await fs.readdir(dirPath, { withFileTypes: true });
      const lines = entries.map(e =>
        `${e.isDirectory() ? "[DIR]" : "[FILE]"} ${e.name}`
      );
      return {
        content: [{
          type: "text" as const,
          text: `Contents of ${dirPath}:\n\n${lines.join("\n")}`
        }]
      };
    } catch (error: any) {
      return {
        content: [{ type: "text" as const, text: `Error: ${error.message}` }],
        isError: true
      };
    }
  }
);

// ─── Resources ───────────────────────────────────────────

server.resource(
  "cwd",
  "file://cwd",
  "Current working directory path",
  "text/plain",
  async () => ({
    contents: [{
      uri: "file://cwd",
      mimeType: "text/plain",
      text: process.cwd()
    }]
  })
);

// ─── Start ───────────────────────────────────────────────

const transport = new StdioServerTransport();
await server.connect(transport);
console.error("Filesystem MCP server running on stdio");
```

### Running and Configuring

```bash
# Build
npx tsc

# Run directly
node dist/index.js

# Test with Inspector
npx @modelcontextprotocol/inspector node dist/index.js

# Configure in Claude Desktop (claude_desktop_config.json)
```

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "node",
      "args": ["/path/to/dist/index.js"]
    }
  }
}
```

---

## Summary

The TypeScript SDK provides a parallel experience to the Python SDK, with Zod replacing type annotations for schema generation.

Key takeaways:

- **`McpServer`** is the high-level API, equivalent to Python's `FastMCP`
- **Zod schemas** define tool inputs with automatic JSON Schema generation
- **`server.tool()`**, **`server.resource()`**, and **`server.prompt()`** define capabilities
- **`StdioServerTransport`** is the standard transport for local servers
- **The low-level `Server`** class provides full protocol control
- **Error handling** uses try/catch with `isError: true` for tool-level failures
- **Testing** works with the MCP Inspector (`npx @modelcontextprotocol/inspector`)
- Both SDKs produce protocol-compatible servers — a Python client can talk to a TypeScript server and vice versa

In the next chapter, we will explore transport implementation in detail — how to set up SSE and Streamable HTTP servers for network-accessible MCP services.
