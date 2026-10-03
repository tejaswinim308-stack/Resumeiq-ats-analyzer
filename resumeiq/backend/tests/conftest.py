import io
import os
import sys

import pytest

# Make the backend package importable when pytest is run from backend/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("FLASK_ENV", "development")

from app import create_app  # noqa: E402


@pytest.fixture()
def app():
    application = create_app()
    application.config.update(TESTING=True)
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


def make_minimal_pdf_bytes() -> bytes:
    """A minimal, syntactically valid PDF with no text layer -- used for
    tests that only need to pass the magic-byte / parse checks."""
    from reportlab.pdfgen import canvas
    import io as _io

    buf = _io.BytesIO()
    c = canvas.Canvas(buf)
    c.showPage()
    c.save()
    return buf.getvalue()


def make_pdf_with_text_bytes() -> bytes:
    """A real, valid single-page PDF with an actual extractable text
    layer, generated with reportlab so pypdf can parse it reliably."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    import io as _io

    buf = _io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(72, 720, "Jane Doe - Software Engineer")
    c.drawString(72, 700, "Experienced backend engineer skilled in Python, PostgreSQL, and Docker.")
    c.save()
    return buf.getvalue()


@pytest.fixture()
def minimal_pdf_file():
    return (io.BytesIO(make_minimal_pdf_bytes()), "resume.pdf")


@pytest.fixture()
def sample_resume():
    return {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "555-123-4567",
        "summary": "Backend engineer who built and deployed scalable APIs, reducing latency by 40%.",
        "education": [{"degree": "Bachelor of Science in Computer Science", "institution": "State University", "year": "2020"}],
        "skills": ["Python", "JS", "Postgres", "Docker"],
        "technical_skills": [],
        "programming_languages": ["Python", "JavaScript"],
        "frameworks": ["Flask", "React"],
        "tools": ["Docker", "Git"],
        "projects": [
            {
                "name": "Inventory API",
                "description": "Built a REST API with Flask and PostgreSQL, deployed on Docker to handle 10k requests/day.",
                "technologies": ["Flask", "PostgreSQL", "Docker"],
            }
        ],
        "experience": [
            {
                "title": "Software Engineer",
                "company": "Acme Corp",
                "duration": "2020-2023",
                "description": "Led development of internal tools.",
                "highlights": ["Reduced deployment time by 30% using CI/CD automation."],
            }
        ],
        "certifications": ["AWS Certified Developer"],
        "achievements": ["Won internal hackathon, improving checkout speed by 25%."],
    }


@pytest.fixture()
def sample_job():
    return {
        "title": "Backend Engineer",
        "required_skills": ["Python", "PostgreSQL", "Docker"],
        "preferred_skills": ["React", "AWS"],
        "keywords": ["REST API", "CI/CD", "scalability"],
        "soft_skills": ["communication"],
    }
