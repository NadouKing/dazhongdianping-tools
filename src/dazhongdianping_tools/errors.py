"""Stable, credential-safe errors for library and CLI consumers."""


class DianpingError(Exception):
    """A predictable tool failure with a machine-readable code."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message}
