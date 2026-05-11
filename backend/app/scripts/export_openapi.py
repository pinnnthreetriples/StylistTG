from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from app.main import app


def _normalize_openapi_schema(value: object) -> None:
    if isinstance(value, dict):
        schema = cast(dict[str, Any], value)
        if (
            schema.get("type") == "object"
            and "properties" not in schema
            and "additionalProperties" not in schema
        ):
            items = list(schema.items())
            schema.clear()
            schema["additionalProperties"] = True
            schema.update(items)
        for child in schema.values():
            _normalize_openapi_schema(child)
    elif isinstance(value, list):
        for child in cast(list[Any], value):
            _normalize_openapi_schema(child)


def export_openapi(out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    _normalize_openapi_schema(schema)
    out.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export the FastAPI OpenAPI schema without starting a server."
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    export_openapi(args.out)


if __name__ == "__main__":
    main()
