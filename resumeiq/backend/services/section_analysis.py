"""
Per-section quality analysis (0-10 each) plus strengths/weaknesses and
grounded recommendations.

Deterministic heuristics only -- no additional Gemini calls. This keeps
the whole scoring/analysis pipeline reproducible and explainable, and
means the app degrades gracefully (still returns section feedback) even
if Gemini's own qualitative commentary were ever unavailable.
"""

import re

from utils.normalize import tokenize_for_search

_ACTION_VERBS = {
    "built", "led", "designed", "developed", "implemented", "created", "improved",
    "optimized", "reduced", "increased", "launched", "architected", "automated",
    "managed", "mentored", "deployed", "migrated", "refactored", "shipped",
    "delivered", "scaled", "spearheaded", "engineered", "streamlined",
}

_QUANTIFIER_RE = re.compile(r"\b\d+(\.\d+)?\s*(%|percent|x|ms|s|sec|seconds|k|m|million|billion|users|requests)?\b")


def _has_quantified_impact(text: str) -> bool:
    return bool(re.search(r"\d", text or ""))


def _score_summary(resume: dict) -> dict:
    summary = (resume.get("summary") or "").strip()
    if not summary:
        return {"section": "summary", "score": 0, "notes": "No professional summary found."}
    words = len(summary.split())
    score = 10
    notes = []
    if words < 15:
        score -= 4
        notes.append("Summary is very short; aim for 2-3 sentences.")
    elif words > 80:
        score -= 2
        notes.append("Summary is long; consider tightening it to 2-4 sentences.")
    if not any(v in tokenize_for_search(summary) for v in _ACTION_VERBS):
        score -= 2
        notes.append("Consider leading with a strong action verb or role-defining statement.")
    score = max(0, min(10, score))
    return {"section": "summary", "score": score, "notes": " ".join(notes) or "Clear, well-scoped summary."}


def _score_skills(resume: dict) -> dict:
    all_skills = []
    for f in ["skills", "technical_skills", "programming_languages", "frameworks", "tools"]:
        all_skills.extend(resume.get(f, []) or [])
    count = len(set(s.strip().lower() for s in all_skills if s and s.strip()))
    if count == 0:
        return {"section": "skills", "score": 0, "notes": "No skills listed."}
    if count < 5:
        return {"section": "skills", "score": 5, "notes": "Skills section is thin; list more relevant technologies."}
    if count > 30:
        return {
            "section": "skills",
            "score": 7,
            "notes": "Very large skills list; consider trimming to the most relevant/proficient ones.",
        }
    return {"section": "skills", "score": 10, "notes": "Good breadth of listed skills."}


def _score_entries_with_impact(entries, label):
    if not entries:
        return {"section": label, "score": 0, "notes": f"No {label} entries found."}
    quantified = 0
    action_led = 0
    for e in entries:
        text = e.get("description", "") if isinstance(e, dict) else str(e)
        highlights = e.get("highlights", []) if isinstance(e, dict) else []
        full_text = text + " " + " ".join(highlights)
        if _has_quantified_impact(full_text):
            quantified += 1
        if any(v in tokenize_for_search(full_text)[:200] for v in _ACTION_VERBS):
            action_led += 1
    total = len(entries)
    score = 4  # base credit for having entries at all
    score += round(4 * (quantified / total))
    score += round(2 * (action_led / total))
    score = max(0, min(10, score))
    notes = []
    if quantified < total:
        notes.append("Add measurable outcomes (%, time saved, users, scale) where possible.")
    if action_led < total:
        notes.append("Start bullet points with strong action verbs.")
    return {"section": label, "score": score, "notes": " ".join(notes) or "Well-written, quantified entries."}


def _score_education(resume: dict) -> dict:
    education = resume.get("education", []) or []
    if not education:
        return {"section": "education", "score": 0, "notes": "No education listed."}
    complete = 0
    for e in education:
        if isinstance(e, dict) and (e.get("degree") or e.get("institution")):
            complete += 1
        elif isinstance(e, str) and e.strip():
            complete += 1
    score = 10 if complete == len(education) else 6
    return {"section": "education", "score": score, "notes": "Education section present." if complete else "Education entries are missing key details (degree/institution)."}


def _score_certifications(resume: dict) -> dict:
    certs = resume.get("certifications", []) or []
    if not certs:
        return {"section": "certifications", "score": 0, "notes": "No certifications listed (optional, but can help)."}
    return {"section": "certifications", "score": min(10, 5 + len(certs) * 2), "notes": f"{len(certs)} certification(s) listed."}


def _score_achievements(resume: dict) -> dict:
    ach = resume.get("achievements", []) or []
    if not ach:
        return {"section": "achievements", "score": 0, "notes": "No standout achievements listed (optional, but can strengthen the resume)."}
    quantified = sum(1 for a in ach if _has_quantified_impact(a if isinstance(a, str) else str(a)))
    score = 6 + round(4 * (quantified / len(ach)))
    return {"section": "achievements", "score": min(10, score), "notes": f"{len(ach)} achievement(s) listed."}


