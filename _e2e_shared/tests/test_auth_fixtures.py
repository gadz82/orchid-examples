"""Self-tests for shared auth fixtures."""

from __future__ import annotations

from examples._e2e_shared.fixtures.auth import (
    make_auth_context,
)
from orchid_ai.core.state import OrchidAuthContext


def test_auth_context_is_base_class(auth_context: OrchidAuthContext) -> None:
    assert auth_context.tenant_key == "test-tenant"
    assert auth_context.user_id == "test-user"
    assert auth_context.access_token == "test-token"
    assert auth_context.roles == frozenset()


def test_admin_auth_has_admin_role(admin_auth: OrchidAuthContext) -> None:
    assert "admin" in admin_auth.roles


def test_other_tenant_auth_is_different_principal(other_tenant_auth: OrchidAuthContext) -> None:
    assert other_tenant_auth.tenant_key == "other-tenant"
    assert other_tenant_auth.user_id == "other-user"


def test_other_tenant_admin_is_admin_elsewhere(other_tenant_admin: OrchidAuthContext) -> None:
    assert other_tenant_admin.tenant_key == "other-tenant"
    assert "admin" in other_tenant_admin.roles


def test_make_auth_context_accepts_extra() -> None:
    auth = make_auth_context(plan="pro")
    assert auth.extra == {"plan": "pro"}
