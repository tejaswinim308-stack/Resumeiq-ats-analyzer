import io

import pytest
from werkzeug.datastructures import FileStorage

from utils.errors import (
    InvalidFileError,
    EmptyFileError,
    UnsupportedFileTypeError,
    FileTooLargeError,
    MissingJobDescriptionError,
    JobDescriptionTooShortError,
)
from utils.validators import validate_resume_file, validate_job_description, MAX_FILE_SIZE_BYTES
from tests.conftest import make_minimal_pdf_bytes


def _file_storage(data: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(data), filename=filename)


def test_valid_pdf_passes():
    fs = _file_storage(make_minimal_pdf_bytes(), "resume.pdf")
    assert validate_resume_file(fs) is True


def test_missing_file_raises_invalid_file_error():
    with pytest.raises(InvalidFileError):
        validate_resume_file(None)


def test_empty_file_raises_empty_file_error():
    fs = _file_storage(b"", "resume.pdf")
    with pytest.raises(EmptyFileError):
        validate_resume_file(fs)


def test_wrong_extension_raises_unsupported_file_type():
    fs = _file_storage(make_minimal_pdf_bytes(), "resume.docx")
    with pytest.raises(UnsupportedFileTypeError):
        validate_resume_file(fs)


def test_oversized_file_raises_file_too_large():
    data = b"%PDF-" + (b"0" * (MAX_FILE_SIZE_BYTES + 1))
    fs = _file_storage(data, "resume.pdf")
    with pytest.raises(FileTooLargeError):
        validate_resume_file(fs)


def test_non_pdf_content_with_pdf_extension_is_rejected():
    fs = _file_storage(b"this is not a pdf at all", "resume.pdf")
    with pytest.raises(InvalidFileError):
        validate_resume_file(fs)


def test_empty_job_description_raises():
    with pytest.raises(MissingJobDescriptionError):
        validate_job_description("")
    with pytest.raises(MissingJobDescriptionError):
        validate_job_description("   ")
    with pytest.raises(MissingJobDescriptionError):
        validate_job_description(None)


def test_too_short_job_description_raises():
    with pytest.raises(JobDescriptionTooShortError):
        validate_job_description("Too short.")


def test_reasonable_job_description_passes():
    assert validate_job_description("We are looking for a backend engineer with Python and SQL experience.") is True
