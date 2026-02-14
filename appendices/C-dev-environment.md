# Appendix C: Setting Up Your Development Environment

---

## Python Setup

### Install Python 3.10+

```bash
# macOS
brew install python@3.12

# Ubuntu/Debian
sudo apt install python3.12 python3.12-venv

# Windows
# Download from python.org
```

### Install uv (Recommended Package Manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Create an MCP Server Project

```bash
mkdir my-mcp-server && cd my-mcp-server
uv init
uv add "mcp[cli]"
```

### Run the MCP Inspector

```bash
mcp dev server.py
```

---

## TypeScript/Node.js Setup

### Install Node.js 18+

```bash
# macOS
brew install node

# Using nvm
nvm install 18
nvm use 18
```

### Create an MCP Server Project

```bash
mkdir my-mcp-server && cd my-mcp-server
npm init -y
npm install @modelcontextprotocol/sdk zod
npm install -D typescript @types/node tsx
npx tsc --init
```

### Run the MCP Inspector

```bash
npx @modelcontextprotocol/inspector node dist/index.js
```

---

## Claude Desktop Configuration

Configuration file locations:

| OS | Path |
|----|------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

Minimal configuration:

```json
{
  "mcpServers": {
    "my-server": {
      "command": "python",
      "args": ["/absolute/path/to/server.py"]
    }
  }
}
```

---

## Claude Code Configuration

Project-level (`.mcp.json` in project root):

```json
{
  "mcpServers": {
    "my-server": {
      "command": "python",
      "args": ["server.py"]
    }
  }
}
```

---

## MCP Inspector

The Inspector is a web-based debugging tool:

```bash
# For Python servers
mcp dev server.py

# For Node.js servers
npx @modelcontextprotocol/inspector node server.js

# For any command
npx @modelcontextprotocol/inspector <command> [args...]
```

Features:
- List and invoke tools interactively
- Browse and read resources
- List and expand prompts
- View raw JSON-RPC messages
- Monitor server notifications and logs
