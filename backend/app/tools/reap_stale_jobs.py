from __future__ import annotations

from app.config import settings
from app.db import SessionLocal
from app.services.stale_jobs import reap_stale_jobs


def main() -> None:
    with SessionLocal() as session:
        reaped = reap_stale_jobs(session, stale_after_seconds=settings.stale_job_timeout_seconds)
    print(f"reaped_stale_jobs={reaped}")


if __name__ == "__main__":
    main()
