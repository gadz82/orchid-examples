"""Tool-strategies example — per-MCP-server tool_call_strategy showcase.

Demonstrates Orchid's :class:`OrchidToolCallStrategy` extension point:

  * Built-in strategies (``all`` / ``sequential`` / ``llm_decides``)
    selected per MCP server via YAML.
  * A custom ``priority`` strategy registered at startup that calls
    tools in declared order but stops at the first non-empty result.
  * Per-agent ``parallel_tools`` flag for the agentic-loop's parallel
    dispatch path (Phase A).

See ``README.md`` for the full walkthrough.
"""
