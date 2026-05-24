# Tools Coverage Matrix

| Tool / method | Covered | Findings produced | Gaps |
| --- | --- | --- | --- |
| Serena activation + project instructions | Project bootstrap and code-navigation discipline | None directly | Symbol editing not needed because audit writes docs only. |
| Semble semantic search | Critical-path discovery, sender equivalent, security/concurrency paths | F-003, F-004, F-008, B F-002/B F-003/B F-004/B F-005, D integration findings | Search is advisory; final evidence came from file/line reads. |
| `rg` / targeted PowerShell reads | Exact callsites, metrics names, time calls, TODOs, contracts | Most findings | Does not prove runtime behavior alone. |
| `python -m ruff check` targeted files | Backend quality smoke | No new finding | Not a full repo lint pass. |
| `tools.test_analyzer` targeted safety tests | Test quality rules on safety gate/E2E tests | Supported F-042 review context; no analyzer findings | Full test tree not analyzed in one command. |
| Targeted pytest | `test_ggr_calculator.py`, `test_account_quarantine.py` | No direct finding; confidence for no-issue checks | Full collection blocked by missing `prometheus_client`; sender command incomplete. |
| Dashboard typecheck + targeted Vitest | Safety UI surfaces | F-006-001/F-006-003 context; no test failures | Full coverage/ESLint/browser/a11y not run. |
| `gh pr list` / issue/project reads | PR/task inventory and branch/board status | Task/PR matrix context | Some Task 41 details are PR-based, not spec-heading based. |
| Alembic head/file count | Migration baseline | F-E002 context | Full replay not run without disposable DB. |
| Grafana JSON parse/static query inspection | Dashboard validity and metric names | F-302/F-006-002 | No live Prometheus/Grafana datasource. |
| Redaction smoke command | Secret/PII sanitizer behavior | B F-001 | No full audit API round-trip test run. |

## Tool Gaps

- `semgrep` CLI missing: tenant rule existence reviewed, execution not verified.
- `bandit` missing: security scan replaced by targeted security review.
- `markdownlint` missing: markdown syntax reviewed manually and by plain file reads.
- `jq` missing: JSON checks done through PowerShell/Python-capable fallbacks when used.
- `prometheus_client` missing locally: full backend collection blocked.
- No disposable Postgres dataset: migration replay and FK orphan checks are static/inconclusive.

## Coverage Confidence

| Area | Confidence | Why |
| --- | --- | --- |
| Critical backend correctness | Medium-high | Line review + targeted tests; sender tests incomplete. |
| Security/tenancy/concurrency | Medium | Strong static evidence; semgrep unavailable. |
| Observability | Medium-high | Metric source/runbook/dashboard compared statically. |
| Data/migration readiness | Medium | Static constraints reviewed; replay not run. |
| Frontend/docs | Medium-high | Typecheck and targeted tests passed. |
