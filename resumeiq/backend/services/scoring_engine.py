"""
Deterministic ATS scoring engine.

Gemini is used ONLY to extract structured facts from the resume and job
description (services/gemini_service.py). It never determines the final
score. Every point value produced here is computed by explicit,
reproducible arithmetic over that structured data, so the same
(resume, job) pair always yields the same score and every number can be
explained to the user.

Category weights (sum to 100):
  skill_match     30
  keyword_match   20
  project_match   20
  education_match 10
  structure       10
  certifications  10
"""

from services.matching_engine import match_skills, match_keywords, recommend_keywords, _resume_evidence_text
from utils.normalize import normalize_skill_set, tokenize_for_search, basic_normalize

WEIGHTS = {
    "skill_match": 30,
    "keyword_match": 20,
    "project_match": 20,
    "education_match": 10,
    "structure": 10,
    "certifications": 10,
}

# Split of the 30 skill_match points between required vs. preferred skills.
_REQUIRED_SKILL_SHARE = 0.8
_PREFERRED_SKILL_SHARE = 0.2

# Section weights that sum to the 10 "structure" points.
_STRUCTURE_SECTIONS = {
    "summary": 2,
    "skills": 2,
    "experience_or_projects": 3,
    "education": 2,
    "formatting": 1,  # presence of contact info (name/email) as a proxy for a parseable, well-formed doc
}

# How many relevant certifications earns the full 10 points.
_CERT_TARGET_COUNT = 2


def _round(x):
    return round(x, 1)


def score_skill_match(resume: dict, job: dict, skills_result: dict) -> dict:
    """30 points, split 24/6 between required and preferred skills.

    score = 30 * [0.8 * (matched_required / total_required)
                 + 0.2 * (matched_preferred / total_preferred)]

    If the job lists no required skills, required's share is
    redistributed to preferred (and vice-versa) so the category is
    never unfairly capped by a job description that simply didn't
    specify one bucket.
    """
    stats = skills_result["stats"]
    total_req = stats["total_required"]
    total_pref = stats["total_preferred"]
    matched_req = stats["matched_required"]
    matched_pref = stats["matched_preferred"]

    req_share = _REQUIRED_SKILL_SHARE
    pref_share = _PREFERRED_SKILL_SHARE
    if total_req == 0 and total_pref > 0:
        req_share, pref_share = 0.0, 1.0
    elif total_pref == 0 and total_req > 0:
        req_share, pref_share = 1.0, 0.0

    req_ratio = (matched_req / total_req) if total_req else 0.0
    pref_ratio = (matched_pref / total_pref) if total_pref else 0.0

    if total_req == 0 and total_pref == 0:
        # No skills at all were extracted from the job description --
        # nothing to grade against; award full marks rather than
        # penalizing the candidate for an under-specified JD.
        points = WEIGHTS["skill_match"]
        explanation = "Job description listed no specific required/preferred skills; full marks awarded by default."
    else:
        points = WEIGHTS["skill_match"] * (req_share * req_ratio + pref_share * pref_ratio)
        explanation = (
            f"{matched_req}/{total_req} required skills matched (weight {req_share*100:.0f}%), "
            f"{matched_pref}/{total_pref} preferred skills matched (weight {pref_share*100:.0f}%)."
        )

    return {"points": _round(points), "max": WEIGHTS["skill_match"], "explanation": explanation}


def score_keyword_match(keywords_result: dict) -> dict:
    """20 points = 20 * (matched_keywords / total_keywords).

    If the JD yields no extractable keywords, full marks are awarded
    (nothing to grade against) rather than zero.
    """
    stats = keywords_result["stats"]
    total = stats["total_keywords"]
    matched = stats["matched_keywords"]
    if total == 0:
        return {
            "points": WEIGHTS["keyword_match"],
            "max": WEIGHTS["keyword_match"],
            "explanation": "No distinct technical keywords were extracted from the job description; full marks awarded by default.",
        }
    points = WEIGHTS["keyword_match"] * (matched / total)
    return {
        "points": _round(points),
        "max": WEIGHTS["keyword_match"],
        "explanation": f"{matched}/{total} job-description keywords found in the resume text.",
    }


