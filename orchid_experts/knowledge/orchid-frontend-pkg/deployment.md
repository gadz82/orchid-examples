<!-- Source: derived from orchid-frontend/README.md, orchid-website/src/content/packages/orchid-frontend.mdx, and codebase analysis -->

# Frontend Deployment

Guidelines for deploying the Orchid frontend in production. The frontend is a Next.js 15 application that can be deployed to Vercel, Docker, or any Node.js hosting platform.

## Fork Checklist

Before deploying, customize these items:

1. **Brand colors** — Update the orchid palette in `src/app/globals.css` (via `@theme inline`).
2. **Logo and favicon** — Replace `public/logo.svg` and `public/favicon.ico`.
3. **Metadata** — Update title, description, and OG tags in `src/app/layout.tsx`.
4. **NextAuth** — Configure your OIDC provider in `src/lib/auth.ts`.
5. **API URL** — Set `ORCHID_API_URL` in environment variables.
6. **Custom components** — Add or customize React components as needed.

## Environment Variables

```bash
# Required
ORCHID_API_URL=https://api.orchid.example.com
NEXTAUTH_URL=https://chat.orchid.example.com
AUTH_SECRET=${AUTH_SECRET}            # NextAuth encryption key (openssl rand -base64 32)

# OIDC Provider
OIDC_ISSUER=https://auth.example.com
OIDC_CLIENT_ID=my-frontend
OIDC_CLIENT_SECRET=${OIDC_CLIENT_SECRET}

# Optional
NEXT_PUBLIC_APP_NAME="Orchid Chat"
NEXT_PUBLIC_APP_DESCRIPTION="Multi-agent AI chat interface"
NEXT_PUBLIC_LOGO_URL="/logo.svg"
```

## Docker Deployment

```dockerfile
# Dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

```yaml
# docker-compose.yml
services:
  frontend:
    build: .
    ports:
      - "3000:3000"
    environment:
      - ORCHID_API_URL=http://api:8000
      - NEXTAUTH_URL=http://localhost:3000
      - OIDC_ISSUER=https://auth.example.com
      - OIDC_CLIENT_ID=${OIDC_CLIENT_ID}
      - OIDC_CLIENT_SECRET=${OIDC_CLIENT_SECRET}
      - AUTH_SECRET=${AUTH_SECRET}
```

## Static Export (Limited)

For static hosting (S3, Cloudflare Pages, GitHub Pages):

```js
// next.config.js
module.exports = {
  output: "export",
};
```

**Limitations of static export:**
- No server actions (must use API routes or client-side fetch).
- No NextAuth server-side (must use client-side auth or hosted auth service).
- No SSE streaming proxy (must connect to API SSE endpoint directly from browser).

Static export is suitable for documentation sites or demos without authentication. For production chat UIs, use the server runtime.

## Reverse Proxy

Run behind Nginx or Caddy with TLS termination:

```nginx
# nginx.conf
server {
    listen 443 ssl http2;
    server_name chat.example.com;

    ssl_certificate /etc/ssl/certs/chat.example.com.crt;
    ssl_certificate_key /etc/ssl/private/chat.example.com.key;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
```

## Health Checks

The frontend doesn't have a dedicated health endpoint but you can check:

```bash
# The home page loads (returns 200)
curl -I https://chat.example.com

# Server-side rendering works
curl https://chat.example.com | grep -q "Orchid Chat"
```

## Build and Start

```bash
# Development
npm run dev          # http://localhost:3000 (Turbopack)

# Production build
npm run build        # Lint + typecheck + next build
npm start            # Port 3000

# Lint and test
npm run lint         # ESLint
npm test             # Vitest
```

## Custom Branding (Full Fork)

For complete rebranding:

1. Fork the `orchid-frontend` repository.
2. Create a new Git repository for your fork.
3. Update `package.json`: name, description, repository URL.
4. Update `globals.css`: brand colors, fonts, radii.
5. Replace `public/logo.svg` and `public/favicon.ico`.
6. Update `src/app/layout.tsx`: title, metadata, OG tags.
7. Configure your OIDC provider in `src/lib/auth.ts`.
8. Add custom components or modify existing ones.
9. Deploy as your own branded application.

## Monitoring

- Track page load time and Core Web Vitals.
- Monitor SSE connection drops and reconnection success rate.
- Track client-side errors (via Sentry or similar).
- Monitor API latency from the frontend's perspective.
