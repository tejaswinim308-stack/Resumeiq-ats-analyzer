"""
Centralized application errors.

All errors that should be shown to the client (as clean JSON, never a
Python stack trace) subclass AppError. Unexpected exceptions are caught
by the generic handler registered in app.py and converted into a
generic 500 AppError so internals are never leaked to the frontend.
"""


class AppError(Exception):
    """Base class for all controlled, user-facing application errors."""

    status_code = 500
    error_code = "internal_error"

    def __init__(self, message: str, status_code: int = None, error_code: str = None, details=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code
        self.details = details or {}

    def to_dict(self):
        payload = {
            "success": False,
            "error": {
                "code": self.error_code,
                "message": self.message,
            },
        }
        if self.details:
            payload["error"]["details"] = self.details
        return payload


class ValidationError(AppError):
    """Bad request from the client: malformed input, missing fields, etc."""

    status_code = 400
    error_code = "validation_error"


class InvalidFileError(ValidationError):
    error_code = "invalid_file"


class FileTooLargeError(ValidationError):
    status_code = 413
    error_code = "file_too_large"


class EmptyFileError(ValidationError):
    error_code = "empty_file"


class UnsupportedFileTypeError(ValidationError):
    error_code = "unsupported_file_type"


class MissingJobDescriptionError(ValidationError):
    error_code = "missing_job_description"


class JobDescriptionTooShortError(ValidationError):
    error_code = "job_description_too_short"


class AuthenticationError(AppError):
    status_code = 401
    error_code = "authentication_error"


class NotFoundError(AppError):
    status_code = 404
    error_code = "not_found"


class ConfigurationError(AppError):
    """A required environment variable / credential is missing server-side."""

    status_code = 503
    error_code = "configuration_error"


class GeminiTimeoutError(AppError):
    status_code = 504
    error_code = "gemini_timeout"


class GeminiResponseError(AppError):
    """Gemini returned something we could not safely parse/validate."""

    status_code = 502
    error_code = "gemini_invalid_response"


class FirebaseError(AppError):
    status_code = 503
    error_code = "firebase_error"


class ServiceUnavailableError(AppError):
    status_code = 503
    error_code = "service_unavailable"
