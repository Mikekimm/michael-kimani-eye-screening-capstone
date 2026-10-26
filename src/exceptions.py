"""Domain-specific exceptions so callers can handle each failure precisely."""


class ScreeningError(Exception):
    """Base class for every error raised by the screening pipeline."""


class InvalidImageError(ScreeningError):
    """The uploaded data could not be decoded as an image."""


class ImageQualityError(ScreeningError):
    """The image decoded but is unusable (for example blank or too small)."""

    def __init__(self, message, report=None):
        super().__init__(message)
        self.report = report


class ModelNotAvailableError(ScreeningError):
    """No usable trained model could be loaded."""


class RecordValidationError(ScreeningError):
    """A screening or review record failed validation and was not stored."""


class RecordNotFoundError(ScreeningError):
    """The requested screening record does not exist."""


class RemoteError(ScreeningError):
    """Base class for failures talking to the cloud backend."""


class RemoteUnavailableError(RemoteError):
    """No connectivity or the server failed (5xx). Safe to retry later."""


class RemoteAuthError(RemoteError):
    """The server rejected the credentials (401) or role (403)."""


class RemoteRejectedError(RemoteError):
    """The server refused this record (4xx). Retrying unchanged will not help."""
