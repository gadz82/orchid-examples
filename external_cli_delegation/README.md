# External CLI Agent Delegation Example

Demonstrates the `external_agents:` YAML configuration block — lets an Orchid
orchestrator agent delegate sub-tasks to an external AI CLI subprocess.

## What this example does

- One **orchestrator** agent with access to an `ask_assistant` tool
- The tool spawns a Python subprocess (stand-in for a real AI CLI)
- The orchestrator's LLM decides when to delegate and feeds results back

## Quick start

```bash
# Validate the config
orchid config validate agents.yaml

# List the configured external-agent tools
orchid external-agents list agents.yaml

# Send a chat message (requires Ollama with llama3.2)
orchid chat send "Hello" --config orchid.yml
```

## Swapping in a real AI CLI

Edit the `external_agents:` block in `agents.yaml` to point to your installed
CLI.  The `command` + `args` fields form the argv list (no shell expansion):

```yaml
external_agents:
  ask_assistant:
    command: ["claude"]              # absolute or on-PATH binary
    args: ["--print", "--output-format", "text"]
    timeout: 180
    description: "Delegate a coding task."
    requires_approval: true          # operator must approve each delegation
```

The LLM only controls the `prompt` argument — the path and flags come from
operator-controlled YAML.  Combined with `requires_approval: true` (the
default), no LLM can run an external command without your consent.

## Security

- **Approval gate:** every delegation pauses for operator confirmation (HITL)
- **No shell:** the command runs as an argv list (`subprocess_exec`, not `shell=True`)
- **Operator-controlled:** the executable path and flags come from YAML, not the LLM
- **Timeout:** runaway processes are killed after the configured timeout (default 120s)

## Files

| File | Purpose |
|------|---------|
| `orchid.yml` | Top-level config (SQLite, Chroma, dev auth) |
| `agents.yaml` | Agent + external-agent tool definitions |
| `.env.example` | Environment variable template |
