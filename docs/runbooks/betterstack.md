# Better Stack Observability

This project can send backend structured logs to Better Stack Telemetry and can expose Better Stack Uptime/Telemetry data to Codex through MCP.

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
