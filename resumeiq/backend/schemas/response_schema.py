"""
JSON schema used two ways:

1. Sent to Gemini as `generationConfig.responseSchema` so the model is
   constrained to emit machine-readable structured output (Gemini's
   controlled generation), instead of freeform prose we'd have to parse.
2. Used locally (validate_extraction) to defensively re-validate
   whatever Gemini actually returned before it touches the scoring
   engine, since a model's structured-output guarantee is a strong
   hint, not a contract we should blindly trust.
"""

_STRING = {"type": "STRING"}
_STRING_ARRAY = {"type": "ARRAY", "items": _STRING}

_PROJECT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "name": _STRING,
        "description": _STRING,
        "technologies": _STRING_ARRAY,
    },
    "required": ["name", "description"],
}

_EXPERIENCE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "title": _STRING,
        "company": _STRING,
        "duration": _STRING,
        "description": _STRING,
        "highlights": _STRING_ARRAY,
    },
    "required": ["title", "description"],
}

_EDUCATION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "degree": _STRING,
        "institution": _STRING,
        "year": _STRING,
    },
    "required": ["degree"],
}

GEMINI_EXTRACTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "resume": {
            "type": "OBJECT",
            "properties": {
                "name": _STRING,
                "email": _STRING,
                "phone": _STRING,
                "summary": _STRING,
                "education": {"type": "ARRAY", "items": _EDUCATION_SCHEMA},
                "skills": _STRING_ARRAY,
                "technical_skills": _STRING_ARRAY,
                "programming_languages": _STRING_ARRAY,
                "frameworks": _STRING_ARRAY,
                "tools": _STRING_ARRAY,
                "projects": {"type": "ARRAY", "items": _PROJECT_SCHEMA},
                "experience": {"type": "ARRAY", "items": _EXPERIENCE_SCHEMA},
                "certifications": _STRING_ARRAY,
                "achievements": _STRING_ARRAY,
            },
            "required": ["name", "summary", "skills"],
        },
        "job": {
            "type": "OBJECT",
            "properties": {
                "title": _STRING,
                "required_skills": _STRING_ARRAY,
                "preferred_skills": _STRING_ARRAY,
                "keywords": _STRING_ARRAY,
                "soft_skills": _STRING_ARRAY,
            },
            "required": ["title", "required_skills", "keywords"],
        },
    },
    "required": ["resume", "job"],
}

# Top-level keys that MUST be present after our own re-validation, beyond
# what we trust Gemini's schema adherence to have guaranteed.
_REQUIRED_RESUME_FIELDS = ["name", "summary"]
_REQUIRED_JOB_FIELDS = ["title"]

_LIST_FIELDS_RESUME = [
    "skills",
    "technical_skills",
    "programming_languages",
    "frameworks",
    "tools",
    "projects",
    "experience",
    "education",
    "certifications",
    "achievements",
]
_LIST_FIELDS_JOB = ["required_skills", "preferred_skills", "keywords", "soft_skills"]


class SchemaValidationError(Exception):
    pass


def validate_extraction(data: dict) -> dict:
    """Validate + normalize a parsed Gemini JSON payload.

    - Ensures top-level `resume` and `job` objects exist.
    - Ensures required scalar fields exist (fills "" if missing, since a
      missing *optional-in-practice* field like phone shouldn't fail the
      whole analysis -- but a missing name/summary/title is suspicious
      enough to raise).
    - Ensures every expected list field is actually a list (coerces
      None -> [], rejects wrong types).

    Raises SchemaValidationError if the payload is unusable, which the
    caller (gemini_service) turns into a controlled GeminiResponseError.
    """
    if not isinstance(data, dict):
        raise SchemaValidationError("Top-level response was not a JSON object.")

    resume = data.get("resume")
    job = data.get("job")
    if not isinstance(resume, dict) or not isinstance(job, dict):
        raise SchemaValidationError("Response is missing 'resume' or 'job' objects.")

    for field in _REQUIRED_RESUME_FIELDS:
        if field not in resume or resume[field] is None:
            raise SchemaValidationError(f"Resume extraction is missing required field '{field}'.")
    for field in _REQUIRED_JOB_FIELDS:
        if field not in job or job[field] is None:
            raise SchemaValidationError(f"Job extraction is missing required field '{field}'.")

    for field in _LIST_FIELDS_RESUME:
        value = resume.get(field)
        if value is None:
            resume[field] = []
        elif not isinstance(value, list):
            raise SchemaValidationError(f"Resume field '{field}' must be a list.")

    for field in _LIST_FIELDS_JOB:
        value = job.get(field)
        if value is None:
            job[field] = []
        elif not isinstance(value, list):
            raise SchemaValidationError(f"Job field '{field}' must be a list.")

    # Graceful fallbacks for whitespace-only strings
    if not str(resume.get("name", "")).strip():
        resume["name"] = "Candidate"
    resume["summary"] = str(resume.get("summary", "") or "").strip()
    resume.setdefault("email", "")
    resume.setdefault("phone", "")
    if not str(job.get("title", "")).strip():
        job["title"] = "Target Role"

    return {"resume": resume, "job": job}
