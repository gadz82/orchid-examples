"""Pollen/Bloom dispatcher entry point.

This module exposes the trigger-to-handler map so the event framework can call
``examples.fm_agent.bloom_dispatcher.dispatch(trigger_id, ctx, payload)``.
"""

from __future__ import annotations

from examples.fm_agent.bloom_jobs import (
    TRIGGER_HANDLERS,
    BloomContext,
    JobRun,
    dispatch,
)

__all__ = ["TRIGGER_HANDLERS", "BloomContext", "JobRun", "dispatch"]
