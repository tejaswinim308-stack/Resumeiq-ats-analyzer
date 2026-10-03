"""PDF text extraction. Uses pypdf (pure Python, no native dependencies,
Cloud Run friendly). We never persist the uploaded PDF bytes to disk or
to Firestore -- only the extracted text (transiently, for the Gemini
call) and the final structured analysis are kept, per the security
requirements."""

import io

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from utils.errors import InvalidFileError


def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except PdfReadError as exc:
        raise InvalidFileError("The uploaded PDF could not be read. It may be corrupted or password-protected.") from exc
    except Exception as exc:  # noqa: BLE001 - convert any parser failure into a controlled error
        raise InvalidFileError("The uploaded PDF could not be read. It may be corrupted or password-protected.") from exc

    if getattr(reader, "is_encrypted", False):
        try:
            reader.decrypt("")
        except Exception:  # noqa: BLE001
            raise InvalidFileError("The uploaded PDF is password-protected. Please upload an unprotected PDF.")

    pages_text = []
    for page in reader.pages:
        try:
            pages_text.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001 - a single unparsable page shouldn't fail the whole request
            continue

    text = "\n".join(pages_text).strip()
    if not text:
        raise InvalidFileError(
            "No readable text could be extracted from this PDF. It may be a scanned image without a text layer."
        )
    return text
