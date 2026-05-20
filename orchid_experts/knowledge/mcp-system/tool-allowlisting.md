<!-- Source: derived from orchid-website/src/content/concepts/mcp.mdx, orchid/AGENTS.md, and codebase analysis -->

# Tool Allowlisting

Tool allowlisting restricts which MCP tools are exposed to an agent, even when the server offers more tools. This provides security and predictability by limiting the agent's tool surface.

## How Allowlisting Works

### Wildcard (Discover All)

Use `"*"` to expose all tools the server offers:

```yaml
mcp_servers:
  - name: my-server
    url: http://localhost:3001/mcp
    tools: "*"
```

The agent discovers all tools via `list_tools()` at capability warming time. Every discovered tool is available for LLM selection.

### Explicit List (Allowlist)

Use an explicit list to expose only specific tools:

```yaml
mcp_servers:
  - name: my-server
    url: http://localhost:3001/mcp
    tools:
      - name: search_catalog
      - name: get_inventory
      - name: create_order
```

Only these three tools are available, even if the server offers more. This is the production-recommended pattern.

### Why Allowlist?

1. **Security** — Prevents agents from calling sensitive or dangerous tools.
2. **Predictability** — The agent's behavior is bounded to known tools.
3. **Token efficiency** — Fewer tool descriptions in the LLM prompt.
4. **Error isolation** — A buggy tool on the server won't affect the agent if it's not in the allowlist.

## Per-Tool Configuration

Each allowed tool can have additional configuration:

```yaml
tools:
  - name: search_catalog
    arguments:
      max_results: 10
      language: en
    inject_to_rag: true
    rag_ttl: 3600

  - name: get_inventory
    # No special configuration
```

### Fields

- **`arguments`** — Default arguments for every invocation. Merged with the query.
- **`inject_to_rag`** — Store results in vector store for future retrieval. Default: `false`.
- **`rag_ttl`** — Cache TTL in seconds. Default: `null` (uses agent's default).

## prompts and resources Allowlisting

Prompts and resources can also be allowlisted:

```yaml
mcp_servers:
  - name: my-server
    url: http://localhost:3001/mcp
    tools: "*"
    prompts:
      - catalog_schema
      - search_query
    resources:
      - catalog/
```

Or use `"*"` for all:

```yaml
prompts: "*"
resources: "*"
```

## Best Practices

- **Use explicit lists in production** — They provide security and predictability.
- **Use `"*"` in development** — It's convenient for exploration and testing.
- **Keep allowlists minimal** — Only expose tools the agent actually needs.
- **Document tool dependencies** — For each agent, document which tools it uses and why.
- **Review allowlists periodically** — Remove tools that are no longer needed.
