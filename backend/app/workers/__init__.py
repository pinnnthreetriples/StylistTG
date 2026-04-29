"""RQ worker package.

RQ resolves dotted function paths through package attributes on some versions,
so keep worker modules explicitly importable from ``app.workers``.
"""

from importlib import import_module

account_update_jobs = import_module("app.workers.account_update_jobs")
profile_jobs = import_module("app.workers.profile_jobs")

__all__ = ["account_update_jobs", "profile_jobs"]
