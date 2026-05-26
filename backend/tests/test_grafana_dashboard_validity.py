from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from prometheus_client import CollectorRegistry

from app import observability
from app.observability.safety_metrics import SafetyMetrics


DASHBOARD_PATH = Path("../docs/grafana/safety-pipeline.json")
METRIC_SELECTOR_RE = re.compile(r"(?<![\w:])([a-zA-Z_:][a-zA-Z0-9_:]*)(?=\s*(?:\{|\[))")
LABEL_VALUES_RE = re.compile(r"label_values\(\s*([a-zA-Z_:][a-zA-Z0-9_:]*)\s*,")


def _strings(value: Any):
    if isinstance(value, dict):
        for child in value.values():
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)
    elif isinstance(value, str):
        yield value


def _dashboard_metric_names(dashboard: dict[str, Any]) -> set[str]:
    metrics: set[str] = set()
    for text in _strings(dashboard):
        metrics.update(METRIC_SELECTOR_RE.findall(text))
        metrics.update(LABEL_VALUES_RE.findall(text))
    return metrics


def _registered_metric_names() -> set[str]:
    registry = CollectorRegistry()
    SafetyMetrics(registry=registry, enabled=True)
    return set(registry._names_to_collectors)


def test_safety_pipeline_dashboard_json_is_valid() -> None:
    assert json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))["uid"] == (
        "stylisttg-safety-pipeline"
    )


def test_safety_pipeline_dashboard_metrics_are_registered() -> None:
    dashboard = json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))

    missing = _dashboard_metric_names(dashboard) - _registered_metric_names()

    assert missing == set()


def test_dashboard_metric_validation_detects_missing_metric() -> None:
    dashboard = {"panels": [{"targets": [{"expr": "sum(unknown_metric_total[5m])"}]}]}

    missing = _dashboard_metric_names(dashboard) - _registered_metric_names()

    assert missing == {"unknown_metric_total"}


def test_observability_public_contract_exports_safety_metrics() -> None:
    assert observability.SafetyMetrics is SafetyMetrics
    assert isinstance(observability.safety_metrics, SafetyMetrics)
    assert hasattr(observability.safety_metrics, "weak_ggr_accounts_total")
    assert hasattr(observability.safety_metrics, "weak_ggr_transition")


def test_new_safety_metrics_reachable_through_public_observability_path() -> None:
    registry = CollectorRegistry()
    metrics = observability.SafetyMetrics(registry=registry, enabled=True)

    metrics.weak_ggr_accounts_total(workspace_id="workspace-1", value=2)
    metrics.weak_ggr_transition(workspace_id="workspace-1", from_bucket="medium")

    assert (
        registry.get_sample_value("weak_ggr_accounts_total", {"workspace_id": "workspace-1"}) == 2.0
    )
    assert (
        registry.get_sample_value(
            "weak_ggr_transitions_total",
            {"workspace_id": "workspace-1", "from_bucket": "medium"},
        )
        == 1.0
    )
