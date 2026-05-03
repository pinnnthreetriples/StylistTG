from __future__ import annotations

import json

from app.services.scheduler import scheduler_report


def main() -> None:
    print(json.dumps(scheduler_report().to_dict(), indent=2))


if __name__ == "__main__":
    main()
