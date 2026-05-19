"""Tests for the tech-conference example."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_identity_resolver_returns_known_user() -> None:
    """Resolve a bearer token returns a valid OrchidAuthContext."""
    from examples.tech_conference.identity import ConferenceIdentityResolver

    resolver = ConferenceIdentityResolver(tenant_key="conference-test")
    ctx = await resolver.resolve(domain="conference-test", bearer_token="t:demo")
    assert ctx.tenant_key == "conference-test"
    assert ctx.user_id == "bearer-user"


@pytest.mark.asyncio
async def test_identity_resolver_mints_for_known_user() -> None:
    """Mint a user that was previously seeded."""
    from examples.tech_conference.identity import ConferenceIdentityResolver

    resolver = ConferenceIdentityResolver()
    resolver.seed("u-bob", token="t:bob")
    ctx = await resolver.mint_for_user(tenant_key="conference-demo", user_id="u-bob")
    assert ctx.user_id == "u-bob"
    assert ctx.access_token == "t:bob"


@pytest.mark.asyncio
async def test_identity_resolver_rejects_unknown_user() -> None:
    """Minting an unknown user raises."""
    from examples.tech_conference.identity import ConferenceIdentityResolver
    from orchid_ai.core.events.errors import OrchidIdentityNotMintableError

    resolver = ConferenceIdentityResolver()
    with pytest.raises(OrchidIdentityNotMintableError):
        await resolver.mint_for_user(tenant_key="conference-demo", user_id="nobody")


@pytest.mark.asyncio
async def test_seed_conference_knowledge_noop_on_null_reader() -> None:
    """When reader is None, the hook should return without error."""
    from examples.tech_conference.hooks.startup import seed_conference_knowledge

    await seed_conference_knowledge(reader=None, settings=None)
