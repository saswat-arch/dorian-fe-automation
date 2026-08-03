from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


StepStatus = Literal["passed", "failed", "healed", "skipped"]
Tier = Literal["cached", "smart-selector", "ai-resolver"]


class BrowserEvent(BaseModel):
    type: str
    message: str
    url: str
    step_id: Optional[str] = Field(None, alias="stepId")
    timestamp: str
    meta: dict = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class StepResult(BaseModel):
    step_id: str = Field(alias="stepId")
    intent: str
    status: StepStatus
    tier: Tier
    strategy: str
    confidence: float
    duration_ms: float = Field(alias="durationMs")
    error: Optional[str] = None
    screenshot: Optional[str] = None
    healed_from: Optional[str] = Field(None, alias="healedFrom")
    healed_to: Optional[str] = Field(None, alias="healedTo")
    browser_events: list[BrowserEvent] = Field(default_factory=list, alias="browserEvents")

    model_config = {"populate_by_name": True}


class Viewport(BaseModel):
    width: int
    height: int


class Environment(BaseModel):
    base_url: str = Field(alias="baseUrl")
    viewport: Viewport
    user_agent: Optional[str] = Field(None, alias="userAgent")

    model_config = {"populate_by_name": True}


class RunResult(BaseModel):
    test_id: str = Field(alias="testId")
    test_name: str = Field(alias="testName")
    passed: bool
    steps: list[StepResult]
    total_duration: float = Field(alias="totalDuration")
    browser: str
    timestamp: str
    healed_count: int = Field(alias="healedCount")
    environment: Environment
    browser_events: list[BrowserEvent] = Field(default_factory=list, alias="browserEvents")

    model_config = {"populate_by_name": True}
