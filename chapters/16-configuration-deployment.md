# Chapter 16: Configuration and Deployment

---

## 16.1 Configuring MCP Servers in Claude Desktop

Claude Desktop is one of the primary MCP hosts. It discovers and connects to MCP servers through a configuration file.

### 16.1.1 The `claude_desktop_config.json` Format

The configuration file is located at:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "database": {
      "command": "python",
      "args": ["/path/to/database_server.py"],
      "env": {
        "DB_PATH": "/data/production.db"
      }
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "ghp_xxxxxxxxxxxx"
      }
    },
    "filesystem": {
      "command": "node",
      "args": ["/path/to/filesystem-server/dist/index.js"],
      "env": {}
    }
  }
}
```

Each server entry has:
- **Key** (e.g., `"database"`): A unique name for the server
- **`command`**: The executable to run
- **`args`**: Command-line arguments passed to the executable
- **`env`** (optional): Environment variables set for the server process

### 16.1.2 Environment Variables and Arguments

Environment variables are the recommended way to pass sensitive configuration (API keys, database URLs, tokens) to MCP servers:

```json
{
  "mcpServers": {
    "slack": {
      "command": "python",
      "args": ["slack_server.py"],
      "env": {
        "SLACK_BOT_TOKEN": "xoxb-xxxx",
        "SLACK_WORKSPACE": "mycompany"
      }
    }
  }
}
```

The server reads these at startup:

```python
import os

SLACK_TOKEN = os.environ["SLACK_BOT_TOKEN"]
WORKSPACE = os.environ.get("SLACK_WORKSPACE", "default")
```

### 16.1.3 Managing Multiple Servers

You can configure any number of servers. Claude Desktop will launch and connect to all of them at startup:

```json
{
  "mcpServers": {
    "database": { "command": "python", "args": ["db_server.py"] },
    "github": { "command": "node", "args": ["github_server.js"] },
    "slack": { "command": "python", "args": ["slack_server.py"] },
    "filesystem": { "command": "node", "args": ["fs_server.js"] },
    "docker": { "command": "python", "args": ["docker_server.py"] }
  }
}
```

All tools from all servers appear as a unified set to Claude.

---

## 16.2 Configuring MCP Servers in Claude Code

Claude Code supports MCP server configuration at multiple levels:

**Project-level** (`.mcp.json` in the project root):

```json
{
  "mcpServers": {
    "database": {
      "command": "python",
      "args": ["tools/db_server.py"],
      "env": {
        "DB_PATH": "./data/dev.db"
      }
    }
  }
}
```

**User-level** (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "ghp_xxxx"
      }
    }
  }
}
```

Project-level configurations are scoped to the project directory. User-level configurations apply globally.

Claude Code can also connect to remote MCP servers:

```json
{
  "mcpServers": {
    "remote-tools": {
      "url": "https://mcp.example.com/sse"
    }
  }
}
```

---

## 16.3 Packaging MCP Servers for Distribution

### 16.3.1 npm Packages (TypeScript)

Publish your TypeScript MCP server as an npm package:

```json
{
  "name": "@myorg/mcp-server-database",
  "version": "1.0.0",
  "bin": {
    "mcp-server-database": "./dist/index.js"
  },
  "files": ["dist"],
  "scripts": {
    "build": "tsc",
    "prepublishOnly": "npm run build"
  }
}
```

Users install and configure it:

```json
{
  "mcpServers": {
    "database": {
      "command": "npx",
      "args": ["-y", "@myorg/mcp-server-database"],
      "env": {
        "DB_URL": "postgresql://localhost/mydb"
      }
    }
  }
}
```

The `npx -y` pattern downloads and runs the package without prior installation, making setup effortless for users.

### 16.3.2 PyPI Packages (Python)

Publish your Python MCP server as a PyPI package:

```toml
# pyproject.toml
[project]
name = "mcp-server-database"
version = "1.0.0"
dependencies = ["mcp[cli]>=1.0.0", "aiosqlite"]

[project.scripts]
mcp-server-database = "mcp_server_database:main"
```

Users install and configure:

```bash
pip install mcp-server-database
```

```json
{
  "mcpServers": {
    "database": {
      "command": "mcp-server-database",
      "env": {
        "DB_URL": "postgresql://localhost/mydb"
      }
    }
  }
}
```

