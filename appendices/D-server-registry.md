# Appendix D: MCP Server Registry — Notable Servers

---

## Official Reference Servers

These servers are maintained by Anthropic or the MCP organization:

| Server | Package | Description |
|--------|---------|-------------|
| Filesystem | `@modelcontextprotocol/server-filesystem` | Read, write, and search files |
| GitHub | `@modelcontextprotocol/server-github` | GitHub API integration |
| GitLab | `@modelcontextprotocol/server-gitlab` | GitLab API integration |
| Google Drive | `@modelcontextprotocol/server-gdrive` | Google Drive file access |
| PostgreSQL | `@modelcontextprotocol/server-postgres` | PostgreSQL database access |
| SQLite | `@modelcontextprotocol/server-sqlite` | SQLite database access |
| Slack | `@modelcontextprotocol/server-slack` | Slack workspace integration |
| Memory | `@modelcontextprotocol/server-memory` | Persistent key-value memory |
| Puppeteer | `@modelcontextprotocol/server-puppeteer` | Browser automation |
| Brave Search | `@modelcontextprotocol/server-brave-search` | Web search via Brave |
| Google Maps | `@modelcontextprotocol/server-google-maps` | Location and mapping |
| Sentry | `@modelcontextprotocol/server-sentry` | Error tracking |
| Fetch | `@modelcontextprotocol/server-fetch` | HTTP fetching and scraping |
| Everything | `@modelcontextprotocol/server-everything` | Reference/test server |

## Community Servers by Category

### Databases
- PostgreSQL, MySQL, SQLite, MongoDB, Redis, Elasticsearch, Supabase, Neon

### Cloud & Infrastructure
- AWS, Google Cloud, Azure, Cloudflare, Vercel, Docker, Kubernetes, Terraform

### Communication
- Slack, Discord, Email (IMAP/SMTP), Microsoft Teams

### Development
- GitHub, GitLab, Jira, Linear, Notion, Confluence

### Search & Web
- Brave Search, Google Search, Bing, web scraping, Puppeteer

### AI & ML
- Hugging Face, vector databases (Pinecone, Weaviate, Qdrant)

### File & Storage
- Local filesystem, S3, Google Drive, Dropbox, FTP

### Monitoring
- Sentry, Datadog, Grafana, PagerDuty, Prometheus

## Publishing Your Own Server

### npm (TypeScript)
```bash
npm publish --access public
```

### PyPI (Python)
```bash
uv build && uv publish
```

### Naming Convention
- npm: `@your-org/mcp-server-<name>` or `mcp-server-<name>`
- PyPI: `mcp-server-<name>`
