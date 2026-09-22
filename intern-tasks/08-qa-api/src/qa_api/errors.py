"""Safe application errors exposed by the HTTP boundary."""

from uuid import UUID


class ApplicationError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        trace_id: UUID,
        retryable: bool,
        status_code: int,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.trace_id = trace_id
        self.retryable = retryable
        self.status_code = status_code
