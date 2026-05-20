from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CrossModuleName = Literal["warmup", "commenting", "editing", "other"]
CrossModuleLoadBreakdown = dict[CrossModuleName, int]


class CrossModuleLoad(BaseModel):
    last_hour: int = Field(ge=0)
    last_24h: int = Field(ge=0)
    breakdown: CrossModuleLoadBreakdown

    model_config = ConfigDict(frozen=True)


__all__ = ["CrossModuleLoad", "CrossModuleLoadBreakdown", "CrossModuleName"]
