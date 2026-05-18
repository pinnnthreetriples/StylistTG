# Legacy Wrapper Audit

Legacy wrappers remain for import compatibility while canonical ownership moves
to `app.modules`. Do not add behavior to these files.

| Legacy path | Canonical owner | Current reason to keep | Allowed imports | Forbidden changes | Planned removal condition | Known call-sites |
| --- | --- | --- | --- | --- | --- | --- |
| `app.api.account_update` | `app.modules.account_editing.router` | Preserve public import path for `/api/account-update`. | `sys`, canonical router module. | New route logic, auth changes, response mapping. | Remove only after router import audit shows no `app.api.account_update` users. | `backend/tests/api/test_account_update_api.py`. |
| `app.api.warmup` | `app.modules.warmup.router` | Preserve public import path for `/api/warmup`. | `sys`, canonical router module. | New route logic, auth changes, response mapping. | Remove only after router import audit shows no `app.api.warmup` users. | `backend/tests/warmup/test_warmup_foundation.py`. |
| `app.services.account_update_jobs` | `app.modules.account_editing.service` | Preserve old preview/job creation service imports. | Canonical account editing service/errors and stable shared types. | Planning, validation, enqueue, or execution behavior. | Remove after service call-sites migrate to `app.modules.account_editing.service`. | Account update API/tests, worker hardening tests, security regression tests, account safety tests. |
| `app.services.account_update_plan` | `app.modules.account_editing.planner` | Preserve old planner imports. | Canonical planner exports only. | Planning algorithm or constants ownership. | Remove after planner call-sites migrate to `app.modules.account_editing.planner`. | Account plan/orchestrator tests. |
| `app.services.auth_context` | `app.modules.auth.dependencies` / `app.modules.auth.context` | Preserve existing auth dependency imports and dependency override keys. | Canonical auth context/dependency/service exports only. | Auth resolution, role policy, workspace membership, or error mapping behavior. | Remove after API routers and tests migrate to `app.modules.auth`. | API routers, module routers, security tests, workspace onboarding tests. |
| `app.workers.account_update_jobs` | `app.modules.account_editing.executor` | Preserve old RQ worker import path. | Canonical executor exports only. | Worker execution or rematerialization behavior. | Remove after worker entrypoint call-sites migrate to `app.modules.account_editing.jobs` or executor. | Worker hardening tests and account orchestrator tests. |
| `app.services.warmup` | `app.modules.warmup.service` | Preserve old warmup service imports. | Canonical warmup service/repository/events exports only. | Warmup session, event, policy, or queue behavior. | Remove after warmup service call-sites migrate to module surfaces. | Account APIs, warmup API tests, warmup runtime tests, warmup helpers. |
| `app.services.warmup_worker` | `app.modules.warmup.worker` | Preserve old warmup worker service imports. | Canonical worker exports only. | Due-session processing behavior. | Remove after runtime tests and callers migrate to `app.modules.warmup.worker`. | Warmup worker and dispatch tests. |
| `app.services.warmup_dispatch` | `app.modules.warmup.dispatcher` | Preserve old dispatch service imports. | Canonical dispatcher exports only. | Dispatch scheduling, live/shadow execution behavior. | Remove after dispatch callers migrate to `app.modules.warmup.dispatcher`. | Warmup dispatch/passive/network tests. |
| `app.services.warmup_isolation` | `app.modules.warmup.isolation` | Preserve old isolation imports. | Canonical isolation exports only. | Claim acquire/release behavior. | Remove after isolation callers migrate to `app.modules.warmup.isolation`. | Warmup isolation/API/dispatch tests. |
| `app.services.warmup_readiness` | `app.modules.warmup.readiness` | Preserve old readiness imports. | Canonical readiness exports only. | Readiness checks or messages. | Remove after readiness callers migrate to `app.modules.warmup.readiness`. | Warmup readiness tests. |
| `app.services.warmup_p2p` | `app.modules.warmup.p2p` | Preserve old p2p imports. | Canonical p2p exports only. | Peer selection/contact recording behavior. | Remove after p2p callers migrate to `app.modules.warmup.p2p`. | Warmup network/advanced tests. |
| `app.workers.warmup_jobs` | `app.modules.warmup.jobs` | Preserve old RQ due-session worker path. | Canonical warmup jobs module only. | No-arg handler signature or due-session behavior. | Remove after worker configs and imports use module job paths only. | Workflow registry compatibility tests. |
| `app.workers.warmup_dispatch_jobs` | `app.modules.warmup.jobs` | Preserve old RQ dispatch worker path. | Canonical warmup jobs module only. | No-arg handler signature or dispatch behavior. | Remove after worker configs and imports use module job paths only. | Workflow registry compatibility tests. |

Deprecation process:

- `docs/architecture/legacy-wrapper-deprecation-plan.md` defines the staged removal policy.
- `docs/architecture/legacy-wrappers.json` is the deterministic machine-readable wrapper manifest.
- `backend/scripts/legacy_wrapper_audit.py` validates the committed manifest; `--print` emits the deterministic manifest to stdout.

All wrappers remain in Stage 0 compatibility active. This audit does not remove
wrappers, emit runtime deprecation warnings, rename paths, or change exports.
Architecture tests enforce that feature modules do not import these wrappers and
that wrapper files keep compatibility-owner docstrings.
