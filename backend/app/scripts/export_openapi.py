from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.main import app


def _normalize_openapi_schema(value: object) -> None:
    if isinstance(value, dict):
        if (
            value.get("type") == "object"
            and "properties" not in value
            and "additionalProperties" not in value
        ):
            value["additionalProperties"] = True
        for child in value.values():
            _normalize_openapi_schema(child)
    elif isinstance(value, list):
        for child in value:
            _normalize_openapi_schema(child)


def export_openapi(out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    _normalize_openapi_schema(schema)
    out.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the FastAPI OpenAPI schema without starting a server.")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    export_openapi(args.out)


if __name__ == "__main__":
    main()
