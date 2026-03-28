from __future__ import annotations


class ServiceError(RuntimeError):
    def __init__(self, code: str, message: str, *, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.cause = cause

