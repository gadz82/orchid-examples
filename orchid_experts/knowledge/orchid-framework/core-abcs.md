<!-- Source: derived from orchid/AGENTS.md, orchid/README.md, orchid-website/src/content/packages/orchid.mdx, and codebase analysis -->

# Core ABCs

The `orchid_ai/core/` module defines the abstract base classes (ABCs) that form the foundation of the entire Orchid framework. This is the architectural leaf: `core/` has **zero external dependencies** beyond Python stdlib and `langchain-core` (for `Document` and message types). Every other module in the framework depends on `core/` — never the reverse.

## The Zero-Dependency Rule

`core/` imports only the Python standard library and `langchain-core`. No concrete backend imports (`qdrant_client`, `asyncpg`, `litellm`, `aiosqlite`) are allowed. This boundary is strictly enforced — violating it is an architectural bug.

The dependency direction flows one way:

```
graph/ → agents/ → core/
         agents/ → rag/ → core/
         agents/ → mcp/ → core/
persistence/ → core/  (standalone)
documents/   → core/  (standalone)
```

## OrchidAgent

**File:** `core/agent.py`

The primary agent identity. Every concrete agent in Orchid inherits from `OrchidAgent`. It defines:

- **`name`** (property) — The agent's unique identifier, used in routing and logging.
- **`description`** (property) — Short description read by the supervisor for routing decisions.
- **`run(state)`** — The main execution method. Receives `OrchidAgentState` and returns a dict with `messages`.
- **`summarise(query, rag_data, conversation_history, prior_tool_context)`** — Synthesizes a response using the injected LLM. Accepts RAG context, conversation history, and prior tool results.
- **`fetch_rag_context(query, scope)`** — Retrieves relevant documents from the vector store using an `OrchidRAGScope`.
- **`extract_user_query(state)`** — Extracts the clean user message from graph state (filters supervisor noise).
- **`extract_conversation_history(state)`** — Extracts clean dialogue from graph state, respecting `history_max_turns` and `history_max_chars` limits.

Consumer agents subclass `OrchidAgent` and override `run()`. They inherit `summarise()`, `fetch_rag_context()`, `extract_user_query()`, and `extract_conversation_history()` — these should never be duplicated.

## OrchidAuthContext

**File:** `core/state.py`

The authenticated identity context carried through the graph. Contains:

- **`tenant_key`** — The tenant identifier (from `auth.tenant_key`, defaults to `"default"` if null).
- **`user_id`** — The authenticated user identifier.
- **`bearer_header`** — The original bearer token (for passthrough auth to MCP servers).
- **`access_token`** — The resolved access token.

`OrchidAuthContext` is subclass-friendly: no `__slots__`, no `frozen=True`. Consumer subclasses add fields freely. Framework code uses only the base interface.

## OrchidAgentState

**File:** `core/state.py`

The state dictionary passed between LangGraph nodes. Contains messages, auth context, tool results, RAG data, and orchestrator state. Typed as a dict with well-known keys.

## OrchidIdentityResolver

**File:** `core/identity.py`

Resolves bearer tokens to `OrchidAuthContext`. Defines:

- **`resolve(domain, bearer_token)`** — Validates a bearer token and returns an `OrchidAuthContext`.
- **`resolve_service_account(name)`** — Resolves a named service account identity. Raises `OrchidServiceAccountUnknownError` if unknown.
- **`mint_for_user(tenant_key, user_id)`** — Mints a new auth context for a known user (used by `act_as_user` Bloom identity mode). Raises `OrchidIdentityNotMintableError` if the user is not seeded.

The resolver does double-duty: per-request bearer validation AND the upstream-token → identity bridge exposed at `/auth/resolve-identity`.

## OrchidAuthConfigProvider

**File:** `core/auth_config.py`

Resolves non-secret upstream-OAuth discovery configuration (`OrchidUpstreamOAuthConfig`) consumed by the API's `/auth-info` endpoint. Pure config resolution: no network calls, no side effects. Reads environment variables seeded from `orchid.yml`.

## OrchidAuthExchangeClient

**File:** `core/auth_config.py`

