"""Shared API error type and FastAPI exception handlers.

Errors always use the shape: {"error": {"code": ..., "message": ...}}
so the frontend can render clear, actionable messages.
"""
from typing import Optional


class AppError(Exception):
    """Domain error carrying an HTTP status and a stable machine code."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class ProviderNotConfiguredError(AppError):
    def __init__(self) -> None:
        super().__init__(
            409,
            "no_provider",
            "No AI provider is configured yet. Open Settings and add your "
            "API key, or continue with the offline lessons and exercises.",
        )


class ProviderRequestError(AppError):
    def __init__(self, code: str, message: str, status: int = 502) -> None:
        super().__init__(status, code, message)


class RateLimitedError(AppError):
    def __init__(self, retry_after: int = 60) -> None:
        super().__init__(
            429,
            "rate_limited",
            f"Too many requests. Please wait {retry_after} seconds and try again.",
        )
        self.retry_after = retry_after
