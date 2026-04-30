# API Error Model

Target response shape:

```json
{
  "error": {
    "code": "TENANT_VIOLATION",
    "message": "workspace access denied",
    "details": {},
    "request_id": "req_..."
  }
}
```

## Goals

- Keep errors machine-readable for frontend and operators.
- Always include a request id.
- Keep user-facing messages separate from raw technical/debug details.
- Never expose secrets such as JWTs, OTP codes, two-factor passwords, proxy passwords, API hashes, or TDLib session internals.

## Migration Strategy

1. Keep the current flat `AppError` response compatible while backend SaaS boundaries stabilize.
2. Introduce the envelope gradually for auth, tenant, billing/limits, safety, and proxy errors first.
3. Update frontend error parsing to accept both the current flat shape and the new envelope.
4. Convert remaining routers after compatibility tests cover both shapes.
5. Remove the flat shape only after all clients are migrated.

## Initial Error Codes

- `AUTH_REQUIRED`
- `ROLE_FORBIDDEN`
- `WORKSPACE_ACCESS_DENIED`
- `TENANT_VIOLATION`
- `NOT_FOUND`
- `REQUEST_VALIDATION_ERROR`
- `BILLING_REQUIRED`
- `RATE_LIMITED`
- `SAFETY_BLOCKED`
- `TELEGRAM_RUNTIME_ERROR`
- `PROXY_ERROR`

This document is a design note only. The full API error rewrite is intentionally not part of the SaaS production-hardening slice.
