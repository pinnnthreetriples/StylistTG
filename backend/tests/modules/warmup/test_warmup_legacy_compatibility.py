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


def test_legacy_warmup_service_exports_canonical_module_functions() -> None:
    from app.modules.warmup import events, repository, service
    from app.services import warmup

    assert warmup.create_warmup_session is service.create_warmup_session
    assert warmup.list_warmup_sessions is repository.list_warmup_sessions
    assert warmup.get_warmup_session is repository.get_warmup_session
    assert warmup.write_warmup_event is events.write_warmup_event


def test_legacy_warmup_wrappers_have_owner_docstrings() -> None:
    from app.services import (
        warmup,
        warmup_dispatch,
        warmup_isolation,
        warmup_p2p,
        warmup_readiness,
        warmup_worker,
    )

    wrappers = (
        warmup,
        warmup_dispatch,
        warmup_isolation,
        warmup_p2p,
        warmup_readiness,
        warmup_worker,
    )
    for wrapper in wrappers:
        assert wrapper.__doc__ is not None
        assert "Compatibility wrapper." in wrapper.__doc__
        assert "Canonical owner: app.modules.warmup." in wrapper.__doc__
        assert "Do not add new behavior here." in wrapper.__doc__


def test_legacy_worker_and_dispatch_services_remain_available() -> None:
    from app.services import warmup_dispatch, warmup_worker

    assert callable(warmup_worker.process_due_warmup_sessions)
    assert callable(warmup_dispatch.process_due_warmup_dispatches)


def test_module_facades_are_canonical_owners() -> None:
    from app.modules.warmup import dispatcher, events, repository, service, worker

    assert service.warmup_operation_policy.__module__ == "app.modules.warmup.queries"
    assert events.write_warmup_event.__module__ == "app.modules.warmup.events"
    assert repository.list_warmup_sessions.__module__ == "app.modules.warmup.repository"
    assert worker.process_due_warmup_sessions.__module__ == "app.modules.warmup.worker"
    assert dispatcher.process_due_warmup_dispatches.__module__ == "app.modules.warmup.dispatcher"


def test_warmup_service_facade_reexports_query_functions() -> None:
    from app.modules.warmup import queries, service

    assert service.get_warmup_readiness is queries.get_warmup_readiness
    assert service.validate_warmup is queries.validate_warmup
    assert service.list_warmup_strategies is queries.list_warmup_strategies
    assert service.list_warmup_sessions_page is queries.list_warmup_sessions_page
    assert service.get_warmup_session_detail is queries.get_warmup_session_detail
    assert service.get_warmup_session_status is queries.get_warmup_session_status
    assert service.list_warmup_session_events_page is queries.list_warmup_session_events_page
    assert service.get_warmup_isolation_status is queries.get_warmup_isolation_status
    assert service.warmup_operation_policy is queries.warmup_operation_policy


def test_warmup_service_facade_reexports_command_functions() -> None:
    from app.modules.warmup import commands, service

    assert service.create_warmup_session is commands.create_warmup_session
    assert service.create_warmup_session_use_case is commands.create_warmup_session_use_case
    assert service.pause_warmup_session is commands.pause_warmup_session
    assert service.pause_warmup_session_use_case is commands.pause_warmup_session_use_case
    assert service.resume_warmup_session is commands.resume_warmup_session
    assert service.resume_warmup_session_use_case is commands.resume_warmup_session_use_case
    assert service.delete_warmup_session is commands.delete_warmup_session
    assert service.delete_warmup_session_use_case is commands.delete_warmup_session_use_case


def test_warmup_service_facade_reexports_read_model_functions() -> None:
    from app.modules.warmup import read_models, service

    assert service.session_read is read_models.session_read
    assert service.session_summary is read_models.session_summary


def test_module_warmup_does_not_import_legacy_worker_entrypoints() -> None:
    from pathlib import Path

    module_sources = "\n".join(
        path.read_text(encoding="utf-8") for path in Path("app/modules/warmup").glob("*.py")
    )

    assert "app.workers." + "warmup" not in module_sources
