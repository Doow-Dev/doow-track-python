"""Error types for Doow SDK."""

from typing import Optional


class DoowError(Exception):
    """Base exception for Doow SDK."""

    pass


class APIError(DoowError):
    """API error response."""

    def __init__(
        self,
        status: int,
        message: str,
        error_class: Optional[str] = None,
        details: Optional[dict] = None,
    ):
        self.status = status
        self.message = message
        self.error_class = error_class
        self.details = details or {}
        super().__init__(f"doow: {message} (status={status})")

    def is_not_found(self) -> bool:
        return self.status == 404

    def is_unauthorized(self) -> bool:
        return self.status == 401

    def is_forbidden(self) -> bool:
        return self.status == 403

    def is_rate_limited(self) -> bool:
        return self.status == 429

    def is_server_error(self) -> bool:
        return self.status >= 500

    def is_retryable(self) -> bool:
        return self.status in (429, 500, 502, 503, 504)


class ValidationError(DoowError):
    """Input validation error."""

    pass


class ConfigurationError(DoowError):
    """SDK configuration error."""

    pass
