"""Custom :class:`OrchidSignalProducer` — weekly fan-out.

Demonstrates the integrator-extensible producer pattern with a
runnable example: at cron time, the producer enumerates active
learners for each tenant and emits one
``weekly-digest.due`` signal per ``(tenant, user)``.  The dispatcher
then enqueues N independent jobs that the processor pool drains in
parallel under :class:`addressed_to_user` identity.

The producer takes two collaborators by composition (DIP):

- ``tenant_provider.list()`` returns the active tenant keys.
- ``user_lister.active(tenant)`` returns the active learner ids
  for a given tenant.

Both are tiny in-memory implementations in tests; production
integrators wire their own (DB query, IdP enumeration, …).

This file lives in :mod:`examples.learning.producers` so the YAML
loads it via ``class:
examples.learning.producers.weekly_digest.WeeklyDigestFanoutProducer``.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import logging
from typing import Callable, Protocol, runtime_checkable

from orchid_ai.core.events.dispatcher import OrchidSignalDispatcher
from orchid_ai.core.events.producer import OrchidSignalProducer
from orchid_ai.core.events.signal import SignalEnvelope

_logger = logging.getLogger(__name__)


@runtime_checkable
class _TenantProvider(Protocol):
    async def list(self) -> list[str]: ...


@runtime_checkable
class _UserLister(Protocol):
    async def active(self, tenant: str) -> list[str]: ...


class WeeklyDigestFanoutProducer(OrchidSignalProducer):
    """At cron time, emit one signal per active learner.

    Construction (YAML ``class: ...`` plus ``extra_args``):

    .. code-block:: yaml

        producers:
          - class: examples.learning.producers.weekly_digest.WeeklyDigestFanoutProducer
            extra_args:
              cron: "0 6 * * 1"
              tenant_provider_class: myapp.tenants.AcmeTenantProvider
              user_lister_class: myapp.users.AcmeUserLister

    The example test below constructs the producer directly with
    the tiny in-memory collaborators rather than via dotted-path
    resolution, but the YAML wiring is identical to the real
    deployment.
    """

    def __init__(
        self,
        *,
        tenant_provider: _TenantProvider,
        user_lister: _UserLister,
        cron: str = "0 6 * * 1",
        clock: Callable[[], _dt.datetime] | None = None,
    ) -> None:
        self._tenant_provider = tenant_provider
        self._user_lister = user_lister
        self._cron = cron
        self._clock = clock or _now
        self._dispatcher: OrchidSignalDispatcher | None = None
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()

    @property
    def name(self) -> str:
        return "WeeklyDigestFanoutProducer"

    async def start(self, dispatcher: OrchidSignalDispatcher) -> None:
        """Register a long-running task that fires the fan-out at
        cron time.  The example doesn't wire APScheduler here —
        :func:`fanout_now` is the sync hook that real deployments
        call from a real scheduler (or that tests invoke directly)."""
        self._dispatcher = dispatcher
        self._stopping.clear()
        # The runnable example doesn't manage its own clock; tests
        # call :func:`fanout_now` to drive a single tick, and real
        # deployments hook this producer's :meth:`fanout_now` into a
        # ``SchedulerProducer`` (or any other clock) via the YAML
        # wiring layer.

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    async def fanout_now(self) -> int:
        """Run a single fan-out tick.  Returns the number of signals
        emitted.  Idempotent under crash via the
        ``(tenant, user, week)`` dedupe key."""
        if self._dispatcher is None:
            raise RuntimeError(
                "WeeklyDigestFanoutProducer.fanout_now called before start()"
            )
        now = self._clock()
        week = now.isocalendar().week
        emitted = 0
        for tenant in await self._tenant_provider.list():
            for user_id in await self._user_lister.active(tenant):
                envelope = SignalEnvelope(
                    type="weekly-digest.due",
                    payload={"week_iso": week, "year": now.year},
                    source="fanout:weekly-digest",
                    occurred_at=now,
                    tenant_key=tenant,
                    user_id=user_id,
                    dedupe_key=f"weekly-digest:{tenant}:{user_id}:{week}",
                    identity_claim={
                        "mode": "addressed_to_user",
                        "service_account": "digest-bot",
                        "user_id_from": "signal.user_id",
                    },
                )
                await self._dispatcher.ingest(envelope)
                emitted += 1
        return emitted


def _now() -> _dt.datetime:
    return _dt.datetime.now(tz=_dt.UTC)


# ── In-memory collaborators (test / demo) ───────────────────


class StaticTenantProvider:
    """``_TenantProvider`` backed by a static list — useful for tests."""

    def __init__(self, tenants: list[str]) -> None:
        self._tenants = list(tenants)

    async def list(self) -> list[str]:
        return list(self._tenants)


class StaticUserLister:
    """``_UserLister`` backed by a static per-tenant map."""

    def __init__(self, users_by_tenant: dict[str, list[str]]) -> None:
        self._map: dict[str, list[str]] = {
            t: list(u) for t, u in users_by_tenant.items()
        }

    async def active(self, tenant: str) -> list[str]:
        return list(self._map.get(tenant, []))
