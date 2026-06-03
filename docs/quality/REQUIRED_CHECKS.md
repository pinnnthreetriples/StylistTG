# Required Checks

Branch-protection changes live in GitHub settings. This file is the checklist for `main` branch protection.

## Required on `main`

Keep these checks required:

- `Backend (Python 3.14)`
- `Frontend`
- `Browser QA`
- `Test Quality / test-quality-pr`
- `Semgrep / Semgrep CE`
- `Secrets Scan / Gitleaks PR diff`
- `Trivy / Trivy filesystem`
- `Trivy / Trivy backend image`

Recommended after the first green canonical run:

- `Trivy / Trivy tdlib image`

## Do not require

- `Test Quality / contract-fuzz`
- `Pytest Benchmark / *`
- `Nightly Backend Quality / *`
- `Complexity / Xenon complexity (soft)`

## Why `test-quality-pr` stays the required aggregator

`test-quality-pr` hides implementation-level job reshuffling from branch protection. The workflow can parallelize or rename internal jobs while GitHub branch protection continues to wait for one stable required status.

The aggregator currently requires:

```text
lint-format
typecheck
backend-tests
audit
duplication
contract-security
```

`contract-security` is a narrow hard subset for security-sensitive API contract regressions.
`contract-fuzz` remains soft because it covers broader fuzzing and may be too noisy or expensive for every required PR path.

The aggregator intentionally does not require broad contract fuzz, benchmark, nightly, mutation, or live checks.

## Applying the canonical branch-protection ruleset (#272)

The canonical configuration ships as `.github/branch-protection.main.json`.
Applying it requires a token with `admin:repo` scope and must be done
by a human operator — Claude/automation cannot apply branch-protection
settings.

Apply via gh CLI:

```bash
gh api \
  -X PUT \
  repos/pinnnthreetriples/StylistTG/branches/main/protection \
  --input .github/branch-protection.main.json
```

Or import the same JSON via `Settings → Branches → main → Edit` in the
GitHub web UI.

The configuration opts into:

- `strict: true` — required checks must be up-to-date with the base
  branch before merge.
- `enforce_admins: true` — admins cannot bypass.
- `required_linear_history: true` — no merge commits.
- `allow_force_pushes: false`, `allow_deletions: false`.
- `required_conversation_resolution: true`.
- `required_approving_review_count: 1` with `dismiss_stale_reviews: true`.

## Release/deploy gating

Release/deploy workflows must consult the latest `Nightly Backend
Quality` run on `main`. When the run is red, release jobs must abort
with a clear `nightly health is red — fix before deploying` message:

```bash
gh run list \
  --workflow="Nightly Backend Quality" \
  --branch main \
  --limit 1 \
  --json conclusion \
  --jq '.[0].conclusion'
```

Assert the output is `success` before proceeding with deploy.

## Workflow least-privilege checklist

Every workflow under `.github/workflows/` must:

- declare `permissions:` at the top (default `contents: read`);
- set `timeout-minutes` on every job (PR ≤ 30, nightly ≤ 60);
- set `concurrency:` so superseded PR runs cancel in-progress;
- avoid `continue-on-error: true` on quality-path steps (enforced by
  the regression test from #262).

The PR workflow `test-quality.yml` and nightly workflow
`nightly-backend-quality.yml` already meet this template.
