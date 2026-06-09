# Required Checks

Branch-protection changes live in GitHub settings. This file is a navigation checklist: verify current check names and workflow behavior against `.github/workflows/` and `.github/branch-protection.main.json` before changing settings.

## Required on `main`

Keep these status checks required when they exist with these names in GitHub branch protection:

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

## Source-of-truth lookup

| Question | Check first | Then check |
| --- | --- | --- |
| Which workflows currently exist? | `.github/workflows/` | GitHub Actions UI |
| Which check names should branch protection require? | `.github/branch-protection.main.json` | this file |
| What does CI actually run? | `.github/workflows/ci.yml` | workflow logs |
| What does the test-quality aggregator require? | `.github/workflows/test-quality.yml` | the aggregator job output |
| What do security scans run? | `.github/workflows/semgrep.yml`, `.github/workflows/secrets-scan.yml`, `.github/workflows/gitleaks.yml`, Trivy workflow files | workflow logs |
| Has workflow hardening drifted? | workflow files | this file's workflow policy section |

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

`contract-security` is a narrow hard subset for security-sensitive API contract regressions. `contract-fuzz` remains soft because it covers broader fuzzing and may be too noisy or expensive for every required PR path.

The aggregator intentionally does not require broad contract fuzz, benchmark, nightly, mutation, or live checks.

## Applying the canonical branch-protection ruleset (#272)

The canonical configuration ships as `.github/branch-protection.main.json`. Applying it requires a token with `admin:repo` scope and must be done by a human operator. Agents must not apply branch-protection settings unless the operator explicitly requests the exact action.

Apply via gh CLI:

```bash
gh api \
  -X PUT \
  repos/pinnnthreetriples/StylistTG/branches/main/protection \
  --input .github/branch-protection.main.json
```

Or import the same JSON via `Settings → Branches → main → Edit` in the GitHub web UI.

The configuration opts into:

- `strict: true` — required checks must be up-to-date with the base branch before merge.
- `enforce_admins: true` — admins cannot bypass.
- `required_linear_history: true` — no merge commits.
- `allow_force_pushes: false`, `allow_deletions: false`.
- `required_conversation_resolution: true`.
- `required_approving_review_count: 1` with `dismiss_stale_reviews: true`.

## Release/deploy gating

Release/deploy workflows should consult the latest `Nightly Backend Quality` run on `main` when a deploy path depends on backend health. When the run is red, release jobs should abort with a clear `nightly health is red — fix before deploying` message:

```bash
gh run list \
  --workflow="Nightly Backend Quality" \
  --branch main \
  --limit 1 \
  --json conclusion \
  --jq '.[0].conclusion'
```

Assert the output is `success` before proceeding with deploy.

## Workflow hardening policy

For new or changed workflows, prefer this hardening template unless a workflow-specific reason is documented in the workflow or PR:

- declare `permissions:` at the top, preferably `contents: read` by default;
- set `timeout-minutes` on jobs that can hang or consume CI minutes;
- set `concurrency:` for PR or branch workflows where superseded runs should cancel;
- avoid `continue-on-error: true` on quality-path steps.

Do not assume every existing workflow already meets this template. Verify the workflow file before citing this policy as current behavior. `test-quality.yml` is the strongest current template for least-privilege and timeout/concurrency posture.
