<!-- Source: derived from orchid-website/src/content/concepts/pollen-bloom.mdx and codebase analysis -->

# Webhook Ingestion

Pollen supports HTTP webhook ingestion for receiving signals from external systems.

## Configuration

```yaml
events:
  ingestion:
    sources:
      - id: support-system
        validator:
          class: orchid_ai.events.auth.HMACValidator
          secret_ref: env:SUPPORT_HMAC_SECRET
        allowed_types:
          - support.ticket.created
          - support.ticket.updated

      - id: monitoring
        validator:
          class: orchid_ai.events.auth.BearerValidator
          secret_ref: env:MONITORING_TOKEN
        allowed_types:
          - system.alert.critical
          - system.alert.warning
```

## Source Configuration

Each source has:

- **`id`** — Unique source identifier (used in logging and metrics).
- **`validator`** — Authentication validator (`HMACValidator` or `BearerValidator`).
- **`allowed_types`** — Allowlist of signal types this source can emit.
- **`secret_ref`** — Reference to the validation secret (`env:VAR_NAME`).

## Validation

### HMACValidator

Validates that the request was signed with the correct HMAC secret:

```
POST /api/events/ingest
Content-Type: application/json
X-Signature: sha256=<hex-encoded-signature>

{ "type": "support.ticket.created", "payload": { ... } }
```

The validator:
1. Reads the `X-Signature` header.
2. Computes `HMAC-SHA256(secret, raw_body)`.
3. Constant-time comparison against the provided signature.
4. Rejects if signatures don't match.

The raw body is validated BEFORE parsing — prevents payload-parsing attacks.

### BearerValidator

Simple bearer token validation:

```
POST /api/events/ingest
Authorization: Bearer <pre-shared-token>

{ "type": "system.alert.critical", "payload": { ... } }
```

### secret_ref

Secrets are never written in YAML. Use `env:VAR_NAME` to reference environment variables:

```yaml
secret_ref: env:SUPPORT_HMAC_SECRET
```

The secret is read from the environment at runtime.

## Endpoint

The ingestion endpoint is exposed by `orchid-api`:

```
POST /api/events/ingest
```

When `events.ingestion.sources` is non-empty, `HTTPIngestionProducer` is mounted automatically — no explicit producer entry needed in `events.producers`.

## Flow

1. External system sends POST with JSON body and signature/token.
2. Validator authenticates the request.
3. Signal type is checked against the source's `allowed_types`.
4. Signal is created with the validated payload.
5. Middleware chain processes the signal (if configured).
6. Signal is persisted and enqueued via `dispatcher.ingest()`.
7. Queue processor picks up the signal and matches it to triggers.

## Security Considerations

- **Validate BEFORE parsing** — HMAC validation on raw body prevents payload-parsing attacks.
- **Constant-time comparison** — HMAC comparison uses constant-time algorithms to prevent timing attacks.
- **Allowlist signal types** — Each source can only emit specific signal types, preventing injection.
- **Rotate secrets** — Webhook secrets should be rotated periodically.
