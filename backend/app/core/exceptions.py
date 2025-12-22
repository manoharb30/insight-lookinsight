"""Custom exceptions for the application."""

from typing import Optional, Any


class InsightException(Exception):
    """Base exception for Insight application."""

    def __init__(
        self,
        message: str,
        details: Optional[Any] = None,
        status_code: int = 500,
    ):
        self.message = message
        self.details = details
        self.status_code = status_code
        super().__init__(self.message)


class SECEdgarError(InsightException):
    """Error fetching data from SEC EDGAR."""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message, details, status_code=502)


class TickerNotFoundError(InsightException):
    """Ticker symbol not found in SEC database."""

    def __init__(self, ticker: str):
        super().__init__(
            f"Ticker '{ticker}' not found in SEC database",
            details={"ticker": ticker},
            status_code=404,
        )


class RateLimitError(InsightException):
    """Rate limit exceeded for external API."""

    def __init__(self, service: str, retry_after: Optional[int] = None):
        super().__init__(
            f"Rate limit exceeded for {service}",
            details={"service": service, "retry_after": retry_after},
            status_code=429,
        )


class ExtractionError(InsightException):
    """Error during signal extraction."""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message, details, status_code=500)


class DatabaseError(InsightException):
    """Database connection or query error."""

    def __init__(self, service: str, message: str, details: Optional[Any] = None):
        super().__init__(
            f"{service} error: {message}",
            details=details,
            status_code=503,
        )


class ValidationError(InsightException):
    """Signal validation error."""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message, details, status_code=400)
