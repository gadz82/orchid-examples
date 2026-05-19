"""Tests for the hospital-front-office example."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_identity_resolver_returns_known_user() -> None:
    """Resolve a bearer token returns a valid OrchidAuthContext."""
    from examples.hospital_front_office.identity import HospitalIdentityResolver

    resolver = HospitalIdentityResolver(tenant_key="hospital-test")
    ctx = await resolver.resolve(domain="hospital-test", bearer_token="t:demo")
    assert ctx.tenant_key == "hospital-test"
    assert ctx.user_id == "bearer-user"


@pytest.mark.asyncio
async def test_identity_resolver_mints_for_known_user() -> None:
    """Mint a user that was previously seeded."""
    from examples.hospital_front_office.identity import HospitalIdentityResolver

    resolver = HospitalIdentityResolver()
    resolver.seed("u-alice", token="t:alice")
    ctx = await resolver.mint_for_user(tenant_key="hospital-demo", user_id="u-alice")
    assert ctx.user_id == "u-alice"
    assert ctx.access_token == "t:alice"


@pytest.mark.asyncio
async def test_identity_resolver_rejects_unknown_user() -> None:
    """Minting an unknown user raises."""
    from examples.hospital_front_office.identity import HospitalIdentityResolver
    from orchid_ai.core.events.errors import OrchidIdentityNotMintableError

    resolver = HospitalIdentityResolver()
    with pytest.raises(OrchidIdentityNotMintableError):
        await resolver.mint_for_user(tenant_key="hospital-demo", user_id="nobody")


@pytest.mark.asyncio
async def test_seed_hospital_knowledge_noop_on_null_reader() -> None:
    """When reader is None, the hook should return without error."""
    from examples.hospital_front_office.hooks.startup import seed_hospital_knowledge

    await seed_hospital_knowledge(reader=None, settings=None)
