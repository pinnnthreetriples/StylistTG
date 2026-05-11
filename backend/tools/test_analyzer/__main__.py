"""Allow running as `python -m tools.test_analyzer`."""

import sys

from .cli import main

sys.exit(main())
