<!-- Source: derived from orchid-frontend/AGENTS.md, orchid-frontend/README.md, orchid-website/src/content/packages/orchid-frontend.mdx, and codebase analysis -->

# Architecture

The `orchid-frontend` is a Next.js 15 multi-chat web UI that connects to `orchid-api` over HTTP. It provides a complete chat interface with streaming, file upload, and Bloom event monitoring.

## Tech Stack

- **Next.js 15** — App Router, React Server Components, Server Actions.
- **TypeScript** — Strict mode.
- **Tailwind CSS v4** — `@theme inline` in `globals.css`.
- **NextAuth v5** — OAuth/OIDC authentication with token proxy pattern.
- **Vitest** — Component testing.

## Directory Structure

```
orchid-frontend/
├── src/
│   ├── app/                 # Next.js App Router pages
│   │   ├── layout.tsx       # Root layout
│   │   ├── page.tsx         # Home / redirect
│   │   ├── chat/
│   │   │   ├── [id]/        # Individual chat page
│   │   │   └── new/         # New chat page
│   │   └── api/
│   │       └── auth/        # NextAuth API routes
│   ├── components/          # React components
│   │   ├── ChatSidebar      # Chat list sidebar
│   │   ├── ChatInput        # Message input with file upload
│   │   ├── MessageBubble    # Chat message display
│   │   ├── HITLCard         # Human-in-the-loop approval card
│   │   ├── BloomPanel       # Bloom run monitoring
│   │   └── MiniAgentTrace   # Mini-agent execution trace
│   ├── lib/                 # Utilities and hooks
│   │   ├── api.ts           # Orchid API client
│   │   ├── auth.ts          # NextAuth configuration
│   │   ├── sse.ts           # SSE stream consumer
│   │   └── use-chat-stream.ts # Streaming hook
│   └── styles/
│       └── globals.css      # Tailwind + Orchid palette
├── public/
├── Dockerfile
└── package.json
```

## Component Tree

```
RootLayout
├── Header (nav bar)
├── Sidebar (chat list)
│   └── ChatListItem[]
└── ChatPage
    ├── MessageList
    │   ├── MessageBubble[]
    │   ├── HITLCard (if approval needed)
    │   └── MiniAgentTrace (if mini-agents used)
    ├── BloomPanel (if bloom events active)
    └── ChatInput (with file upload)
```

## API Communication

The frontend communicates with `orchid-api` via:

- **Server Actions** — For mutations (create chat, send message).
- **SSE** — For real-time streaming (token-by-token responses).
- **HTTP (fetch)** — For queries (list chats, get messages).

### Token Proxy Pattern

The frontend never sends bearer tokens directly to the API. Instead:

1. NextAuth manages the OAuth session server-side.
2. Server actions proxy requests to the API with the server-side token.
3. The browser only has a session cookie, never an access token.