Or with `uvx` for isolated execution:

```json
{
  "mcpServers": {
    "database": {
      "command": "uvx",
      "args": ["mcp-server-database"],
      "env": {
        "DB_URL": "postgresql://localhost/mydb"
      }
    }
  }
}
```

### 16.3.3 Docker Containers

Package your server as a Docker container for maximum isolation:

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENTRYPOINT ["python", "server.py"]
```

Configure with Docker:

```json
{
  "mcpServers": {
    "database": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "DB_URL",
        "myorg/mcp-server-database:latest"
      ],
      "env": {
        "DB_URL": "postgresql://host.docker.internal/mydb"
      }
    }
  }
}
```

The `-i` flag is essential — it keeps stdin open for the stdio transport. The `--rm` flag cleans up the container on exit.

---

## 16.4 Running MCP Servers in Production

### 16.4.1 Process Management and Supervision

For production deployments with network transports, use process managers:

**systemd (Linux):**

```ini
[Unit]
Description=MCP Database Server
After=network.target

[Service]
Type=simple
User=mcpserver
ExecStart=/usr/bin/python3 /opt/mcp/database_server.py
Restart=always
RestartSec=5
Environment=DB_URL=postgresql://localhost/production
Environment=MCP_TRANSPORT=streamable-http
Environment=MCP_PORT=3000

[Install]
WantedBy=multi-user.target
```

**Docker Compose:**

```yaml
version: '3.8'
services:
  mcp-database:
    build: ./servers/database
    ports:
      - "3001:3000"
    environment:
      - DB_URL=postgresql://db:5432/production
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  mcp-github:
    build: ./servers/github
    ports:
      - "3002:3000"
    environment:
      - GITHUB_TOKEN=${GITHUB_TOKEN}
    restart: unless-stopped
```

### 16.4.2 Health Checks and Monitoring

Add health check endpoints for network-based servers:

```python
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

async def health_check(request):
    return JSONResponse({
        "status": "healthy",
        "server": "database-server",
        "version": "1.0.0",
        "uptime_seconds": get_uptime()
    })

app = Starlette(routes=[
    Route("/health", health_check),
    Route("/mcp", handle_mcp, methods=["GET", "POST", "DELETE"]),
])
```

### 16.4.3 Scaling Strategies

**Horizontal scaling** for Streamable HTTP servers:

- Deploy multiple server instances behind a load balancer
- Use sticky sessions (based on `Mcp-Session-Id`) for stateful servers
- Use stateless mode for serverless deployment

**Vertical scaling:**
- Increase resources for CPU/memory-intensive tools
- Use connection pooling for database-backed servers
- Implement caching for frequently-accessed resources

---

## 16.5 MCP Server Registries and Discovery

As the MCP ecosystem grows, discoverability becomes important. Several approaches exist:

- **Official MCP server listings**: The MCP GitHub organization maintains a list of reference servers
- **npm/PyPI**: Searching for `mcp-server-*` packages on package registries
- **Community directories**: Websites and repositories that catalog available MCP servers
- **Smithery**: A registry specifically for MCP servers

When publishing a server, include:
- Clear documentation on what tools, resources, and prompts it provides
- Configuration examples for major hosts
- Environment variable documentation
- Security considerations

---

## Summary

Configuration and deployment are the last mile in making MCP servers useful. Whether you are configuring servers for personal use in Claude Desktop or deploying them as production services, the patterns are well-established.

Key takeaways:

- **Claude Desktop** uses `claude_desktop_config.json` with `command`, `args`, and `env` for each server
- **Claude Code** supports project-level (`.mcp.json`) and user-level configuration, plus remote URLs
- **npm packages** with `npx -y` provide zero-install setup for TypeScript servers
- **PyPI packages** with `uvx` provide isolated execution for Python servers
- **Docker containers** offer maximum isolation and reproducibility
- **Production deployment** needs process management, health checks, and monitoring
- **Scaling** depends on transport choice — Streamable HTTP supports horizontal scaling
- **Registries** help users discover available servers

This concludes Part IV. In Part V, we will move beyond individual servers to explore AI agents and multi-agent orchestration with MCP.
