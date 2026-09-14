"""Auth context factories for e2e tests."""

from __future__ import annotations

import pytest
from orchid_ai.core.state import OrchidAuthContext

DEFAULT_TENANT = "test-tenant"
DEFAULT_USER = "test-user"
DEFAULT_TOKEN = "test-token"


def make_auth_context(
    *,
    tenant_key: str = DEFAULT_TENANT,
    user_id: str = DEFAULT_USER,
    access_token: str = DEFAULT_TOKEN,
    roles: frozenset[str] | set[str] | tuple[str, ...] | list[str] | None = None,
    **extra: object,
) -> OrchidAuthContext:
    """Build a standard OrchidAuthContext for tests.

    The returned context is safe to use with dev-auth-bypass APIs and
    mocked identity resolvers. Extra kwargs land in ``.extra``.
    """
    return OrchidAuthContext(
        access_token=access_token,
        tenant_key=tenant_key,
        user_id=user_id,
        extra=extra or None,
        roles=roles,
    )


@pytest.fixture
def auth_context() -> OrchidAuthContext:
    """Standard non-admin auth context."""
    return make_auth_context()


@pytest.fixture
def admin_auth() -> OrchidAuthContext:
    """Auth context with the admin role."""
    return make_auth_context(user_id="admin-user", roles={"admin"})


@pytest.fixture
def other_tenant_auth() -> OrchidAuthContext:
    """Auth context from a different tenant for cross-tenant tests."""
    return make_auth_context(tenant_key="other-tenant", user_id="other-user")


@pytest.fixture
def other_tenant_admin() -> OrchidAuthContext:
    """Admin auth context from a different tenant."""
    return make_auth_context(
        tenant_key="other-tenant", user_id="other-admin", roles={"admin"}
    )
