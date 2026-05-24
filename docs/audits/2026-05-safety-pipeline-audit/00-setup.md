# Phase 0 Setup Audit

Task: [#148](https://github.com/pinnnthreetriples/StylistTG/issues/148) — Task 42, Full safety pipeline audit.

Branch: `docs/safety-pipeline-full-audit`

Project status: moved from `Todo` to `In Progress`.

## Scope Guard

- Audit is read-only for production code.
- Allowed output path: `docs/audits/2026-05-safety-pipeline-audit/`.
- No live TDLib, Telegram, production DB, production Redis, deploys, migrations against production, or dependency installs.
- Missing tools are recorded with fallback instead of installed.

## Tool Inventory

| Tool | Installed | Version / evidence | Will be used for | Fallback |
| --- | --- | --- | --- | --- |
| `pytest` | yes | Python package `9.0.3`; `python -m pytest --version` | collection, targeted tests, coverage | targeted static review if collection blocked |
| `pytest-cov` | yes | Python package `7.1.0` | coverage report | manual test matrix if coverage blocked |
| `hypothesis` | yes | Python package `6.152.4` | property-based smoke where already supported | boundary-value manual tests |
| `bandit` | no | `PackageNotFoundError` | Python security scan | manual security review + existing tests |
| `mutmut` | yes | Python package `3.5.0` | optional mutation check if budget allows | document as unrun if too slow |
| `semgrep` | partial/no | CLI missing; Python package missing | tenant-scope static rule | inspect `.semgrep/tenant_scope.yaml` + targeted code review |
| `pip-audit` | yes as module | `python -m pip_audit --version` -> `2.10.0`; CLI not on PATH | dependency vulnerability smoke | module invocation |
| `ruff` | yes as module | `python -m ruff --version` -> `0.15.11`; CLI not on PATH | lint / format checks | module invocation |
| `alembic` | yes | `python -m alembic --version` -> `1.18.3` | migration head/replay checks | migration source review |
| `markdownlint` | no | CLI missing | markdown lint | manual markdown/link review |
| `jq` | no | CLI missing | JSON validation | PowerShell / Python JSON parsing |
| `node` | yes | `v24.11.0` | frontend checks | skip frontend commands if deps unavailable |
| `npm` | yes | `11.12.1` | frontend checks | skip if workspace deps absent |
| `gh` | yes | `2.87.3` | GitHub issue/project/PR metadata | GitHub connector / local git logs |
| `tools.test_analyzer` | yes | help command succeeded | test-quality audit | manual review |
| `.semgrep/tenant_scope.yaml` | yes | file exists | tenant rule source | manual rule inspection |

## Baseline

| Check | Result |
| --- | --- |
| Current branch | `docs/safety-pipeline-full-audit`, tracking `origin/main` |
| Git status | clean at branch creation |
| Open PRs | none returned by `gh pr list --state open --limit 20` |
| Migration files | 49 files in `backend/migrations/versions` |
| Alembic heads | single head: `20260523_0053 (head)` |
| `pytest tests --ignore=tests/contract --ignore=tests/benchmarks --collect-only -q` | failed after collecting 1770 tests because `prometheus_client` is missing |
| `pytest tests --collect-only -q` | stopped as runaway/no-output collect after the smaller collect exposed same dependency blocker |

## Environment Gaps

1. `prometheus_client` is missing in local Python, blocking collection for `tests/test_account_safety_gate.py` and `tests/test_safety_metrics.py`.
2. `bandit`, `semgrep`, `markdownlint`, and `jq` are not available on PATH / as Python packages.
3. `ruff`, `pip-audit`, `pytest`, and `alembic` are available through `python -m ...`, not shell command names.

## Dispatch Plan

Six sub-agents will write disjoint files:

| Agent | Output |
| --- | --- |
| A — Critical path deep audit | `01-critical-path-findings.md` |
| B — Tenancy + security + concurrency | `02-security-findings.md` |
| C — Failure modes + performance + observability | `03-resilience-findings.md` |
| D — Quality + integration coherence | `04-quality-findings.md` |
| E — Data integrity + migration safety + cascade | `05-data-findings.md` |
| F — Frontend + docs + spec compliance | `06-frontend-docs-findings.md` |

Each sub-agent must avoid production-code edits and write only its assigned markdown artifact.
