import uuid
import logging
from flask import Blueprint, jsonify, request

# Update this line to match where extract_resume_and_job actually resides
# e.g., services.gemini_service OR services.analyze
from services.gemini_service import extract_resume_and_job
from services.pdf_service import extract_text_from_pdf
from services.scoring_engine import compute_score
from services.section_analysis import analyze_sections, derive_strengths_and_weaknesses, build_recommendations
from services import firebase_service
from utils.validators import validate_resume_file, validate_job_description, sanitize_text_input

logger = logging.getLogger("resumeiq")

analyze_bp = Blueprint("analyze", __name__)


@analyze_bp.route("/api/analyze", methods=["POST"])
def analyze():
    """
    multipart/form-data:
      resume: PDF file (required, <=10MB)
      job_description: string (required, >=50 chars)

    Pipeline: validate -> extract PDF text -> Gemini structured extraction
    -> deterministic scoring engine -> section analysis -> response.
    """
    resume_file = request.files.get("resume")
    job_description = request.form.get("job_description", "")

    validate_resume_file(resume_file)
    validate_job_description(job_description)

    job_description = sanitize_text_input(job_description)

    file_bytes = resume_file.read()
    resume_text = extract_text_from_pdf(file_bytes)
    resume_text = sanitize_text_input(resume_text, max_length=40000)

    # Structured extraction with safe fallback
    try:
        extraction = extract_resume_and_job(resume_text, job_description)
    except Exception as exc:
        logger.warning("Extraction error in analyze route: %s. Using fallback extractor.", exc)
        from services.fallback_service import fallback_extract_resume_and_job
        extraction = fallback_extract_resume_and_job(resume_text, job_description)

    resume = extraction.get("resume", {})
    job = extraction.get("job", {})

    score_result = compute_score(resume, job)
    sections = analyze_sections(resume)
    strengths, improvements = derive_strengths_and_weaknesses(sections, score_result.get("score_breakdown", {}))
    recommendations = build_recommendations(resume, job, sections, score_result)

    analysis_id = str(uuid.uuid4())

    response_payload = {
        "success": True,
        "analysis_id": analysis_id,
        "resume": {
            "name": resume.get("name", ""),
            "email": resume.get("email", ""),
            "summary": resume.get("summary", ""),
            "skills": resume.get("skills", []),
            "projects": resume.get("projects", []),
            "experience": resume.get("experience", []),
            "education": resume.get("education", []),
            "certifications": resume.get("certifications", []),
            "achievements": resume.get("achievements", []),
        },
        "job": {
            "title": job.get("title", ""),
            "required_skills": job.get("required_skills", []),
            "preferred_skills": job.get("preferred_skills", []),
            "keywords": job.get("keywords", []),
        },
        "score": score_result.get("score", 0),
        "score_breakdown": score_result.get("score_breakdown", {}),
        "skills": score_result.get("skills", {}),
        "keywords": score_result.get("keywords", {}),
        "sections": sections,
        "strengths": strengths,
        "improvements": improvements,
        "recommendations": recommendations,
    }

    # Best-effort history save
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and hasattr(firebase_service, "is_available") and firebase_service.is_available():
        try:
            token = auth_header[len("Bearer "):].strip()
            uid = firebase_service.verify_id_token(token)
            firebase_service.save_analysis(uid, response_payload)
        except Exception as err:  # noqa: BLE001
            logger.warning("Firebase history save skipped: %s", str(err))

    return jsonify(response_payload), 200