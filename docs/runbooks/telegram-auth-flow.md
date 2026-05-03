# Telegram Auth Flow Runbook

This flow creates controlled TDLib authorization sessions. It does not bypass Telegram verification and does not enable profile/story/music jobs.

## API

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/accounts/auth-sessions -ContentType 'application/json' -Body '{"phone_number":"+15550102000","label":"operator test"}'
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/api/accounts/auth-sessions/<auth-session-id>
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/accounts/auth-sessions/<auth-session-id>/code -ContentType 'application/json' -Body '{"code":"<telegram-code>"}'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/accounts/auth-sessions/<auth-session-id>/password -ContentType 'application/json' -Body '{"password":"<2fa>"}'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/accounts/auth-sessions/<auth-session-id>/cancel
```

Reauth for an existing account:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/accounts/<account-id>/reauth-sessions -ContentType 'application/json' -Body '{"phone_number":"+15550102000"}'
```

## Safety Contract

- Auth starts only from explicit user/operator action.
- Codes and 2FA passwords are never persisted and must not be logged.
- Flood-wait errors create cooldowns instead of aggressive retries.
- Account linking happens only after TDLib reports `authorizationStateReady` and a safe `getMe` read.
- In default staging/mock mode, auth attempts fail safely with `tdlib_live_disabled`.
- Every auth action writes sanitized audit metadata.
