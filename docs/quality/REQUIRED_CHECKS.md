# Required Checks

Branch-protection changes live in GitHub settings. This file is the checklist for `main` branch protection.

## Required on `main`

Keep these checks required:

- `Backend (Python 3.12)`
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
