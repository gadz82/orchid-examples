"""Identity resolver for the education example."""

from __future__ import annotations

from orchid_ai.core.events.errors import OrchidServiceAccountUnknownError
from orchid_ai.core.identity import OrchidIdentityResolver
from orchid_ai.core.state import OrchidAuthContext


class EducationIdentityResolver(OrchidIdentityResolver):
    """Single-tenant demo resolver for local education workflows."""

    def __init__(
        self,
        *,
        tenant_key: str = "education-demo",
        user_tokens: dict[str, str] | None = None,
    ) -> None:
        self._tenant_key = tenant_key
        self._user_tokens: dict[str, str] = dict(user_tokens or {})

    async def resolve(self, domain: str, bearer_token: str) -> OrchidAuthContext:
        return OrchidAuthContext(
            access_token=bearer_token,
            tenant_key=self._tenant_key,
            user_id="demo-user",
        )

    async def resolve_service_account(self, name: str) -> OrchidAuthContext:
        if name == "quiz-bot":
            ctx = OrchidAuthContext(
                access_token="sa:quiz-bot",
                tenant_key=self._tenant_key,
                user_id="",
            )
            ctx.extra["service_account"] = name
            return ctx
        raise OrchidServiceAccountUnknownError(name)

    async def mint_for_user(self, tenant_key: str, user_id: str) -> OrchidAuthContext:
        token = self._user_tokens.get(user_id)
        if token is not None:
            return OrchidAuthContext(
                access_token=token,
                tenant_key=tenant_key,
                user_id=user_id,
            )
        # Unknown user — mint a minimal context so Bloom can
        # still invoke the agent.  In production this should
        # resolve a real upstream token; for the demo the
        # agent does not need a valid bearer token.
        return OrchidAuthContext(
            access_token="",
            tenant_key=tenant_key,
            user_id=user_id,
        )

    def seed(self, user_id: str, token: str) -> None:
        self._user_tokens[user_id] = token
