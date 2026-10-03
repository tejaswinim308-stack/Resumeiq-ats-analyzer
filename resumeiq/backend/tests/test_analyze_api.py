import io
import pytest
from unittest.mock import patch

from tests.conftest import make_pdf_with_text_bytes
from utils.errors import GeminiTimeoutError, GeminiResponseError, ConfigurationError


@pytest.fixture()
def valid_pdf_file():
    return (io.BytesIO(make_pdf_with_text_bytes()), "resume.pdf")


@pytest.fixture()
def mock_gemini_extraction():
    return {
        "resume": {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "555-0100",
            "summary": "Experienced backend engineer who built scalable microservices in Python and Docker.",
            "education": [{"degree": "Bachelor of Science in Computer Science", "institution": "State University", "year": "2020"}],
            "skills": ["Python", "Docker", "PostgreSQL", "Git"],
            "technical_skills": ["Flask", "REST APIs"],
            "programming_languages": ["Python", "SQL"],
            "frameworks": ["Flask"],
            "tools": ["Docker", "Git"],
            "projects": [
                {
                    "name": "API Service",
                    "description": "Engineered a high-throughput REST API using Python and Docker.",
                    "technologies": ["Python", "Docker", "PostgreSQL"],
                }
            ],
            "experience": [
                {
                    "title": "Software Engineer",
                    "company": "Tech Corp",
                    "duration": "2021-Present",
                    "description": "Developed backend APIs and managed Docker deployments.",
                    "highlights": ["Reduced latency by 35%."],
                }
            ],
            "certifications": ["AWS Certified Cloud Practitioner"],
            "achievements": ["Delivered mission critical migration on schedule."],
        },
        "job": {
            "title": "Backend Engineer",
            "required_skills": ["Python", "Docker"],
            "preferred_skills": ["PostgreSQL", "Kubernetes"],
            "keywords": ["REST API", "microservices"],
            "soft_skills": ["teamwork"],
        },
    }


def test_analyze_success_end_to_end(client, valid_pdf_file, mock_gemini_extraction):
    stream, filename = valid_pdf_file
    jd = "We are seeking a Backend Engineer with strong Python and Docker skills to build scalable REST API microservices."

    with patch("routes.analyze.extract_resume_and_job", return_value=mock_gemini_extraction):
        resp = client.post(
            "/api/analyze",
            data={"resume": (stream, filename), "job_description": jd},
            content_type="multipart/form-data",
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "analysis_id" in data
    assert data["resume"]["name"] == "Jane Doe"
    assert data["job"]["title"] == "Backend Engineer"

    # Deterministic scoring validation
    score = data["score"]
    assert 0 <= score["overall"] <= 100
    assert "skill_match" in score
    assert "keyword_match" in score
    assert "project_match" in score
    assert "education_match" in score
    assert "structure" in score
    assert "certifications" in score

    # Skill matching
    assert "Python" in [s.capitalize() for s in data["skills"]["matched"]]
    assert "Docker" in [s.capitalize() for s in data["skills"]["matched"]]

    # Sections & recommendations
    assert len(data["sections"]) >= 5
    assert len(data["recommendations"]) >= 1


def test_analyze_gemini_timeout_uses_fallback_gracefully(client, valid_pdf_file):
    stream, filename = valid_pdf_file
    jd = "Seeking a talented software engineer with strong Python, PostgreSQL and Docker experience."

    with patch("services.gemini_service.requests.post", side_effect=GeminiTimeoutError("The resume analysis service timed out.")):
        resp = client.post(
            "/api/analyze",
            data={"resume": (stream, filename), "job_description": jd},
            content_type="multipart/form-data",
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "score" in data
    assert "skills" in data
    assert "recommendations" in data


def test_analyze_gemini_invalid_response_uses_fallback_gracefully(client, valid_pdf_file):
    stream, filename = valid_pdf_file
    jd = "Seeking a talented software engineer with strong Python, PostgreSQL and Docker experience."

    with patch("services.gemini_service.requests.post", side_effect=GeminiResponseError("Malformed JSON response.")):
        resp = client.post(
            "/api/analyze",
            data={"resume": (stream, filename), "job_description": jd},
            content_type="multipart/form-data",
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "score" in data
    assert 0 <= data["score"]["overall"] <= 100


def test_analyze_gemini_unconfigured_uses_fallback_gracefully(client, valid_pdf_file):
    stream, filename = valid_pdf_file
    jd = "Seeking a talented software engineer with strong Python, PostgreSQL and Docker experience."

    with patch("config.Config.gemini_configured", return_value=False):
        resp = client.post(
            "/api/analyze",
            data={"resume": (stream, filename), "job_description": jd},
            content_type="multipart/form-data",
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "score" in data
    assert "score_breakdown" in data


def test_analyze_saves_to_firestore_when_authenticated(client, valid_pdf_file, mock_gemini_extraction):
    stream, filename = valid_pdf_file
    jd = "We are looking for a Python developer with Docker skills."

    with patch("routes.analyze.extract_resume_and_job", return_value=mock_gemini_extraction), \
         patch("services.firebase_service.is_available", return_value=True), \
         patch("services.firebase_service.verify_id_token", return_value="user-123"), \
         patch("services.firebase_service.save_analysis") as mock_save:

        resp = client.post(
            "/api/analyze",
            data={"resume": (stream, filename), "job_description": jd},
            headers={"Authorization": "Bearer test-firebase-token"},
            content_type="multipart/form-data",
        )

        assert resp.status_code == 200
        mock_save.assert_called_once()
        args, _ = mock_save.call_args
        assert args[0] == "user-123"


def test_serve_frontend_index_and_static(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"ResumeIQ" in resp.data

    css_resp = client.get("/css/styles.css")
    assert css_resp.status_code == 200
    assert b"--surface" in css_resp.data
