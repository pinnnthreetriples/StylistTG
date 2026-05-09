# Better Stack Observability

This project can send backend structured logs to Better Stack Telemetry, send sanitized application errors to Better Stack Errors through Sentry-compatible SDKs, and expose Better Stack Uptime/Telemetry data to Codex through MCP.

## Error Tracking

Better Stack Errors uses Sentry-compatible DSNs. Use the SDKs as clients only; do not configure sentry.io SaaS.

Create or reuse these Better Stack Errors applications:

- `stylisttg-api` - Python / FastAPI backend
- `stylisttg-worker` - Python / RQ worker
- `stylisttg-dashboard` - JavaScript browser / React dashboard

The DSN format is:

```text
https://<APPLICATION_TOKEN>@<INGESTING_HOST>/1
```

Do not commit real DSNs. Configure them only in the host environment:

```env
# Northflank API service
BETTER_STACK_API_DSN=
SENTRY_ENVIRONMENT=staging
SENTRY_RELEASE=

# Northflank worker service
BETTER_STACK_WORKER_DSN=
SENTRY_ENVIRONMENT=staging
SENTRY_RELEASE=

# Cloudflare Pages
VITE_BETTER_STACK_DASHBOARD_DSN=
VITE_APP_ENV=staging
VITE_SENTRY_RELEASE=
```

The SDK configuration keeps performance tracing and session replay disabled. Events are sanitized before sending; request bodies, authorization headers, cookies, tokens, database/Redis URLs, Telegram credentials, proxy credentials, TDLib/session paths, and similar sensitive fields are filtered.

Safe test commands:

```powershell
cd backend
python -m app.scripts.raise_api_observability_error
python -m app.scripts.raise_worker_observability_error
```

For the dashboard, run the Vite dev server with `VITE_BETTER_STACK_DASHBOARD_DSN` set, open the app locally, and run this in the browser console:

```js
window.__STYLISTTG_CAPTURE_TEST_ERROR__()
```

Then check the matching Better Stack Errors application for a `StylistTG ... observability test error` event.

## Backend Telemetry

The backend keeps logging to stderr and local JSONL files by default. Better Stack forwarding is enabled only when both variables are present:

```env
BETTERSTACK_SOURCE_TOKEN=<Better Stack telemetry source token>
BETTERSTACK_INGESTING_HOST=<ingesting host from the source data-ingestion tab>
```

Optional:

```env
BETTERSTACK_REQUEST_TIMEOUT_SECONDS=0.5
```

Use a Telemetry source token for log ingestion. A global Better Stack API token is for API/MCP access and should not be used as the log source token.

If Better Stack ingestion is temporarily unavailable, the backend backs off repeated send attempts so API responses are not repeatedly delayed by logging failures.

## Codex MCP

Configure Codex MCP with the remote Better Stack server through `mcp-remote` and keep the token in the local environment:

```toml
[mcp_servers.betterstack]
command = "powershell"
args = [
  "-NoProfile",
  "-ExecutionPolicy",
  "Bypass",
  "-Command",
  "npx -y mcp-remote https://mcp.betterstack.com --header \"Authorization: Bearer $env:BETTERSTACK_API_TOKEN\"",
]
startup_timeout_sec = 30.0
```

Set `BETTERSTACK_API_TOKEN` outside the repository. Do not commit global API tokens, source tokens, or generated MCP auth files.

## Verification

1. Restart the backend after setting telemetry env variables.
2. Trigger a safe endpoint, for example `/ready`.
3. Check Better Stack Telemetry Live tail for `event=http_request`.
4. Restart Codex after adding MCP config, then ask for the current Better Stack monitor status.
