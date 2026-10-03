"""Server-side input validation. All validation here is enforced on the
backend regardless of anything the frontend already checked -- the
frontend checks exist only for fast user feedback, not as the source
of truth."""

from utils.errors import (
    InvalidFileError,
    FileTooLargeError,
    EmptyFileError,
    UnsupportedFileTypeError,
    MissingJobDescriptionError,
    JobDescriptionTooShortError,
)

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {"pdf"}
PDF_MAGIC_BYTES = b"%PDF-"
MIN_JOB_DESCRIPTION_LENGTH = 50  # characters


def validate_resume_file(file_storage):
    """Validate an uploaded Werkzeug FileStorage as a real, in-size PDF.

    Raises a specific AppError subclass on any failure; never raises a
    bare exception that would surface as a stack trace.
    """
    if file_storage is None or file_storage.filename == "":
        raise InvalidFileError("No resume file was uploaded.")

    filename = file_storage.filename
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '.{extension or '?'}'. Only PDF resumes are accepted."
        )

    # Determine size without loading the whole file into memory twice.
    file_storage.stream.seek(0, 2)  # seek to end
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)

    if size == 0:
        raise EmptyFileError("The uploaded resume file is empty.")

    if size > MAX_FILE_SIZE_BYTES:
        raise FileTooLargeError(
            f"Resume file is too large ({size / (1024*1024):.1f} MB). Maximum allowed size is 10 MB."
        )

    header = file_storage.stream.read(5)
    file_storage.stream.seek(0)
    if header != PDF_MAGIC_BYTES:
        raise InvalidFileError("The uploaded file does not appear to be a valid PDF.")

    return True


def validate_job_description(job_description: str):
    if job_description is None or not job_description.strip():
        raise MissingJobDescriptionError("Job description is required.")
    if len(job_description.strip()) < MIN_JOB_DESCRIPTION_LENGTH:
        raise JobDescriptionTooShortError(
            f"Job description is too short. Please provide at least {MIN_JOB_DESCRIPTION_LENGTH} characters."
        )
    return True


def sanitize_text_input(text: str, max_length: int = 20000) -> str:
    """Basic sanitation for freeform text sent to Gemini / stored in
    Firestore: strip null bytes and cap length to something reasonable."""
    if not text:
        return ""
    cleaned = text.replace("\x00", "")
    return cleaned[:max_length]
