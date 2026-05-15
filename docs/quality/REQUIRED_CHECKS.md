# Required Checks

This repository keeps branch-protection changes in GitHub settings, not in code.
Use this page as the checklist for `main` branch protection.

## Current Required Checks

The current `main` branch protection requires:

- `Backend (Python 3.12)`
- `Frontend`
- `Browser QA`

## Recommended Required Checks

After the quality/security gate expansion, require:

- `Backend (Python 3.12)`
- `Frontend`
- `Browser QA`
- `Test Quality / test-quality-pr`
- `Semgrep / Semgrep CE`
- `Secrets Scan / Gitleaks PR diff`
- `Trivy / Trivy filesystem`
- `Trivy / Trivy backend image`

Keep `Complexity / Xenon complexity (soft)` optional until the project promotes the
Xenon threshold to a hard gate.

## Rationale

- Backend and Frontend are the existing CI merge blockers.
- Browser QA is path-filtered but should stay required so dashboard/browser PRs cannot skip it silently.
- Test Quality carries backend coverage, analyzer, jscpd, and slow quality signals.
- Semgrep, Secrets Scan, and Trivy are security gates and should block production-bound changes.
- Complexity is intentionally soft in this PR to avoid production refactors just to satisfy a new metric.
