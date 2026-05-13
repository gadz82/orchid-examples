"""Identity resolver for the learning example.

Implements both ``service_account`` (the fan-out producer runs as
``digest-bot``) AND ``mint_for_user`` (the
``addressed_to_user`` flavour mints under the named user).  This is
the most-permissive resolver shape — production deployments can
restrict either.
"""

from __future__ import annotations

from orchid_ai.core.events.errors import (
    OrchidIdentityNotMintableError,
    OrchidServiceAccountUnknownError,
)
from orchid_ai.core.identity import OrchidIdentityResolver
from orchid_ai.core.state import OrchidAuthContext


class LearningIdentityResolver(OrchidIdentityResolver):
    def __init__(
        self,
        *,
        tenant_key: str = "learning-demo",
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
        if name == "digest-bot":
            ctx = OrchidAuthContext(
                access_token="sa:digest-bot",
                tenant_key=self._tenant_key,
                user_id="",
            )
            ctx.extra["service_account"] = name
            return ctx
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
