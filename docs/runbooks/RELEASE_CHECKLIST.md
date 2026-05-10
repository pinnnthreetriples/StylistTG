# Release Checklist

Pre-release verification commands. Run all before tagging a release.

## Backend

```bash
cd backend

# Lint
python -m ruff check .

# Tests
python -m pytest

# Coverage report
python -m pytest --cov=app --cov-report=term-missing

# Database migration
python -m alembic upgrade head

# Migration smoke test
python -m app.tools.migration_smoke

# Compile check
python -m compileall app
```

## Frontend

```bash
# OpenAPI drift check
npm run check:api

# Lint
npm run lint

# Tests
npm test

# Type check
npm run typecheck

# Production build
npm run build

# Browser QA
npm run qa:browser
```

## Docker

```bash
docker build -f backend/Dockerfile -t stylisttg-backend:test .
```

## Final Checks

- [ ] All CI checks green on the release branch
- [ ] No `FIXME` or `TODO` in security-critical paths
- [ ] Migration is backwards-compatible or coordinated with deploy
- [ ] Environment variables documented if new ones were added
- [ ] `.mex/` memory and `AGENT_HANDOFF.md` updated if stable architecture or operational knowledge changed
