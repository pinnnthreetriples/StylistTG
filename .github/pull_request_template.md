## Summary

## Risk Area
- [ ] Auth / roles
- [ ] Workspace isolation
- [ ] PII / secrets
- [ ] Jobs / workers
- [ ] Runtime roles / queues
- [ ] Storage / uploads
- [ ] Migrations
- [ ] Frontend API contract
- [ ] UI only

## Architecture Boundaries
- [ ] Module contracts have no ORM/runtime imports
- [ ] Routers remain thin presentation boundaries
- [ ] Repositories own ORM query helpers
- [ ] Legacy wrappers stay compatibility-only
- [ ] Cross-module imports use documented public surfaces

## Runtime Impact
- [ ] No new queue name
- [ ] No new workflow type
- [ ] Runtime role metadata updated if queue/process ownership changed
- [ ] No API/worker process mixing introduced

## OpenAPI Impact
- [ ] No public schema/route change
- [ ] OpenAPI artifacts checked or regenerated intentionally

## Frontend Impact
- [ ] No visible UX change
- [ ] Module boundary imports checked
- [ ] Generated API client compatibility preserved

## Migration Impact
- [ ] No migration/model change
- [ ] Migration included and reversible if applicable

## TDLib / Live Impact
- [ ] No live TDLib behavior change
- [ ] No session path exposure
- [ ] Live gates remain disabled by default

## Tests
- [ ] Backend unit/API tests
- [ ] PostgreSQL/Redis integration tests
- [ ] Frontend tests
- [ ] Browser QA
- [ ] OpenAPI drift check
- [ ] Manual staging smoke

## Regression Coverage
- [ ] This PR fixes a bug and includes a regression test
- [ ] Not applicable

## Security Checklist
- [ ] No new unauthenticated endpoint
- [ ] No cross-workspace data access
- [ ] No full PII exposed to viewer role
- [ ] No secrets in logs/errors/Sentry
- [ ] Production config remains safe

## Validation

## Not Run
