"""Reporter classes for text, JSON, and SARIF output."""

from __future__ import annotations

import json
from typing import Any

from ..models import Issue, Severity


class TextReporter:
    def report(self, issues: list[Issue]) -> str:
        lines: list[str] = []
        for issue in issues:
            sev = issue.severity.name
            lines.append(
                f"[{sev}] {issue.file}:{issue.line} | {issue.rule_id} | "
                f"{issue.rule_type} | {issue.message} -> {issue.recommendation}"
            )
        return "\n".join(lines)


class JsonReporter:
    def report(self, issues: list[Issue]) -> str:
        by_severity: dict[str, int] = {}
        by_type: dict[str, int] = {}
        by_file: dict[str, int] = {}
        for issue in issues:
            sev = issue.severity.name
            by_severity[sev] = by_severity.get(sev, 0) + 1
            by_type[issue.rule_type] = by_type.get(issue.rule_type, 0) + 1
            by_file[issue.file] = by_file.get(issue.file, 0) + 1

        data: dict[str, Any] = {
            "summary": {
                "total": len(issues),
                "by_severity": by_severity,
                "by_type": by_type,
                "by_file": by_file,
            },
            "issues": [
                {
                    "rule_id": i.rule_id,
                    "rule_type": i.rule_type,
                    "severity": i.severity.name,
                    "file": i.file,
                    "line": i.line,
                    "message": i.message,
                    "recommendation": i.recommendation,
                    "fingerprint": i.fingerprint(),
                }
                for i in issues
            ],
        }
        return json.dumps(data, indent=2)


class SarifReporter:
    SARIF_VERSION = "2.1.0"
    SCHEMA_URI = (
        "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json"
    )

    def report(self, issues: list[Issue]) -> str:
        rules_map: dict[str, dict[str, Any]] = {}
        results: list[dict[str, Any]] = []

        for issue in issues:
            if issue.rule_id not in rules_map:
                rules_map[issue.rule_id] = {
                    "id": issue.rule_id,
                    "shortDescription": {"text": f"[{issue.rule_type}] {issue.rule_id}"},
                    "defaultConfiguration": {"level": self._severity_to_level(issue.severity)},
                }

            results.append(
                {
                    "ruleId": issue.rule_id,
                    "level": self._severity_to_level(issue.severity),
                    "message": {"text": f"{issue.message} \u2192 {issue.recommendation}"},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": issue.file},
                                "region": {"startLine": issue.line},
                            }
                        }
                    ],
                    "partialFingerprints": {"primaryLocationLineHash": issue.fingerprint()},
                }
            )

        sarif: dict[str, Any] = {
            "$schema": self.SCHEMA_URI,
            "version": self.SARIF_VERSION,
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "test-quality-analyzer",
                            "version": "1.0.0",
                            "informationUri": ("https://github.com/pinnnthreetriples/StylistTG"),
                            "rules": list(rules_map.values()),
                        }
                    },
                    "automationDetails": {"id": "test-quality"},
                    "results": results,
                }
            ],
        }
        return json.dumps(sarif, indent=2)

    @staticmethod
    def _severity_to_level(severity: Severity) -> str:
        if severity == Severity.CRITICAL:
            return "error"
        elif severity == Severity.WARNING:
            return "warning"
        return "note"
