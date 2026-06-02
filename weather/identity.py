"""Identity resolver for the weather example.

Two methods:
- :meth:`resolve` — standard bearer→OrchidAuthContext flow. In the
  weather demo we trust the bearer wholesale (self-contained example;
  production resolvers verify against an IdP).
- :meth:`resolve_service_account` — required so the events block's
  schedules can mint service-account identities at fire time.
"""

from __future__ import annotations

from orchid_ai.core.events.errors import OrchidServiceAccountUnknownError
from orchid_ai.core.identity import OrchidIdentityResolver
from orchid_ai.core.state import OrchidAuthContext


class WeatherIdentityResolver(OrchidIdentityResolver):
    """Trivial resolver — the demo runs single-tenant + single-user."""

    async def resolve(
        self, domain: str, bearer_token: str
    ) -> OrchidAuthContext:
        return OrchidAuthContext(
            access_token=bearer_token,
            tenant_key="weather-demo",
            user_id="demo-user",
        )

    async def resolve_service_account(self, name: str) -> OrchidAuthContext:
        if name == "weather-bot":
            ctx = OrchidAuthContext(
                access_token="",
                tenant_key="weather-demo",
                user_id="",
            )
            ctx.extra["service_account"] = name
            return ctx
        raise OrchidServiceAccountUnknownError(name)
