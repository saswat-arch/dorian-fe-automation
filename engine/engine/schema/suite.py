from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

RunMode = Literal["fail-fast", "continue"]


class SuiteMetadata(BaseModel):
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), alias="createdAt")
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), alias="updatedAt")
    last_run: Optional[str] = Field(None, alias="lastRun")
    run_count: int = Field(0, alias="runCount")
    pass_count: int = Field(0, alias="passCount")

    model_config = {"populate_by_name": True}


class Suite(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    intent_ids: list[str] = Field(default_factory=list, alias="intentIds")
    tags: list[str] = Field(default_factory=list)
    is_preset: bool = Field(False, alias="isPreset")
    run_mode: RunMode = Field("fail-fast", alias="runMode")
    metadata: SuiteMetadata = Field(default_factory=SuiteMetadata)

    model_config = {"populate_by_name": True}
