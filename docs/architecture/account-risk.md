# Account Risk Foundation

Account Risk is an app-known readiness score. It is not a Telegram anti-ban guarantee and does not perform live TDLib checks.

The current scoring lives in the dashboard at:

- `apps/dashboard/src/features/accounts/accountRisk.ts`

Inputs are safe, already-known API data:

- account state and runtime health;
- account safety summary;
- proxy summary;
- active cooldowns.

Levels:

- `low`: 0-24
- `medium`: 25-59
- `high`: 60-79
- `critical`: 80-100

Risk reasons are deterministic and visible in the UI. The Accounts table shows a risk column, and Health Center shows aggregate risk counts.

Future work can move this scoring to a tenant-scoped read-only backend endpoint when the API contract stabilizes. That endpoint must not call live Telegram/TDLib and must not expose secrets or session paths.
