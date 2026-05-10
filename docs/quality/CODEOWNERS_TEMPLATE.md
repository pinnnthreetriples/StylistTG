# CODEOWNERS Template

Copy this file to `.github/CODEOWNERS` and replace `@placeholder` with real GitHub usernames or team handles.

```
# Backend core
backend/app/api/                @placeholder
backend/app/services/           @placeholder
backend/app/workers/            @placeholder
backend/app/adapters/           @placeholder
backend/app/config.py           @placeholder
backend/app/models.py           @placeholder
backend/app/schemas.py          @placeholder

# Security-sensitive
backend/app/services/auth_context.py      @placeholder
backend/app/services/tenant_scope.py      @placeholder
backend/app/services/secret_redaction.py  @placeholder
backend/app/services/supabase_jwt.py      @placeholder
backend/app/storage/                      @placeholder

# Migrations
backend/migrations/             @placeholder

# Frontend
apps/dashboard/                 @placeholder
packages/api-client/            @placeholder
packages/ui/                    @placeholder
packages/config/                @placeholder

# CI / Infrastructure
.github/                        @placeholder
docker-compose.yml              @placeholder
render.yaml                     @placeholder

# Quality / Docs
docs/quality/                   @placeholder
docs/runbooks/                  @placeholder
backend/tests/                  @placeholder
```
