from __future__ import annotations

from scripts import mutation_suite


def test_soft_mutation_gate_treats_survived_mutants_as_soft_failures() -> None:
    hard, soft = mutation_suite._classify_failures(
        {
            "score": 51.0,
            "survived": 10,
            "returncodes": {"run": 0, "export_cicd_stats": 0, "results": 0},
        },
        min_score=65.0,
    )

    assert hard == []
    assert soft == ["mutation score 51.0% < 65.0%", "10 mutants survived"]


def test_soft_mutation_gate_treats_incomplete_report_as_hard_failure() -> None:
    hard, soft = mutation_suite._classify_failures(
        {
            "error": "mutmut generated mutants but did not check them",
            "score": 0.0,
            "survived": 0,
            "returncodes": {"run": 0, "export_cicd_stats": 0, "results": 0},
        },
        min_score=65.0,
    )

    assert hard == ["mutmut generated mutants but did not check them"]
    assert soft == ["mutation score 0.0% < 65.0%"]
