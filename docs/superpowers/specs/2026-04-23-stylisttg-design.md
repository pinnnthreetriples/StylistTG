# StylistTG Design

## Fixed Stack

- Telegram engine: TDLib.
- Backend: Python + FastAPI.
- Queue and workers: RQ + Redis.
- Database: PostgreSQL as system of record for account and job state.
- Frontend: React + TypeScript + shadcn/ui.
- File storage: local disk for v0.
- Execution model: one subprocess per job with a cold-start TDLib runtime.

## MVP Scope

- Auth: OTP-only.
- Accounts: one Telegram account.
- Operations: `set_name`, `set_bio`, `set_username`, `set_profile_photo`.

## Out of Scope for v0

- Stories.
- Profile music.
- Video.
- Batch multi-account workflows.
- S3 or MinIO.
- Preset/platform layers.

## Initial Project Shape

- `src/`: React admin UI scaffold.
- `backend/app/main.py`: FastAPI entrypoint.
- `backend/app/workers/profile_jobs.py`: RQ-callable subprocess boundary.
- `backend/app/tdlib_job.py`: placeholder for the future per-job TDLib runtime.
- `docker-compose.yml`: local PostgreSQL and Redis.