def analyze_sections(resume: dict) -> list:
    """Returns a list of {section, score (0-10), notes} for each of the
    required sections: summary, skills, projects, experience, education,
    certifications, achievements.
    """
    return [
        _score_summary(resume),
        _score_skills(resume),
        _score_entries_with_impact(resume.get("projects", []) or [], "projects"),
        _score_entries_with_impact(resume.get("experience", []) or [], "experience"),
        _score_education(resume),
        _score_certifications(resume),
        _score_achievements(resume),
    ]


def derive_strengths_and_weaknesses(sections: list, score_breakdown: dict):
    strengths = []
    improvements = []
    for s in sections:
        if s["score"] >= 8:
            strengths.append(f"Strong {s['section']} section.")
        elif s["score"] <= 4:
            improvements.append(s["notes"] or f"{s['section'].capitalize()} section needs improvement.")

    for category, data in score_breakdown.items():
        label = category.replace("_", " ")
        ratio = data["points"] / data["max"] if data["max"] else 0
        if ratio >= 0.85:
            strengths.append(f"High {label} ({data['points']}/{data['max']}).")
        elif ratio <= 0.4:
            improvements.append(f"Low {label} ({data['points']}/{data['max']}): {data['explanation']}")

    # Deduplicate while preserving order.
    def dedup(seq):
        seen = set()
        out = []
        for item in seq:
            if item not in seen:
                seen.add(item)
                out.append(item)
        return out

    return dedup(strengths)[:8], dedup(improvements)[:8]


def build_recommendations(resume: dict, job: dict, sections: list, score_result: dict) -> list:
    """Generate 5-8 grounded, actionable recommendations. Every
    recommendation is derived from concrete facts already computed
    (missing skills/keywords with resume evidence, weak sections, low
    score categories) -- never generic filler.
    """
    recs = []

    for skill in score_result["skills"]["recommended"][:3]:
        recs.append(
            {
                "title": f"Add '{skill}' to your skills section",
                "reason": "Your projects/experience already demonstrate this, but it isn't listed as a skill, so ATS keyword scanners may miss it.",
                "priority": "High",
                "suggested_action": f"Add '{skill}' explicitly to your Skills section.",
            }
        )

    missing_required = score_result.get("_missing_required", [])
    for skill in missing_required[:2]:
        recs.append(
            {
                "title": f"Gain or highlight experience with '{skill}'",
                "reason": "This is a required skill for the role that doesn't currently appear anywhere on your resume.",
                "priority": "High",
                "suggested_action": f"If you have any exposure to '{skill}', add a bullet point demonstrating it; otherwise consider a small project to build it.",
            }
        )

    for kw in score_result["keywords"]["recommended"][:2]:
        recs.append(
            {
                "title": f"Mention '{kw}' explicitly",
                "reason": "This keyword from the job description matches work you've already described, but isn't stated in those exact terms.",
                "priority": "Medium",
                "suggested_action": f"Rephrase a relevant bullet point to include the term '{kw}'.",
            }
        )

    for s in sections:
        if s["score"] <= 5 and s["notes"]:
            recs.append(
                {
                    "title": f"Strengthen your {s['section']} section",
                    "reason": s["notes"],
                    "priority": "Medium" if s["score"] >= 3 else "High",
                    "suggested_action": s["notes"],
                }
            )

    breakdown = score_result["score_breakdown"]
    if breakdown["structure"]["points"] < breakdown["structure"]["max"]:
        recs.append(
            {
                "title": "Fill in missing resume sections",
                "reason": breakdown["structure"]["explanation"],
                "priority": "Medium",
                "suggested_action": "Add the missing section(s) noted above so ATS parsers and recruiters can find complete information.",
            }
        )

    if breakdown["certifications"]["points"] == 0:
        recs.append(
            {
                "title": "Consider adding relevant certifications",
                "reason": "No certifications are currently listed, which can be a differentiator for this role.",
                "priority": "Low",
                "suggested_action": "Look for a widely-recognized certification related to the role's core technologies.",
            }
        )

    # Deduplicate by title, keep 5-8.
    seen_titles = set()
    deduped = []
    for r in recs:
        if r["title"] not in seen_titles:
            seen_titles.add(r["title"])
            deduped.append(r)

    if len(deduped) < 5:
        deduped.append(
            {
                "title": "Tailor your resume to this specific role",
                "reason": "A resume customized to the exact language of each job description consistently scores better with ATS systems.",
                "priority": "Low",
                "suggested_action": "Mirror the job description's terminology for skills you genuinely have, throughout your resume.",
            }
        )

    return deduped[:8]