Holds the upstream `client_secret` and performs authorization-code (`exchange_code`) and refresh-token (`refresh_token`) grants on behalf of downstream public PKCE clients. The default `refresh_token` raises `NotImplementedError` — exchange-only consumers don't break.

## OrchidMCPToolCaller / OrchidMCPDiscoverable

**File:** `core/mcp.py`

Two narrow ABCs for MCP interaction (Interface Segregation Principle):

- **`OrchidMCPToolCaller`** — `call_tool(name, args, auth)` — Call MCP tools. Code that only calls tools depends on this.
- **`OrchidMCPDiscoverable`** — `list_tools(auth)`, `list_prompts(auth)`, `list_resources(auth)` — Discover MCP server capabilities. Code that discovers capabilities depends on this.

`OrchidMCPClient` combines both for backward compatibility.

## OrchidMCPTokenStore / OrchidMCPClientRegistrationStore

**File:** `core/mcp.py`

- **`OrchidMCPTokenStore`** — Per-user outbound OAuth token persistence for MCP servers.
- **`OrchidMCPClientRegistrationStore`** — Per-server discovered endpoints + Dynamic Client Registration credentials (RFC 7591).

## OrchidMCPGatewayClientStore / OrchidMCPGatewayAuthCodeStore / OrchidMCPGatewayTokenStore

**File:** `core/mcp_gateway_state.py`

Three ABCs for the inbound MCP gateway's OAuth state:

- **`OrchidMCPGatewayClientStore`** — Inbound DCR client registrations.
- **`OrchidMCPGatewayAuthCodeStore`** — Inbound in-flight authorization codes.
- **`OrchidMCPGatewayTokenStore`** — Inbound issued access + refresh + IdP-token records.

`OrchidMCPGatewayToken` carries `idp_access_token`, `idp_refresh_token`, and `idp_expires_at` so the refresh path has the upstream pair to swap.

## OrchidVectorReader / OrchidVectorWriter / OrchidVectorStoreAdmin

**File:** `core/repository.py`

Three segregated ABCs for vector store access:

- **`OrchidVectorReader`** — `retrieve(query, scope, k)` — Vector store retrieval. Agents depend on this only.
- **`OrchidVectorWriter`** — `upsert(documents, scope, namespace)` — Vector store indexing. Indexers depend on this only.
- **`OrchidVectorStoreAdmin`** — `create_collection()`, `delete_collection()`, `list_collections()` — Collection management. Admin operations only.

No Qdrant imports are allowed outside `rag/backends/`. All vector access goes through these ABCs.

## OrchidChatStorage

**File:** `persistence/base.py`

ABC for chat session and message CRUD. Defines:

- **`init_db()`** / **`close()`** — Lifecycle methods.
- **`create_chat(tenant_id, user_id, title)`** — Create a new chat session.
- **`list_chats(tenant_id, user_id)`** — List all chats for a user.
- **`get_chat(chat_id)`** — Get a single chat by ID.
- **`delete_chat(chat_id)`** — Delete a chat.
- **`update_title(chat_id, title)`** — Update chat title.
- **`mark_shared(chat_id)`** — Mark a chat as shared.
- **`add_message(chat_id, role, content, agents_used, metadata)`** — Add a message.
- **`get_messages(chat_id, limit, offset)`** — Retrieve messages.

The library ships built-in SQLite and PostgreSQL implementations. Alternative backends live in consumer projects.

## LLM Abstraction

Orchid uses LangChain's `BaseChatModel` directly (no custom ABC). The `build_chat_model(model_string)` factory creates one from a LiteLLM-style model string. The factory supports provider-first resolution: if a provider-specific package is installed (e.g., `langchain-openai`), it uses that directly; otherwise it falls back to `ChatLiteLLM`.

## Document Model

Uses `langchain_core.documents.Document` (re-exported from `core/repository.py`). Fields: `page_content`, `metadata`, `id`.

## Embeddings

Uses `langchain_core.embeddings.Embeddings`. The `build_embeddings(model_string)` factory creates an embedding model from a LiteLLM-style string.