def score_project_match(resume: dict, job: dict) -> dict:
    """20 points based on how many of the resume's projects/experience
    entries demonstrably relate to the job's required+preferred skills
    or keywords.

    relevant_ratio = (# projects/experience entries with >=1 overlapping
                       skill or keyword) / (total projects/experience entries)
    points = 20 * relevant_ratio, scaled down if there are very few
    entries overall (a single relevant project should not automatically
    max this category).
    """
    job_terms = normalize_skill_set(job.get("required_skills", []) or []) | normalize_skill_set(
        job.get("preferred_skills", []) or []
    )
    job_terms |= {basic_normalize(k) for k in (job.get("keywords", []) or [])}
    job_terms.discard("")

    entries = list(resume.get("projects", []) or []) + list(resume.get("experience", []) or [])
    if not entries:
        return {
            "points": 0.0,
            "max": WEIGHTS["project_match"],
            "explanation": "No projects or work experience were found on the resume.",
        }

    relevant_count = 0
    for entry in entries:
        if isinstance(entry, dict):
            text = " ".join(
                [
                    str(entry.get("name", "") or entry.get("title", "")),
                    str(entry.get("description", "")),
                    " ".join(entry.get("technologies", []) or entry.get("highlights", []) or []),
                ]
            )
        else:
            text = str(entry)
        normalized_text = tokenize_for_search(text)
        if any(term and term in normalized_text for term in job_terms):
            relevant_count += 1

    ratio = relevant_count / len(entries)
    # Density factor: reward having *enough* relevant entries, not just a
    # nonzero fraction. Two or more relevant entries reach full credit;
    # a single relevant entry earns partial credit.
    density_factor = min(1.0, relevant_count / 2)
    points = WEIGHTS["project_match"] * ratio * density_factor + WEIGHTS["project_match"] * (1 - density_factor) * (
        0.5 * ratio
    )
    points = min(points, WEIGHTS["project_match"])

    return {
        "points": _round(points),
        "max": WEIGHTS["project_match"],
        "explanation": f"{relevant_count}/{len(entries)} project/experience entries relate to the job's required skills or keywords.",
    }


_DEGREE_LEVELS = {
    "phd": 4,
    "ph d": 4,
    "doctorate": 4,
    "master": 3,
    "masters": 3,
    "msc": 3,
    "m sc": 3,
    "ms": 3,
    "m s": 3,
    "mba": 3,
    "bachelor": 2,
    "bachelors": 2,
    "bsc": 2,
    "b sc": 2,
    "bs": 2,
    "b s": 2,
    "btech": 2,
    "b tech": 2,
    "associate": 1,
    "diploma": 1,
}


def _highest_degree_level(education_entries) -> int:
    best = 0
    for edu in education_entries or []:
        text = tokenize_for_search(edu if isinstance(edu, str) else " ".join(str(v) for v in edu.values() if v))
        words = set(text.split())
        for term, level in _DEGREE_LEVELS.items():
            if " " in term:
                if term in text:
                    best = max(best, level)
            else:
                if term in words or (len(term) >= 4 and term in text):
                    best = max(best, level)
    return best


def score_education_match(resume: dict, job: dict) -> dict:
    """10 points.

    If the job description specifies a minimum degree level (detected
    via keyword scan of required_skills/keywords/title for terms like
    "bachelor"/"master"/"phd"), the resume earns full marks if its
    highest listed degree meets or exceeds that level, half marks if it
    has a degree but below the requirement, and zero if no education is
    listed at all.

    If the job specifies no degree requirement, the resume earns full
    marks for simply having at least one well-formed education entry
    (presence credit), since we cannot grade against an unstated bar.
    """
    education = resume.get("education", []) or []
    resume_level = _highest_degree_level(education)

    job_text = tokenize_for_search(
        " ".join(job.get("required_skills", []) or [])
        + " "
        + " ".join(job.get("keywords", []) or [])
        + " "
        + (job.get("title", "") or "")
    )
    job_words = set(job_text.split())
    job_level = 0
    for term, level in _DEGREE_LEVELS.items():
        if " " in term:
            if term in job_text:
                job_level = max(job_level, level)
        else:
            if term in job_words or (len(term) >= 4 and term in job_text):
                job_level = max(job_level, level)

    if not education:
        return {
            "points": 0.0,
            "max": WEIGHTS["education_match"],
            "explanation": "No education entries were found on the resume.",
        }

    if job_level == 0:
        return {
            "points": WEIGHTS["education_match"],
            "max": WEIGHTS["education_match"],
            "explanation": "Job description specifies no explicit degree requirement; full marks awarded for having education listed.",
        }

    if resume_level >= job_level:
        return {
            "points": WEIGHTS["education_match"],
            "max": WEIGHTS["education_match"],
            "explanation": "Resume's highest listed degree meets or exceeds the job's implied requirement.",
        }

    return {
        "points": _round(WEIGHTS["education_match"] * 0.5),
        "max": WEIGHTS["education_match"],
        "explanation": "Resume lists education, but below the degree level implied by the job description.",
    }


