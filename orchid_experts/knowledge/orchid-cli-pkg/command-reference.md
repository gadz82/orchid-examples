<!-- Source: derived from orchid-cli/AGENTS.md, orchid-cli/README.md, orchid-website/src/content/packages/orchid-cli.mdx, and codebase analysis -->

# Command Reference

The `orchid-cli` package provides a Typer-based command-line interface for interacting with the Orchid framework without an API server.

## Command Tree

```
orchid
├── auth                 OAuth token management
│   ├── login            Start OAuth login flow
│   ├── logout           Remove stored tokens
│   └── status           Show current auth status
├── chat                 Chat with agents
│   ├── send             Send a single message
│   └── interactive      Start interactive conversation
├── config               Configuration management
│   ├── validate         Validate agents.yaml
│   └── show             Display loaded configuration
├── index                RAG indexing
│   ├── file             Index a single file
│   ├── directory        Index a directory of files
│   └── text             Index raw text
├── skill                Skill generation
│   └── generate         Generate Claude Code skill docs from tools
├── generate-flower      Interactive project scaffolding wizard
└── pollen-bloom         Event management (local mode)
    ├── list-jobs        List Bloom job runs
    ├── list-signals     List Pollen signals
    └── trigger          Manually trigger a Bloom run
```

## Global Options

```
--config PATH            Path to orchid.yml
--verbose, -v            Increase verbosity
--quiet, -q              Decrease verbosity
--help                   Show help
```

## chat send

Send a single message to the agent fleet:

```bash
orchid chat send "What ABCs does orchid define?" \
  --config examples/orchid_experts/orchid.yml
```

Options:
- `--agent NAME` — Route to a specific agent (bypasses supervisor).
- `--chat-id ID` — Continue in an existing chat.
- `--stream` — Stream the response (default: true).

## chat interactive

Start an interactive conversation:

```bash
orchid chat interactive \
  --config examples/orchid_experts/orchid.yml
```

Slash commands in interactive mode:
- `/agents` — List available agents.
- `/skills` — List available skills.
- `/agent NAME` — Switch to a specific agent.
- `/new` — Start a new chat.
- `/history` — Show conversation history.
- `/help` — Show help.
- `/exit` — Exit interactive mode.

## config validate

Validate an agents.yaml file:

```bash
orchid config validate agents.yaml
```

Returns validation errors or "Configuration is valid."

## config show

Display the loaded configuration:

```bash
orchid config show --config orchid.yml
```

Shows all configuration values with their resolved sources (env var, YAML, or default).
