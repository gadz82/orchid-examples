<!-- Source: derived from orchid-api/AGENTS.md, orchid-website/src/content/packages/orchid-api.mdx, and codebase analysis -->

# Endpoints

The Orchid API exposes a comprehensive set of REST endpoints organized by domain-specific routers.

## Chat Endpoints

```
GET    /chats                          List chats for authenticated user
POST   /chats                          Create a new chat session
GET    /chats/{chat_id}                Get chat details
DELETE /chats/{chat_id}                Delete a chat and its messages
PATCH  /chats/{chat_id}                Update chat title or metadata
```

## Message Endpoints

```
POST   /chats/{chat_id}/messages       Send a message (supports multipart file upload)
GET    /chats/{chat_id}/messages       Get messages (with pagination: ?limit=50&offset=0)
```

### Multipart Upload

The `POST /chats/{chat_id}/messages` endpoint accepts `multipart/form-data`:

```
POST /chats/abc123/messages
Content-Type: multipart/form-data

--boundary
Content-Disposition: form-data; name="message"

What's in this document?
--boundary
Content-Disposition: form-data; name="file"; filename="report.pdf"

<binary data>
--boundary--
```

## Streaming Endpoints

```
GET    /chats/{chat_id}/stream         SSE stream for chat messages
GET    /events/stream                  SSE stream for Bloom events
```

## Auth Endpoints

```
GET    /auth/info                      Get OAuth discovery information
POST   /auth/exchange-code             Exchange authorization code for tokens
POST   /auth/token                     Refresh token exchange
GET    /auth/resolve-identity           Bridge upstream token to Orchid identity
```

## Admin Endpoints

```
POST   /index                          Index documents into RAG
GET    /index/status/{job_id}          Check indexing job status
```

## Diagnostics

```
GET    /health                         Health check (graph ready, DB connected)
GET    /diagnostics/config             Current configuration (sanitized)
```

## MCP Gateway Endpoints

```
GET    /mcp-gateway/.well-known/oauth-authorization-server    OAuth server metadata
POST   /mcp-gateway/register           Dynamic client registration
POST   /mcp-gateway/authorize          Authorization endpoint
POST   /mcp-gateway/token              Token endpoint
```

## Session Warming

```
POST   /session/warm                   Warm MCP capabilities for current session
```

## Sharing

```
POST   /chats/{chat_id}/share          Share a chat (generates share link)
GET    /shared/{share_token}           Access a shared chat
```

## Pagination

List endpoints support pagination:

```
GET /chats?limit=10&offset=0
GET /chats/{id}/messages?limit=50&offset=0
```

## Error Responses

Standard HTTP status codes:

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad request / validation error |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not found |
| 413 | File too large |
| 422 | Unprocessable entity |
| 500 | Internal server error |
