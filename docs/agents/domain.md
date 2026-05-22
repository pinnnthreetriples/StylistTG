# Domain Docs

StylistTG uses `.mex` as the compact project-memory and domain-doc entrypoint.

Start with `.mex/ROUTER.md`, then follow its routing table for the task type:

- Backend API/service work: `.mex/context/backend.md` and `.mex/patterns/backend-api-change.md`
- Frontend module/UI work: `.mex/context/frontend.md` and `.mex/patterns/frontend-module-change.md`
- Worker/queue/scheduler work: `.mex/context/workers.md` and `.mex/patterns/worker-queue-change.md`
- Warmup/account-preparation work: `.mex/context/warmup.md` and `.mex/patterns/warmup-change.md`
- Security/live TDLib/env work: `.mex/context/security.md` and `.mex/patterns/live-tdlib-safety.md`
- Setup/runtime work: `.mex/context/setup.md`
- Coding standards/review: `.mex/context/conventions.md`

Use `.mex/patterns/INDEX.md` to find the matching workflow before editing.

Do not duplicate `.mex` content here. This file tells project skills where to read domain language, constraints, and decision context.

