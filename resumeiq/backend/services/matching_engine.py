"""
Skill and keyword matching between a parsed resume and a parsed job
description.

Everything here is deterministic and explainable: no ML, no fuzzy /
semantic substitution. Two strings are only considered "the same skill"
if they normalize to the same canonical form via utils.normalize
(case, punctuation, whitespace, and a small curated alias table).
"""

from utils.normalize import (
    normalize_skill,
    normalize_skill_set,
    normalize_keyword_set,
    tokenize_for_search,
    basic_normalize,
)


def _collect_resume_skill_strings(resume: dict):
    """Pull every skill-like string out of the resume payload: the
    explicit skills list plus programming languages / frameworks /
    tools, which Gemini returns as separate arrays."""
    fields = ["skills", "technical_skills", "programming_languages", "frameworks", "tools"]
    collected = []
    for f in fields:
        collected.extend(resume.get(f, []) or [])
    return collected


def match_skills(resume: dict, job: dict):
    """Compare resume skills against job required/preferred skills.

    Returns a dict with:
      matched:   canonical skills present in both resume and job (required ∪ preferred)
      missing:   required/preferred job skills not found in the resume
      recommended: subset of `missing` the resume has real evidence for
                   elsewhere (projects/experience mention it) even though
                   it wasn't listed as a formal "skill" -- these are safe
                   to recommend adding to the skills section.
      stats:     counts used by the scoring engine, so the score is
                   reproducible from this same data.
    """
    resume_skill_strings = _collect_resume_skill_strings(resume)
    resume_skills = normalize_skill_set(resume_skill_strings)

    required = normalize_skill_set(job.get("required_skills", []))
    preferred = normalize_skill_set(job.get("preferred_skills", []))

    matched_required = resume_skills & required
    matched_preferred = resume_skills & preferred
    missing_required = required - resume_skills
    missing_preferred = preferred - resume_skills

    # Evidence text: projects + experience bullets + summary, normalized.
    evidence_text = tokenize_for_search(_resume_evidence_text(resume))

    recommended = set()
    for skill in missing_required | missing_preferred:
        # Only recommend a missing skill if the resume's own words
        # (projects/experience/summary) already demonstrate it -- i.e.
        # the user forgot to list it in their skills section, we are not
        # inventing experience they don't have.
        if skill and skill in evidence_text:
            recommended.add(skill)

    return {
        "matched": sorted(matched_required | matched_preferred),
        "missing": sorted(missing_required | missing_preferred),
        "missing_required": sorted(missing_required),
        "missing_preferred": sorted(missing_preferred),
        "recommended": sorted(recommended),
        "stats": {
            "total_required": len(required),
            "total_preferred": len(preferred),
            "matched_required": len(matched_required),
            "matched_preferred": len(matched_preferred),
        },
    }


def _resume_evidence_text(resume: dict) -> str:
    parts = [resume.get("summary", "") or ""]
    for proj in resume.get("projects", []) or []:
        if isinstance(proj, dict):
            parts.append(proj.get("description", "") or "")
            parts.append(proj.get("name", "") or "")
            parts.append(" ".join(proj.get("technologies", []) or []))
        else:
            parts.append(str(proj))
    for exp in resume.get("experience", []) or []:
        if isinstance(exp, dict):
            parts.append(exp.get("description", "") or "")
            parts.append(exp.get("title", "") or "")
            parts.append(" ".join(exp.get("highlights", []) or []))
        else:
            parts.append(str(exp))
    return " \n ".join(parts)


def match_keywords(resume: dict, job: dict):
    """Compare job-description keywords/technical terms against the full
    resume body text (not just the skills list) via substring
    containment on normalized text.

    Never recommends a keyword purely because it appears in the job
    description -- `recommended` (see recommend_keywords) only includes
    ones the resume already has real evidence for.
    """
    keywords = normalize_keyword_set(job.get("keywords", []))
    full_resume_text = tokenize_for_search(_full_resume_text(resume))

    matched = set()
    missing = set()
    for kw in keywords:
        if kw and kw in full_resume_text:
            matched.add(kw)
        else:
            missing.add(kw)

    return {
        "matched": sorted(matched),
        "missing": sorted(missing),
        "stats": {
            "total_keywords": len(keywords),
            "matched_keywords": len(matched),
        },
    }


def _full_resume_text(resume: dict) -> str:
    parts = [_resume_evidence_text(resume)]
    parts.append(" ".join(_collect_resume_skill_strings(resume)))
    for cert in resume.get("certifications", []) or []:
        parts.append(cert if isinstance(cert, str) else cert.get("name", ""))
    for ach in resume.get("achievements", []) or []:
        parts.append(ach if isinstance(ach, str) else str(ach))
    for edu in resume.get("education", []) or []:
        if isinstance(edu, dict):
            parts.append(" ".join(str(v) for v in edu.values() if v))
        else:
            parts.append(str(edu))
    return " \n ".join(p for p in parts if p)


def recommend_keywords(resume: dict, missing_keywords):
    """Of the keywords missing from the resume's explicit skill/keyword
    surface, only recommend the ones that genuinely correspond to
    resume evidence (projects, experience, skills) -- i.e. keywords the
    candidate could truthfully add, not ones invented to please an ATS.
    """
    evidence_text = tokenize_for_search(_resume_evidence_text(resume))
    recommended = []
    for kw in missing_keywords:
        norm_kw = basic_normalize(kw)
        if norm_kw and norm_kw in evidence_text:
            recommended.append(kw)
    return sorted(set(recommended))
