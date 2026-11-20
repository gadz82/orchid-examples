"""Local dev identity resolver for the event-driven pipeline example.

The HTTP path resolves any bearer to a fixed demo tenant. The events path
mints an ``OrchidAuthContext`` for the user named on an ``act_as_user`` signal,
and resolves the scheduler's service account in the ``default`` tenant. This is
deliberately permissive: production deployments replace it with an IdP-backed
``OrchidIdentityResolver``.
"""

from __future__ import annotations

from orchid_ai.core.identity import OrchidIdentityResolver
from orchid_ai.core.state import OrchidAuthContext

DEMO_TENANT = "data-pipeline-demo"
DEMO_USER = "dev-user"


class PipelineIdentityResolver(OrchidIdentityResolver):
    """Deterministic resolver for local demos and hermetic tests."""

    async def resolve(self, domain: str, bearer_token: str) -> OrchidAuthContext:
        return OrchidAuthContext(
            access_token=bearer_token,
            tenant_key=DEMO_TENANT,
            user_id=DEMO_USER,
        )

    async def resolve_service_account(self, name: str) -> OrchidAuthContext:
        return OrchidAuthContext(
            access_token="service-account",
            tenant_key="default",
            user_id=f"svc:{name}",
        )

    async def mint_for_user(self, tenant_key: str, user_id: str) -> OrchidAuthContext:
        return OrchidAuthContext(
            access_token="minted-user-token",
            tenant_key=tenant_key,
            user_id=user_id,
        )
