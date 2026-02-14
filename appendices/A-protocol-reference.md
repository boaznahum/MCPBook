# Appendix A: MCP Protocol Reference

---

## Request Methods

### Client → Server

| Method | Purpose | Params |
|--------|---------|--------|
| `initialize` | Initialize connection | `protocolVersion`, `capabilities`, `clientInfo` |
| `ping` | Health check | None |
| `tools/list` | List available tools | `cursor?` |
| `tools/call` | Invoke a tool | `name`, `arguments`, `_meta?` |
| `resources/list` | List resources | `cursor?` |
| `resources/templates/list` | List resource templates | `cursor?` |
| `resources/read` | Read a resource | `uri` |
| `resources/subscribe` | Subscribe to changes | `uri` |
| `resources/unsubscribe` | Unsubscribe from changes | `uri` |
| `prompts/list` | List prompts | `cursor?` |
| `prompts/get` | Get prompt content | `name`, `arguments?` |
| `logging/setLevel` | Set server log level | `level` |
| `completion/complete` | Request autocompletion | `ref`, `argument` |

### Server → Client

| Method | Purpose | Params |
|--------|---------|--------|
| `sampling/createMessage` | Request AI completion | `messages`, `maxTokens`, `modelPreferences?`, `systemPrompt?`, `temperature?`, `includeContext?` |
| `roots/list` | Get root URIs | None |
| `ping` | Health check | None |

## Notifications

### Client → Server

| Method | Purpose |
|--------|---------|
| `notifications/initialized` | Initialization complete |
| `notifications/cancelled` | Cancel a request |
| `notifications/progress` | Report progress |
| `notifications/roots/list_changed` | Root list changed |

### Server → Client

| Method | Purpose |
|--------|---------|
| `notifications/cancelled` | Cancel a request |
| `notifications/progress` | Report progress |
| `notifications/tools/list_changed` | Tool list changed |
| `notifications/resources/list_changed` | Resource list changed |
| `notifications/resources/updated` | Subscribed resource changed |
| `notifications/prompts/list_changed` | Prompt list changed |
| `notifications/message` | Log message |

## Capabilities

### Client Capabilities

```json
{
  "roots": { "listChanged": true },
  "sampling": {}
}
```

### Server Capabilities

```json
{
  "tools": { "listChanged": true },
  "resources": { "subscribe": true, "listChanged": true },
  "prompts": { "listChanged": true },
  "logging": {}
}
```

## Content Types

| Type | Fields |
|------|--------|
| `text` | `type: "text"`, `text: string` |
| `image` | `type: "image"`, `data: string (base64)`, `mimeType: string` |
| `resource` | `type: "resource"`, `resource: { uri, mimeType?, text?, blob? }` |

## Tool Annotations

| Annotation | Type | Default | Meaning |
|-----------|------|---------|---------|
| `readOnlyHint` | boolean | `false` | Tool only reads data |
| `destructiveHint` | boolean | `true` | Tool may perform irreversible actions |
| `idempotentHint` | boolean | `false` | Repeated calls produce same result |
| `openWorldHint` | boolean | `true` | Tool interacts with external systems |
