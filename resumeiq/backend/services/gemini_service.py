"""
Gemini integration.

Gemini's ONLY job is structured extraction: turning raw resume text +
a raw job description into the `resume` / `job` JSON objects defined in
schemas/response_schema.py. It never computes a score or makes the
final ATS decision -- that happens deterministically in
services/scoring_engine.py.

The Gemini API key lives only in this backend process (read from the
environment) and is never sent to, or reachable from, frontend
JavaScript.
"""

import json
import logging
import re

import requests

from config import Config
from schemas.response_schema import GEMINI_EXTRACTION_SCHEMA, validate_extraction, SchemaValidationError
from services.fallback_service import fallback_extract_resume_and_job
from utils.errors import ConfigurationError, GeminiTimeoutError, GeminiResponseError

logger = logging.getLogger("resumeiq.gemini")

_GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

_SYSTEM_PROMPT = """You are a precise resume and job-description parser.

Extract ONLY facts that are explicitly present in the provided resume text
and job description text. Do not invent, infer, or embellish any skill,
project, employer, date, or qualification that is not clearly stated.

If a field has no supporting evidence in the source text, return an empty
string or empty array for it -- never fabricate a plausible-looking value.

Return your answer strictly as JSON matching the provided response schema.
Do not include any commentary, markdown formatting, or text outside the
JSON object.
"""


def _build_user_prompt(resume_text: str, job_description: str) -> str:
    return (
        "RESUME TEXT:\n"
        "-----\n"
        f"{resume_text}\n"
        "-----\n\n"
        "JOB DESCRIPTION TEXT:\n"
        "-----\n"
        f"{job_description}\n"
        "-----\n\n"
        "Extract the resume's structured fields (name, email, phone, summary, "
        "education, skills, technical_skills, programming_languages, frameworks, "
        "tools, projects, experience, certifications, achievements) and the job "
        "description's structured fields (title, required_skills, preferred_skills, "
        "keywords, soft_skills). Follow the response schema exactly."
    )


def _extract_json_block(text: str) -> str:
    """Best-effort safe extraction if the model wraps JSON in markdown
    fences or adds stray text despite instructions not to."""
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        return brace_match.group(0)
    return text


def extract_resume_and_job(resume_text: str, job_description: str, allow_fallback: bool = True) -> dict:
    """Call Gemini once with both the resume text and job description,
    and return a validated {"resume": {...}, "job": {...}} dict.

    If Gemini is unavailable, times out, is rate-limited, returns an error,
    or fails schema validation, it falls back seamlessly to rule-based
    heuristic extraction so the analysis pipeline never crashes.
    """
    if not Config.gemini_configured():
        logger.info("Gemini API key is not configured; using deterministic fallback extraction.")
        if allow_fallback:
            return fallback_extract_resume_and_job(resume_text, job_description)
        raise ConfigurationError(
            "The resume analysis service is not fully configured (missing Gemini API key). Please try again later."
        )

    try:
        url = _GEMINI_ENDPOINT.format(model=Config.GEMINI_MODEL)
        payload = {
            "system_instruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": _build_user_prompt(resume_text, job_description)}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": GEMINI_EXTRACTION_SCHEMA,
                "temperature": 0.1,
            },
        }
        headers = {"Content-Type": "application/json", "x-goog-api-key": Config.GEMINI_API_KEY}

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=Config.GEMINI_TIMEOUT_SECONDS)
        except requests.exceptions.Timeout as exc:
            if allow_fallback:
                logger.warning("Gemini timed out. Falling back to heuristic extraction.")
                return fallback_extract_resume_and_job(resume_text, job_description)
            raise GeminiTimeoutError("The resume analysis service timed out. Please try again.") from exc
        except requests.exceptions.RequestException as exc:
            if allow_fallback:
                logger.warning("Gemini connection error: %s. Falling back to heuristic extraction.", exc)
                return fallback_extract_resume_and_job(resume_text, job_description)
            raise GeminiResponseError("Could not reach the resume analysis service. Please try again shortly.") from exc

        if response.status_code != 200:
            logger.error("Gemini API error (status %d): %s", response.status_code, response.text)
            if allow_fallback:
                logger.warning("Gemini returned status %d. Switching to fallback extraction.", response.status_code)
                return fallback_extract_resume_and_job(resume_text, job_description)

        if response.status_code == 401 or response.status_code == 403:
            raise ConfigurationError("The resume analysis service is misconfigured. Please contact support.")
        if response.status_code == 429:
            raise GeminiResponseError("The resume analysis service is currently busy. Please try again in a moment.")
        if response.status_code >= 500:
            raise GeminiResponseError("The resume analysis service is temporarily unavailable. Please try again shortly.")
        if response.status_code != 200:
            raise GeminiResponseError(f"The resume analysis service returned an unexpected error (status {response.status_code}).")

        try:
            body = response.json()
        except ValueError as exc:
            raise GeminiResponseError("The resume analysis service returned a malformed response.") from exc

        try:
            candidates = body["candidates"]
            parts = candidates[0]["content"]["parts"]
            raw_text = "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError, TypeError) as exc:
            raise GeminiResponseError("The resume analysis service returned an unexpected response shape.") from exc

        if not raw_text or not raw_text.strip():
            raise GeminiResponseError("The resume analysis service returned an empty response.")

        parsed = None
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            candidate_text = _extract_json_block(raw_text)
            try:
                parsed = json.loads(candidate_text)
            except json.JSONDecodeError as exc:
                raise GeminiResponseError(
                    "The resume analysis service returned a response that could not be parsed as JSON."
                ) from exc

        try:
            validated = validate_extraction(parsed)
        except SchemaValidationError as exc:
            raise GeminiResponseError(f"The resume analysis service returned incomplete data: {exc}") from exc

        return validated

    except Exception as exc:
        if allow_fallback:
            logger.warning("Gemini extraction failed (%s: %s). Using fallback extraction.", type(exc).__name__, str(exc))
            return fallback_extract_resume_and_job(resume_text, job_description)
        raise
