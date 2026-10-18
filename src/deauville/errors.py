class FestivalError(Exception):
    """Base exception for all festival domain errors."""
    status_code: int = 400


class NotFoundError(FestivalError):
    status_code: int = 404


class ConflictError(FestivalError):
    status_code: int = 409


class InvalidValueError(FestivalError):
    status_code: int = 422