<!-- Source: derived from orchid-cli/AGENTS.md, orchid-website/src/content/packages/orchid-cli.mdx, and codebase analysis -->

# Generate Flower

The `generate-flower` command is an interactive project scaffolding wizard that creates a complete, runnable Orchid project with agents, tools, knowledge directories, and test files. Named after the orchid flower, it grows a new project from seed.

## Running the Wizard

```bash
orchid generate-flower
```

The wizard presents a series of interactive prompts to configure your new project.

## Interactive Prompts

### 1. Project Name
```
Project name: my-ai-assistant
```
Used for the directory name, Python package name, and README title. Must be a valid Python identifier (lowercase, underscores OK).

### 2. Description
```
Description: AI assistant for customer support
```
Short description used in the generated README and `agents.yaml` header comment.

### 3. LLM Provider
```
Choose LLM provider:
  1. Ollama (local, free)
  2. OpenAI (cloud)
  3. Anthropic (cloud)
  4. Google Gemini (cloud)
  5. Groq (cloud, fast)
→ 1
```
Selects the default LLM model. The wizard sets `defaults.llm.model` in `agents.yaml` and `llm.model` in `orchid.yml` accordingly.

### 4. Vector Backend
```
Choose vector backend:
  1. ChromaDB (zero-infra, local)
  2. Qdrant (requires Docker, production-ready)
→ 1
```
Selects the default vector store. ChromaDB is recommended for getting started; Qdrant for production.

### 5. Storage Backend
```
Choose storage:
  1. SQLite (local file, simple)
  2. PostgreSQL (requires server, production-ready)
→ 1
```
Selects the chat persistence backend.

### 6. Auth Mode
```
Choose auth:
  1. Development (no auth)
  2. OIDC (production)
→ 1
```
Development mode uses a trivial identity resolver. OIDC requires configuring an OIDC provider.

### 7. Agent Count
```
How many starter agents? (1-5): 2
```
Creates that many agent definitions in `agents.yaml` with sensible defaults.

### 8. First Agent Domain
```
Agent 1 name: support-agent
Agent 1 description: Customer support specialist
Agent 1 RAG namespace: support-docs
```
Sets up the first agent with a name, description, and RAG namespace. Repeat for each agent.

## Generated Files

```
my-ai-assistant/
├── orchid.yml                      # Runtime: LLM, RAG, storage, auth
├── agents.yaml                     # Agent definitions (2 agents + supervisor)
├── identity.py                     # Trivial or OIDC identity resolver
├── __init__.py                     # Package marker
├── hooks/
│   ├── __init__.py
│   └── startup.py                  # Example startup hook (empty, ready to customize)
├── tools/
│   ├── __init__.py
│   └── example.py                  # Example built-in tool (hello world)
├── knowledge/
│   ├── support-docs/               # Knowledge directory for agent 1
│   └── agent-2-ns/                 # Knowledge directory for agent 2
├── tests/
│   ├── __init__.py
│   └── test_basic.py              # Basic validation tests
└── README.md                       # Project overview and usage instructions
```

## Agent Scaffolding

The wizard creates starter agents:

```yaml
version: "1"

defaults:
  llm:
    model: "ollama/llama3.2"
    temperature: 0.2
  rag:
    enabled: true

supervisor:
  assistant_name: "My AI Assistant"
  system_prompt: |
    You are the My AI Assistant supervisor...

agents:
  support-agent:
    description: "Customer support specialist"
    prompt: |
      You are a customer support specialist for My AI Assistant.
      Answer support questions clearly and helpfully.
      Always provide:
      1. A clear answer to the question
      2. Relevant documentation references
      3. Next steps if the issue isn't resolved
    rag:
      namespace: support-docs
      k: 5
    execution_hints:
      parallel_safe: true
```

## Post-Generation Instructions

After scaffolding, the wizard prints next steps:

```
✅ Project created at: ./my-ai-assistant

Next steps:

  1. cd my-ai-assistant

  2. Write knowledge files:
     Create .md files in knowledge/support-docs/

  3. Validate configuration:
     orchid config validate agents.yaml

  4. Index knowledge:
     orchid index directory ./knowledge/ --namespace support-docs

  5. Start chatting:
     orchid chat interactive --config orchid.yml

  6. Run tests:
     python -m pytest tests/ -v

  7. Deploy with Docker:
     (see Dockerfile and orchid.yml)
```

## Customization After Generation

The generated files are starting points. Customize:
- Agent prompts for your domain.
- Add more agents by editing `agents.yaml`.
- Write real knowledge files in `knowledge/*/`.
- Replace `tools/example.py` with real tools.
- Configure production auth in `orchid.yml` and `identity.py`.
- Add cross-agent skills for multi-domain workflows.
