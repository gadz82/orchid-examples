"""Identity resolver for the basketball example.

Two methods on the surface:

- :meth:`resolve` — the standard bearer→OrchidAuthContext flow.  In
  the basketball demo we trust the bearer wholesale (this is a
  self-contained example; production resolvers verify against an IdP).
- :meth:`resolve_service_account` — required so the events block's
  ``trivia-bot`` schedule can mint a service-account identity at
  fire time.  ``mint_for_user`` is intentionally NOT implemented:
  the example uses ``service_account`` only, so any ``act_as_user``
  trigger would fail at boot via the registry's mint probe — exactly
  the deterministic-misconfiguration-detection §13 calls for.
"""

from __future__ import annotations

from orchid_ai.core.events.errors import OrchidServiceAccountUnknownError
from orchid_ai.core.identity import OrchidIdentityResolver
from orchid_ai.core.state import OrchidAuthContext


class BasketballIdentityResolver(OrchidIdentityResolver):
    """Trivial resolver — the demo runs single-tenant + single-user."""

    async def resolve(
        self, domain: str, bearer_token: str
    ) -> OrchidAuthContext:
        return OrchidAuthContext(
            access_token=bearer_token,
            tenant_key="basketball-demo",
            user_id="demo-user",
        )

    async def resolve_service_account(self, name: str) -> OrchidAuthContext:
        if name == "trivia-bot":
            ctx = OrchidAuthContext(
                access_token="",
                tenant_key="basketball-demo",
                user_id="",
            )
            ctx.extra["service_account"] = name
            return ctx
        raise OrchidServiceAccountUnknownError(name)
