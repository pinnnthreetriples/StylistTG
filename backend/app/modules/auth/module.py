from __future__ import annotations

from app.modules.contracts import FeatureModule


module = FeatureModule(name="auth", workflows=(), router_path=None)


__all__ = ["module"]
