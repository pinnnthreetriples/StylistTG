from __future__ import annotations

import sys


def patch_windows_platform_probe() -> None:
    if sys.platform != "win32":
        return
    import platform

    platform.system = lambda: "Windows"
    platform.machine = lambda: "AMD64"


patch_windows_platform_probe()
