# Appendix B: JSON-RPC 2.0 Quick Reference

---

## Message Formats

### Request

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "method_name",
  "params": { ... }
}
```

### Success Response

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": { ... }
}
```

### Error Response

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32600,
    "message": "Invalid Request",
    "data": { ... }
  }
}
```

### Notification (no response)

```json
{
  "jsonrpc": "2.0",
  "method": "notification_name",
  "params": { ... }
}
```

## Error Code Ranges

| Range | Category |
|-------|----------|
| `-32700` | Parse error |
| `-32600` | Invalid Request |
| `-32601` | Method not found |
| `-32602` | Invalid params |
| `-32603` | Internal error |
| `-32000` to `-32099` | Server/implementation-defined errors |

## MCP-Specific Error Codes

| Code | Meaning |
|------|---------|
| `-32001` | Resource not found |
| `-32002` | Tool not found |

## Rules

1. `jsonrpc` field MUST be `"2.0"`
2. `id` MUST be unique per session (string or integer)
3. Response `id` MUST match request `id`
4. Response MUST have `result` OR `error`, never both
5. Notifications have NO `id` field and get NO response
6. Batch: wrap messages in a JSON array
