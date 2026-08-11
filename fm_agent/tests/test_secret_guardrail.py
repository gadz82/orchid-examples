"""Tests for the secret-detection output guardrail."""

from __future__ import annotations

import pytest

from examples.fm_agent.secret_guardrail import SecretDetectionGuardrail


class TestSecretGuardrail:
    """Cover output redaction and input passthrough."""

    @pytest.fixture
    def guardrail(self):
        return SecretDetectionGuardrail()

    @pytest.fixture
    def output_context(self):
        from orchid_ai.core.guardrails import OrchidGuardrailContext, OrchidGuardrailDirection

        return OrchidGuardrailContext(direction=OrchidGuardrailDirection.OUTPUT)

    @pytest.fixture
    def input_context(self):
        from orchid_ai.core.guardrails import OrchidGuardrailContext, OrchidGuardrailDirection

        return OrchidGuardrailContext(direction=OrchidGuardrailDirection.INPUT)

    async def test_clean_output_passes(self, guardrail, output_context) -> None:
        result = await guardrail.check("Hello, this is safe.", output_context)

        assert result.triggered is False
        assert result.action.name == "ALLOW"

    async def test_output_with_secret_is_redacted(self, guardrail, output_context) -> None:
        text = "The deploy key is AKIAIOSFODNN7EXAMPLE"
        result = await guardrail.check(text, output_context)

        assert result.triggered is True
        assert result.action.name == "REDACT"
        assert result.redacted_content is not None
        assert "AKIAIOSFODNN7EXAMPLE" not in result.redacted_content
        assert "[REDACTED]" in result.redacted_content
        assert "Credential patterns detected" in result.message

    async def test_input_direction_is_ignored(self, guardrail, input_context) -> None:
        text = "The deploy key is AKIAIOSFODNN7EXAMPLE"
        result = await guardrail.check(text, input_context)

        assert result.triggered is False
        assert result.action.name == "ALLOW"