def score_structure(resume: dict) -> dict:
    """10 points split across section presence/non-emptiness:
      summary 2, skills 2, experience-or-projects 3, education 2, contact info 1.
    """
    points = 0.0
    present = []
    missing = []

    if (resume.get("summary") or "").strip():
        points += _STRUCTURE_SECTIONS["summary"]
        present.append("summary")
    else:
        missing.append("summary")

    if _collect_any(resume, ["skills", "technical_skills", "programming_languages", "frameworks", "tools"]):
        points += _STRUCTURE_SECTIONS["skills"]
        present.append("skills")
    else:
        missing.append("skills")

    if (resume.get("experience") or []) or (resume.get("projects") or []):
        points += _STRUCTURE_SECTIONS["experience_or_projects"]
        present.append("experience/projects")
    else:
        missing.append("experience/projects")

    if resume.get("education") or []:
        points += _STRUCTURE_SECTIONS["education"]
        present.append("education")
    else:
        missing.append("education")

    if (resume.get("name") or "").strip() and (resume.get("email") or "").strip():
        points += _STRUCTURE_SECTIONS["formatting"]
        present.append("contact info")
    else:
        missing.append("contact info")

    return {
        "points": _round(points),
        "max": WEIGHTS["structure"],
        "explanation": f"Present: {', '.join(present) or 'none'}. Missing: {', '.join(missing) or 'none'}.",
    }


def _collect_any(resume, fields):
    for f in fields:
        if resume.get(f):
            return True
    return False


def score_certifications(resume: dict, job: dict) -> dict:
    """10 points.

    If the job explicitly lists required certifications (rare, detected
    via overlap of job required_skills/keywords with common
    certification vocabulary is unreliable, so instead): compare
    resume certifications against job required/preferred skills by
    normalized substring match. Matched, job-relevant certifications
    count double. Otherwise, presence-based credit: each certification
    up to a target count of 2 is worth 5 points.
    """
    certs = resume.get("certifications", []) or []
    if not certs:
        return {"points": 0.0, "max": WEIGHTS["certifications"], "explanation": "No certifications listed."}

    job_terms = normalize_skill_set(job.get("required_skills", []) or []) | normalize_skill_set(
        job.get("preferred_skills", []) or []
    )
    relevant = 0
    for c in certs:
        name = c if isinstance(c, str) else c.get("name", "")
        norm = tokenize_for_search(name)
        if any(term and term in norm for term in job_terms):
            relevant += 1

    if relevant > 0:
        points = min(WEIGHTS["certifications"], WEIGHTS["certifications"] * (relevant / min(len(job_terms) or 1, 2)))
        explanation = f"{relevant} certification(s) directly relevant to the job's required/preferred skills."
    else:
        points = min(WEIGHTS["certifications"], (WEIGHTS["certifications"] / _CERT_TARGET_COUNT) * len(certs))
        explanation = f"{len(certs)} certification(s) listed (none explicitly matched to job requirements); credited for presence."

    return {"points": _round(points), "max": WEIGHTS["certifications"], "explanation": explanation}


def compute_score(resume: dict, job: dict) -> dict:
    """Compute the full deterministic ATS score for a (resume, job) pair.

    Returns a dict with the overall 0-100 score plus a per-category
    breakdown, each carrying its own point value, max value, and a
    plain-English explanation of how it was calculated -- so nothing
    about the score is a black box.
    """
    skills_result = match_skills(resume, job)
    keywords_result = match_keywords(resume, job)

    skill_score = score_skill_match(resume, job, skills_result)
    keyword_score = score_keyword_match(keywords_result)
    project_score = score_project_match(resume, job)
    education_score = score_education_match(resume, job)
    structure_score = score_structure(resume)
    cert_score = score_certifications(resume, job)

    breakdown = {
        "skill_match": skill_score,
        "keyword_match": keyword_score,
        "project_match": project_score,
        "education_match": education_score,
        "structure": structure_score,
        "certifications": cert_score,
    }

    overall = sum(b["points"] for b in breakdown.values())
    overall = max(0.0, min(100.0, overall))

    recommended_skills = skills_result["recommended"]
    recommended_keywords = recommend_keywords(resume, keywords_result["missing"])

    return {
        "score": {
            "overall": round(overall),
            "skill_match": round(skill_score["points"]),
            "keyword_match": round(keyword_score["points"]),
            "project_match": round(project_score["points"]),
            "education_match": round(education_score["points"]),
            "structure": round(structure_score["points"]),
            "certifications": round(cert_score["points"]),
        },
        "score_breakdown": breakdown,  # detailed, with explanations -- exposed to the frontend for transparency
        "skills": {
            "matched": skills_result["matched"],
            "missing": skills_result["missing"],
            "recommended": sorted(set(recommended_skills)),
        },
        "keywords": {
            "matched": keywords_result["matched"],
            "missing": keywords_result["missing"],
            "recommended": recommended_keywords,
        },
        "_missing_required": skills_result["missing_required"],  # internal use (recommendations engine)
    }
