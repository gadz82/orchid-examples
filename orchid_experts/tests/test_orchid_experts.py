"""Tests for the orchid_experts example."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_identity_resolver_returns_known_user() -> None:
    """Resolve a bearer token returns a valid OrchidAuthContext."""
    from examples.orchid_experts.identity import ExpertsIdentityResolver

    resolver = ExpertsIdentityResolver(tenant_key="experts-test")
    ctx = await resolver.resolve(domain="experts-test", bearer_token="t:demo")
    assert ctx.tenant_key == "experts-test"
    assert ctx.user_id == "bearer-user"


@pytest.mark.asyncio
async def test_identity_resolver_mints_for_known_user() -> None:
    """Mint a user that was previously seeded."""
    from examples.orchid_experts.identity import ExpertsIdentityResolver

    resolver = ExpertsIdentityResolver()
    resolver.seed("u-bob", token="t:bob")
    ctx = await resolver.mint_for_user(tenant_key="experts-demo", user_id="u-bob")
    assert ctx.user_id == "u-bob"
    assert ctx.access_token == "t:bob"


@pytest.mark.asyncio
async def test_identity_resolver_rejects_unknown_user() -> None:
    """Minting an unknown user raises."""
    from examples.orchid_experts.identity import ExpertsIdentityResolver
    from orchid_ai.core.events.errors import OrchidIdentityNotMintableError

    resolver = ExpertsIdentityResolver()
    with pytest.raises(OrchidIdentityNotMintableError):
        await resolver.mint_for_user(tenant_key="experts-demo", user_id="nobody")


@pytest.mark.asyncio
async def test_seed_experts_knowledge_noop_on_null_reader() -> None:
    """When reader is None, the hook should return without error."""
    from examples.orchid_experts.hooks.startup import seed_experts_knowledge

    await seed_experts_knowledge(reader=None, settings=None)


def test_agents_yaml_loads() -> None:
    """agents.yaml is valid and has the expected structure."""
    import yaml
    from pathlib import Path

    agents_path = Path(__file__).resolve().parent.parent / "agents.yaml"
    data = yaml.safe_load(agents_path.read_text(encoding="utf-8"))

    assert "version" in data
    assert "agents" in data
    assert len(data["agents"]) == 10
    assert "skills" in data
    assert len(data["skills"]) == 9
    assert "supervisor" in data
    assert "guardrails" in data


def test_orchid_yml_loads() -> None:
    """orchid.yml is valid and has the expected structure."""
    import yaml
    from pathlib import Path

    orch_path = Path(__file__).resolve().parent.parent / "orchid.yml"
    data = yaml.safe_load(orch_path.read_text(encoding="utf-8"))

    assert "agents" in data
    assert "config_path" in data["agents"]
    assert "rag" in data
    assert "storage" in data
    assert "startup" in data
    assert "hook" in data["startup"]
