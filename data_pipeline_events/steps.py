"""Deterministic operator code for the direct data-pipeline example."""

from __future__ import annotations

from typing import Any


def load_account(ctx: Any) -> dict[str, Any]:
    """Load a synthetic customer record from the run input."""
    customer_id = str(ctx.input["customer_id"])
    return {
        "id": customer_id,
        "name": f"Customer {customer_id}",
        "tier": "pro",
    }


def usage_item(ctx: Any) -> dict[str, Any]:
    """One usage row for a map item."""
    item = ctx.job.item or {}
    region = str(item.get("region") or "unknown")
    return {"region": region, "units": 10 + len(region)}


def propose(ctx: Any) -> dict[str, Any]:
    """Turn the decision label into an actionable recommendation."""
    jobs = ctx.mapping_context.jobs
    label = str((jobs.get("route") or {}).get("output", {}).get("label", "review"))
    assessment = (jobs.get("assess") or {}).get("output") or {}
    recommendations = {
        "retain": "retain and check in 30 days",
        "review": "schedule a success review",
        "escalate": "escalate to the account team",
    }
    return {
        "recommendation": recommendations.get(label, "review the account"),
        "risk": str(assessment.get("risk", "unknown")),
    }


def snapshot(ctx: Any) -> dict[str, Any]:
    """Small child-pipeline payload used by the sub-pipeline step."""
    customer_id = str(ctx.input["customer_id"])
    return {
        "customer_id": customer_id,
        "summary": f"Snapshot for {customer_id}: account loaded and usage aggregated.",
    }
