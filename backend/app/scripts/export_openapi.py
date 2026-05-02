from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.main import app


def export_openapi(out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the FastAPI OpenAPI schema without starting a server.")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    export_openapi(args.out)


if __name__ == "__main__":
    main()
