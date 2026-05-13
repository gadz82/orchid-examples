"""Identity resolver for the restaurant example.

Implements the ``act_as_user`` flow with a hand-rolled in-memory
mapping — production deployments wire :class:`OAuthMintingMixin`
against an :class:`OrchidMCPTokenStore`.  The example keeps it simple
so the chat-binding + cross-user-rejection tests stay hermetic.
"""

from __future__ import annotations

from orchid_ai.core.events.errors import (
    OrchidIdentityNotMintableError,
    OrchidServiceAccountUnknownError,
)
from orchid_ai.core.identity import OrchidIdentityResolver
from orchid_ai.core.state import OrchidAuthContext


class RestaurantIdentityResolver(OrchidIdentityResolver):
    """Mintable resolver — every known user gets a fresh
    :class:`OrchidAuthContext` for the duration of one Bloom run."""

    def __init__(
        self,
        *,
        tenant_key: str = "restaurant-demo",
        users: dict[str, str] | None = None,
    ) -> None:
        self._tenant_key = tenant_key
        self._users: dict[str, str] = dict(users or {})

    async def resolve(
        self, domain: str, bearer_token: str
    ) -> OrchidAuthContext:
        return OrchidAuthContext(
            access_token=bearer_token,
            tenant_key=self._tenant_key,
            user_id="bearer-user",
        )

    async def resolve_service_account(self, name: str) -> OrchidAuthContext:
        # Restaurant uses act_as_user only.
        raise OrchidServiceAccountUnknownError(name)

    async def mint_for_user(
        self, tenant_key: str, user_id: str
    ) -> OrchidAuthContext:
        token = self._users.get(user_id)
        if token is None:
            raise OrchidIdentityNotMintableError(tenant_key, user_id)
        return OrchidAuthContext(
            access_token=token,
            tenant_key=tenant_key,
            user_id=user_id,
        )

    def seed(self, user_id: str, token: str) -> None:
        self._users[user_id] = token
