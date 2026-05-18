"""
Equivalence test — verify that MD and YAML configs produce identical
``OrchidAgentsConfig``.

Run from the orchid package directory::

    cd orchid && .venv/bin/python examples/md-config/test_equivalence.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

from orchid_ai.config.frontmatter import parse_frontmatter
from orchid_ai.config.md_loader import _merge_agent_md, load_md_config
from orchid_ai.config.schema import OrchidAgentsConfig
from orchid_ai.config.loader import load_config
from orchid_ai.config.frontmatter import load_markdown_file


def test_equivalence():
    """Compare MD and YAML configs field-by-field."""
    print("=== Orchid MD Configuration — Equivalence Test ===\n")

    # ── Load MD config ─────────────────────────────────────
    md_root = ROOT / "orchid.md"
    md_config, _ = load_md_config(str(md_root.resolve()), agents_dir=str((ROOT / "agents").resolve()))
    print(f"[MD]  Loaded {len(md_config.agents)} agents: {list(md_config.agents.keys())}")

    # ── Load YAML config ───────────────────────────────────
    yaml_path = ROOT / "agents.yaml"
    yaml_config = load_config(str(yaml_path.resolve()))
    print(f"[YAML] Loaded {len(yaml_config.agents)} agents: {list(yaml_config.agents.keys())}")

    # ── Compare top-level fields ────────────────────────────
    assert md_config.version == yaml_config.version, "version mismatch"
    assert set(md_config.tools.keys()) == set(yaml_config.tools.keys()), "tools keys mismatch"
    assert set(md_config.skills.keys()) == set(yaml_config.skills.keys()), "skills keys mismatch"
    assert set(md_config.agents.keys()) == set(yaml_config.agents.keys()), "agents keys mismatch"
    print("[OK]  Top-level fields match")

    # ── Compare each agent ──────────────────────────────────
    errors = []
    for name in md_config.agents:
        md_agent = md_config.agents[name]
        yaml_agent = yaml_config.agents[name]

        if md_agent.description.strip() != yaml_agent.description.strip():
            # YAML folded scalars may produce double spaces; normalize
            import re
            md_desc = re.sub(r'\s+', ' ', md_agent.description.strip())
            yaml_desc = re.sub(r'\s+', ' ', yaml_agent.description.strip())
            if md_desc != yaml_desc:
                errors.append(f"  {name}.description: MD='{md_desc}' vs YAML='{yaml_desc}'")

        # MD prompts include Markdown headings; YAML prompts are plain.
        # Strip leading heading lines for comparison.
        md_prompt = md_agent.prompt.strip()
        yaml_prompt = yaml_agent.prompt.strip()
        if md_prompt.startswith("# "):
            # Remove lines starting with # until first non-# line
            import re as re2
            md_prompt = re2.sub(r'^#[^\n]*\n\n?', '', md_prompt, count=1).strip()
        if md_prompt != yaml_prompt:
            errors.append(f"  {name}.prompt differs (length MD={len(md_prompt)} vs YAML={len(yaml_prompt)})")
        if md_agent.tools != yaml_agent.tools:
            errors.append(f"  {name}.tools: {md_agent.tools} vs {yaml_agent.tools}")
        if md_agent.name != yaml_agent.name:
            errors.append(f"  {name}.name: '{md_agent.name}' vs '{yaml_agent.name}'")
        if md_agent.execution_hints.parallel_safe != yaml_agent.execution_hints.parallel_safe:
            errors.append(f"  {name}.execution_hints.parallel_safe mismatch")

    if errors:
        print(f"[FAIL] {len(errors)} agent field mismatch(es):")
        for e in errors:
            print(e)
        sys.exit(1)

    # ── Compare tools ──────────────────────────────────────
    for t_name in md_config.tools:
        md_t = md_config.tools[t_name]
        yaml_t = yaml_config.tools[t_name]
        if md_t.handler != yaml_t.handler:
            errors.append(f"  tool {t_name}.handler: {md_t.handler} vs {yaml_t.handler}")
        if md_t.description != yaml_t.description:
            errors.append(f"  tool {t_name}.description mismatch")

    if errors:
        print(f"[FAIL] {len(errors)} tool field mismatch(es):")
        for e in errors:
            print(e)
        sys.exit(1)

    print(f"[OK]  All {len(md_config.agents)} agents match")
    print(f"[OK]  All {len(md_config.tools)} tools match")
    print(f"\n[PASS] MD and YAML configs are identical ✓")


if __name__ == "__main__":
    test_equivalence()
