from __future__ import annotations

from typing import Any, Optional


class QAAutopilotError(Exception):
    pass


class SelectorNotFoundError(QAAutopilotError):
    def __init__(self, message: str, target: dict[str, Any], strategies_attempted: list[str]):
        super().__init__(message)
        self.target = target
        self.strategies_attempted = strategies_attempted


class StepExecutionError(QAAutopilotError):
    def __init__(self, message: str, step_id: str, step_intent: str, cause: Optional[Exception] = None):
        super().__init__(message)
        self.step_id = step_id
        self.step_intent = step_intent
        self.__cause__ = cause


class AIResolverError(QAAutopilotError):
    def __init__(self, message: str, api_response: Optional[str] = None, cause: Optional[Exception] = None):
        super().__init__(message)
        self.api_response = api_response
        self.__cause__ = cause


class IntentValidationError(QAAutopilotError):
    def __init__(self, message: str, validation_errors: list[dict[str, str]]):
        super().__init__(message)
        self.validation_errors = validation_errors


class BrowserLaunchError(QAAutopilotError):
    def __init__(self, message: str, browser: str, cause: Optional[Exception] = None):
        super().__init__(message)
        self.browser = browser
        self.__cause__ = cause


class CacheError(QAAutopilotError):
    def __init__(self, message: str, cache_path: Optional[str] = None, cause: Optional[Exception] = None):
        super().__init__(message)
        self.cache_path = cache_path
        self.__cause__ = cause


class TimeoutError(QAAutopilotError):
    def __init__(self, message: str, timeout_ms: int, operation: str):
        super().__init__(message)
        self.timeout_ms = timeout_ms
        self.operation = operation
