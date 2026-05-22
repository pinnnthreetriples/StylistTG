# Security Baseline

## Enabled Checks

- CI: backend, frontend, OpenAPI, Docker build, dependency audit, and tests.
- Test Quality: backend lint/format, coverage, full-suite and changed-tests
  test analyzer, hard Pyright, pip-audit, soft Schemathesis fuzzing, hard
  contract-security, and duplicate detection.
- Semgrep: static analysis with repository custom rules.
- CodeQL: GitHub CodeQL Default Setup for Python and JavaScript/TypeScript code
  scanning. Do not add an advanced CodeQL workflow while Default Setup is
  enabled for this repository.
- Secrets Scan: Gitleaks PR diff with redacted SARIF output.
- SBOM: Syft SPDX JSON artifacts for backend, frontend/root workspace, and the
  backend container image.
- Trivy: filesystem plus backend and TDLib image scans.

## Merge Blocking

CI, Test Quality hard gates, Semgrep, CodeQL Default Setup failures, Secrets Scan
findings, Trivy filesystem HIGH/CRITICAL findings, and Trivy CRITICAL image
vulnerabilities should block merge. SBOM
generation is an artifact gate: generation failures block merge, but SBOM
contents are triaged separately unless another scanner flags a blocking issue.

Trivy image HIGH findings are reported for triage but do not block during this
baseline phase. Promote image HIGH to blocking only after the backlog is reviewed.

## Triage

1. Confirm the finding is in code or dependencies reachable by this repository.
2. Check whether it affects local-only tooling, test fixtures, or production
   runtime.
3. Fix by upgrading, removing, or isolating the dependency or code path.
4. Link the finding and remediation in the PR.
5. If a finding is accepted temporarily, document owner, expiry, and mitigation.

## Secret Handling

If a secret is leaked:

1. Revoke or rotate it immediately in the source system.
2. Remove it from code, logs, artifacts, and docs.
3. Re-run Gitleaks with redaction.
4. Treat historical exposure as compromised even if the repo is private.

Allowlist only stable test fixtures or placeholders that cannot authenticate to
real systems. Keep allowlists narrow by regex or path and include a comment.
Never allowlist real-looking cloud, Telegram, database, Redis, Supabase, or API
credentials.

## False Positives

Prefer changing fixture text to obviously fake values over allowlisting. If an
allowlist is required, include a short reason in `.gitleaks.toml` and keep it
specific enough that a real secret nearby would still be detected.

## Branch Protection Recommendation

Require these checks on `main` when GitHub branch protection is available:

- CI
- Test Quality
- Semgrep
- CodeQL Default Setup
- Secrets Scan
- SBOM
- Trivy

This repository does not encode branch protection settings in code.
