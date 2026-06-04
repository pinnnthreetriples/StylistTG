# Account Onboarding Artifact Security

Account onboarding artifacts are untrusted private inputs. They must be treated as backend-only until validation, materialization, and readonly verification complete.

## Rules

- No public uploads.
- No public or signed URLs.
- No raw object keys in frontend responses.
- No raw session data, TDLib paths, OTP, 2FA passwords, API hash, or proxy passwords in responses/logs/events.
- No extraction directly into TDLib storage.
- Unknown session formats are unsupported or require reauth.

## Archive Validation

Safe validation codes:

- `archive_missing`
- `archive_invalid`
- `archive_rejected_unsafe_path`
- `archive_rejected_symlink`
- `archive_rejected_too_many_files`
- `archive_rejected_too_deep`
- `archive_rejected_too_large`
- `archive_rejected_unsupported_compression`

The validator rejects absolute paths, path traversal, symlink entries, excessive file counts, excessive nesting, excessive uncompressed size, and invalid archives.

## Verification Boundary

`session_present=true`, `runtime_health=ready`, and account execution readiness are allowed only after readonly verification succeeds. Verification outcomes:

- `verified_ready`
- `requires_reauth`
- `tdlib_not_configured`
- `tdlib_unavailable`
- `identity_mismatch`
- `verification_timeout`
- `verification_failed`

