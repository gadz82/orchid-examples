"""Identity resolver for the helpdesk example.

Demonstrates the ``act_as_user`` identity path: ``mint_for_user``
returns a fresh :class:`OrchidAuthContext` for the requested user
based on a stored credential.  Production deployments wire the
:class:`OAuthMintingMixin` against an :class:`OrchidMCPTokenStore`;
this example uses a hand-rolled in-memory dict so the smoke tests
stay hermetic.

``resolve_service_account`` is intentionally NOT implemented — the
helpdesk example uses ``act_as_user`` only.  Any ``service_account``
trigger added by mistake would fail at boot via the registry's
service-account probe.
"""

from __future__ import annotations

from orchid_ai.core.events.errors import (
    OrchidIdentityNotMintableError,
    OrchidServiceAccountUnknownError,
)
from orchid_ai.core.identity import OrchidIdentityResolver
from orchid_ai.core.state import OrchidAuthContext


class HelpdeskIdentityResolver(OrchidIdentityResolver):
    """Mintable resolver for the helpdesk example.

    The internal ``_user_tokens`` dict is the stand-in for a real
    :class:`OrchidMCPTokenStore` lookup — production resolvers wire
    :class:`OAuthMintingMixin` against the persistent store.
    """

    def __init__(
        self,
        *,
        domain: str = "helpdesk-demo",
        user_tokens: dict[str, str] | None = None,
    ) -> None:
        self._domain = domain
        self._user_tokens: dict[str, str] = dict(user_tokens or {})

    async def resolve(
        self, domain: str, bearer_token: str
    ) -> OrchidAuthContext:
        """Trivial bearer→context for the demo.  Production resolvers
        verify the bearer against an IdP."""
        return OrchidAuthContext(
            access_token=bearer_token,
            tenant_key=self._domain,
            user_id="bearer-user",
        )

    async def resolve_service_account(self, name: str) -> OrchidAuthContext:
        """Helpdesk uses act_as_user only — service-account triggers
        would be misconfiguration and are rejected here."""
        raise OrchidServiceAccountUnknownError(name)

    async def mint_for_user(
        self, tenant_key: str, user_id: str
    ) -> OrchidAuthContext:
        """Mint an :class:`OrchidAuthContext` for the named user.

        Reads the user's stored token from the in-memory map; raises
        :class:`OrchidIdentityNotMintableError` for unknown users —
        which the processor treats as terminal (the run finishes
        FAILED, the queue ack's, no retry).

        The probe sentinel ``"__probe__"`` flows through the same
        branch and raises ``OrchidIdentityNotMintableError`` (NOT
        ``MintingProbeUnsupportedError``) — registration treats this
        as 'I support minting, just not for that user', which is the
        expected boot-time outcome.
        """
        token = self._user_tokens.get(user_id)
        if token is None:
            raise OrchidIdentityNotMintableError(tenant_key, user_id)
        return OrchidAuthContext(
            access_token=token,
            tenant_key=tenant_key,
            user_id=user_id,
        )

    # ── Test seam ────────────────────────────────────────

    def seed(self, user_id: str, token: str) -> None:
        """Test helper: register a user→token mapping."""
        self._user_tokens[user_id] = token
