# Telegram Session Handling

Telegram account/session material is sensitive backend-only data.

## Never Expose

- TDLib database/files paths;
- session auth keys;
- Telegram auth code;
- 2FA password;
- `TELEGRAM_API_HASH`;
- proxy passwords;
- raw import archive paths or filenames that contain secrets.

## Storage Boundaries

TDLib runtime data is isolated by workspace and account or auth-session ID. It is not an application asset and must not be exposed through public asset URLs.

Import packages are private and preview-first. They are validated for shape and safety, but unsupported session formats require manual reauthorization.

## Frontend Handling

The auth wizard keeps code/password values only in component state and clears them immediately after submit. Browser QA uses mock fixtures only.

## Logs and Audit

Audit events record action metadata and redacted hints. They must not include auth codes, passwords, session paths, API hash, or uploaded file contents.
