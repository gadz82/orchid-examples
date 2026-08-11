"""Tests for the secret scanning lane."""

from __future__ import annotations

from examples.fm_agent.indexer.secrets import SecretScanner


class TestSecretScanner:
    """Cover regex + entropy detection and redaction behavior."""

    def test_clean_text_passes(self) -> None:
        scanner = SecretScanner()
        text = "This is a perfectly ordinary sentence with no secrets."
        result = scanner.scan(text)

        assert result.dirty is False
        assert result.findings == []
        assert result.cleaned_text == text
        assert scanner.should_skip_chunk(result) is False

    def test_aws_access_key_detected(self) -> None:
        scanner = SecretScanner()
        text = "Deploy key: AKIAIOSFODNN7EXAMPLE in us-east-1"
        result = scanner.scan(text)

        assert result.dirty is True
        assert any(f.rule == "aws-access-key" for f in result.findings)
        assert "AKIAIOSFODNN7EXAMPLE" not in result.cleaned_text
        assert "[REDACTED]" in result.cleaned_text

    def test_gitlab_pat_detected(self) -> None:
        scanner = SecretScanner()
        token = "glpat-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        text = f"GitLab PAT: {token}"
        result = scanner.scan(text)

        assert result.dirty is True
        assert any(f.rule == "gitlab-token" for f in result.findings)
        assert token not in result.cleaned_text

    def test_private_key_block_detected(self) -> None:
        scanner = SecretScanner()
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----"
        result = scanner.scan(text)

        assert result.dirty is True
        assert any(f.rule == "private-key" for f in result.findings)
        assert "BEGIN RSA PRIVATE KEY" not in result.cleaned_text

    def test_bearer_token_detected(self) -> None:
        scanner = SecretScanner()
        token = "bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.testsignature"
        result = scanner.scan(token)

        assert result.dirty is True
        rules = {f.rule for f in result.findings}
        assert "bearer-token" in rules or "jwt-token" in rules

    def test_heavily_redacted_chunk_is_skipped(self) -> None:
        scanner = SecretScanner()
        # Build a string where >50% of the content will be redacted.
        secret = "AKIAIOSFODNN7EXAMPLE"
        text = f"{secret} {secret} {secret} {secret} {secret}"
        result = scanner.scan(text)

        assert result.dirty is True
        assert scanner.should_skip_chunk(result) is True

    def test_multiple_findings_tracked(self) -> None:
        scanner = SecretScanner()
        text = "aws: AKIAIOSFODNN7EXAMPLE and gitlab: glpat-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        result = scanner.scan(text)

        rules = {f.rule for f in result.findings}
        assert "aws-access-key" in rules
        assert "gitlab-token" in rules
