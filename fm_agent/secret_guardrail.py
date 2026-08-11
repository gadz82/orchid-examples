"""Output guardrail — secret/credential detection (regex + entropy).

Redacts AWS keys, bearer/PAT tokens, SMTP passwords, private key blocks,
DSNs with embedded credentials, and other gitleaks-style secrets from agent
output before it reaches the user.  Registered via hooks/startup.py.

Reuses the same regex+entropy lane from indexer/secrets.py (SPEC §7).
"""

from __future__ import annotations

from orchid_ai.core.guardrails import (
    OrchidGuardrail,
    OrchidGuardrailAction,
    OrchidGuardrailContext,
    OrchidGuardrailDirection,
    OrchidGuardrailResult,
)

GUARDRAIL_NAME = "secret_detection"


class SecretDetectionGuardrail(OrchidGuardrail):
    """Output guardrail that redacts secrets in agent responses."""

    @property
    def name(self) -> str:
        return GUARDRAIL_NAME

    async def check(
        self,
        content: str,
        context: OrchidGuardrailContext,
    ) -> OrchidGuardrailResult:
        """Scan output content for secrets. Redact if found.

        Only runs on OUTPUT direction — input passes through.
        """
        if context.direction != OrchidGuardrailDirection.OUTPUT:
            return OrchidGuardrailResult.passed(GUARDRAIL_NAME)

        from examples.fm_agent.indexer.secrets import SecretScanner

        scanner = SecretScanner()
        result = scanner.scan(content, path="agent-output")

        if not result.dirty:
            return OrchidGuardrailResult.passed(GUARDRAIL_NAME)

        return OrchidGuardrailResult(
            triggered=True,
            action=OrchidGuardrailAction.REDACT,
            guardrail_name=GUARDRAIL_NAME,
            message="Credential patterns detected and redacted in output",
            redacted_content=result.cleaned_text,
            details={
                "findings_count": len(result.findings),
                "rules_triggered": [f.rule for f in result.findings],
            },
        )
