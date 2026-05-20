<!-- Source: derived from orchid-frontend/AGENTS.md, orchid-website/src/content/packages/orchid-frontend.mdx, and codebase analysis -->

# NextAuth Integration

The frontend uses NextAuth v5 for OAuth/OIDC authentication with a token proxy pattern that keeps bearer tokens out of the browser.

## NextAuth v5 Configuration

```typescript
// src/lib/auth.ts
import NextAuth from "next-auth";

export const { auth, handlers, signIn, signOut } = NextAuth({
  providers: [
    {
      id: "orchid",
      name: "Orchid",
      type: "oidc",
      issuer: process.env.OIDC_ISSUER,
      clientId: process.env.OIDC_CLIENT_ID,
      clientSecret: process.env.OIDC_CLIENT_SECRET,
      authorization: {
        params: { scope: "openid profile email" },
      },
    },
  ],
  callbacks: {
    async jwt({ token, account }) {
      if (account) {
        token.accessToken = account.access_token;
        token.refreshToken = account.refresh_token;
      }
      return token;
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken;
      return session;
    },
  },
});
```

## Token Proxy Pattern

The frontend never exposes bearer tokens to the browser:

```
Browser → Server Action → orchid-api (with server-side token)
```

### Why Token Proxy?

1. **Security** — Bearer tokens never reach client-side JavaScript.
2. **CORS** — Server-to-server requests don't have CORS issues.
3. **Token refresh** — Refresh happens server-side, invisible to the user.
4. **Session management** — Browser only has a session cookie.

### Implementation

```typescript
// src/app/actions.ts
"use server";

import { auth } from "@/lib/auth";
import { orchidAPI } from "@/lib/api";

export async function sendMessage(chatId: string, message: string) {
  const session = await auth();
  return orchidAPI.sendMessage(chatId, message, session.accessToken);
}
```

## OIDC Discovery

NextAuth auto-discovers OIDC endpoints from the issuer:

```
GET https://auth.example.com/.well-known/openid-configuration
```

Returns authorization, token, userinfo, and JWKS endpoints automatically.

## Session Management

Sessions are stored server-side with a cookie in the browser:

```typescript
// Check auth in server components
import { auth } from "@/lib/auth";

export default async function ChatPage() {
  const session = await auth();
  if (!session) redirect("/api/auth/signin");
  // ...
}
```

## API Route Handlers

NextAuth API routes are mounted at `/api/auth/[...nextauth]`:

```
GET  /api/auth/signin       Sign-in page
POST /api/auth/signin       Sign-in handler
POST /api/auth/signout      Sign-out handler
GET  /api/auth/session       Get current session
GET  /api/auth/callback/{provider}  OAuth callback
```
