from __future__ import annotations


def test_legacy_warmup_service_imports_remain_available() -> None:
    from app.services import warmup

    for name in (
        "warmup_operation_policy",
        "write_warmup_event",
        "create_warmup_session",
        "list_warmup_sessions",
        "get_warmup_session",
    ):
        assert callable(getattr(warmup, name))


def test_legacy_worker_and_dispatch_services_remain_available() -> None:
    from app.services import warmup_dispatch, warmup_worker

    assert callable(warmup_worker.process_due_warmup_sessions)
    assert callable(warmup_dispatch.process_due_warmup_dispatches)


def test_module_facades_are_canonical_owners() -> None:
    from app.modules.warmup import dispatcher, events, service, worker

    assert service.warmup_operation_policy.__module__ == "app.modules.warmup.service"
    assert events.write_warmup_event.__module__ == "app.modules.warmup.events"
    assert worker.process_due_warmup_sessions.__module__ == "app.modules.warmup.worker"
    assert dispatcher.process_due_warmup_dispatches.__module__ == "app.modules.warmup.dispatcher"


def test_module_warmup_does_not_import_legacy_worker_entrypoints() -> None:
    from pathlib import Path

    module_sources = "\n".join(
        path.read_text(encoding="utf-8") for path in Path("app/modules/warmup").glob("*.py")
    )

    assert "app.workers.warmup" not in module_sources
