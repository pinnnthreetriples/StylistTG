---
name: security
description: Security, secrets, workspace scoping, and live-operation safety rules.
triggers:
  - security
  - secret
  - TDLib
  - live
  - workspace
edges:
  - .mex/context/backend.md
  - .mex/context/warmup.md
  - .mex/patterns/live-tdlib-safety.md
last_updated: 2026-05-28
---

# Security and Live Safety

## Secrets and runtime data

- Do not read, copy, commit, or summarize environment files, dashboard local env files, backend local env files, or cloud/local secret files unless the user explicitly approves the exact file/action.
- Do not read or delete `backend/tdlib/` without explicit approval.
- Logs, artifacts, TDLib sessions, proxy credentials, raw TDLib paths, auth codes, and message bodies must not enter memory files.

## Application boundaries

- Workspace scoping is mandatory for user-owned resources.
- Auth context and FastAPI auth dependencies are canonically owned by
  `app.modules.auth`; `app.services.auth_context` is compatibility-only.
- User-facing runtime policy changes must persist in PostgreSQL instead of mutating process-local settings.
- Backend diagnostics must expose safe metadata only.
- Audit/operation metadata must be sanitized.
- `account_proxy.password_encrypted` must never be returned to the frontend.
- `warmup_event.payload_json` must not contain secrets, auth codes, proxy passwords, raw TDLib paths, or unsafe message bodies.

## Live Telegram/TDLib

- `TDLIB_LIVE_ENABLED=false` is the safe default.
- Story/profile/warmup live behavior requires explicit operator approval and feature gates.
- Live validation scripts may use backend port `8000`; dashboard local dev uses `8002`.

## Verification

- For security-sensitive backend changes, run targeted pytest plus `cd backend; python -m ruff check .`.
- For frontend auth/API contract changes, run targeted vitest/typecheck as applicable.
- Repository security baseline checks are CI, Test Quality, Semgrep, CodeQL
  Default Setup, Secret Scan, SBOM, and Container Scan. See
  `docs/security/security-baseline.md`.
