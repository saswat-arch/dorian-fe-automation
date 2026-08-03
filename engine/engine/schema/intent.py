from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class SelectorTarget(BaseModel):
    text: Optional[str] = None
    role: Optional[str] = None
    test_id: Optional[str] = Field(None, alias="testId")
    css: Optional[str] = None
    xpath: Optional[str] = None
    label: Optional[str] = None
    placeholder: Optional[str] = None
    position: Optional[dict[str, float]] = None
    parent_context: Optional[str] = Field(None, alias="parentContext")

    model_config = {"populate_by_name": True}


StepType = Literal[
    "navigate",
    "click",
    "type",
    "select",
    "hover",
    "wait",
    "scroll",
    "assert",
    "screenshot",
    "fetch-otp",
    "generate-email",
]


class StepIntent(BaseModel):
    id: str
    order: int
    intent: str
    type: StepType
    target: Optional[SelectorTarget] = None
    value: Optional[str] = None
    url: Optional[str] = None
    wait_ms: Optional[int] = Field(None, alias="waitMs")

    model_config = {"populate_by_name": True}


AssertionType = Literal[
    "visible", "hidden", "text", "url", "count", "attribute", "visual", "network", "console"
]


class AssertionIntent(BaseModel):
    id: str
    after_step: str = Field(alias="afterStep")
    intent: str = "assertion"
    type: AssertionType
    expected: Optional[str] = None
    tolerance: Optional[float] = None

    model_config = {"populate_by_name": True}


BrowserType = Literal["chromium", "firefox", "webkit"]


class Viewport(BaseModel):
    width: int = 1280
    height: int = 720


class IntentConfig(BaseModel):
    timeout: int = 10000
    retries: int = 0
    browsers: list[BrowserType] = Field(default_factory=lambda: ["chromium"])
    viewport: Viewport = Field(default_factory=Viewport)


class AuthConfig(BaseModel):
    task_id: str = Field(alias="taskId")

    model_config = {"populate_by_name": True}


class IntentMetadata(BaseModel):
    created_at: str = Field(alias="createdAt", default="")
    updated_at: str = Field(alias="updatedAt", default="")
    last_run: Optional[str] = Field(None, alias="lastRun")
    run_count: int = Field(0, alias="runCount")
    pass_count: int = Field(0, alias="passCount")
    pass_rate: float = Field(0, alias="passRate")
    avg_duration: float = Field(0, alias="avgDuration")
    source: Optional[str] = None

    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def set_timestamps(cls, data: dict) -> dict:
        if isinstance(data, dict):
            now = datetime.now(timezone.utc).isoformat()
            if not data.get("createdAt") and not data.get("created_at"):
                data["createdAt"] = now
            if not data.get("updatedAt") and not data.get("updated_at"):
                data["updatedAt"] = now
        return data


CreatedFrom = Literal["recorder", "prompt", "manual", "bulk"]


class TestIntent(BaseModel):
    id: str
    name: str
    description: str = ""
    base_url: str = Field(alias="baseUrl")
    created_from: CreatedFrom = Field("manual", alias="createdFrom")
    tags: list[str] = Field(default_factory=list)
    auth: Optional[AuthConfig] = None
    steps: list[StepIntent] = Field(min_length=1)
    assertions: list[AssertionIntent] = Field(default_factory=list)
    config: IntentConfig = Field(default_factory=IntentConfig)
    metadata: IntentMetadata = Field(default_factory=IntentMetadata)

    model_config = {"populate_by_name": True}
