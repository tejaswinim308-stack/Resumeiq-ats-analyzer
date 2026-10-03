from services.scoring_engine import compute_score, WEIGHTS


def test_weights_sum_to_100():
    assert sum(WEIGHTS.values()) == 100


def test_compute_score_returns_all_categories(sample_resume, sample_job):
    result = compute_score(sample_resume, sample_job)
    score = result["score"]
    for category in WEIGHTS:
        assert category in score
    assert 0 <= score["overall"] <= 100


def test_full_skill_match_yields_high_skill_score(sample_job):
    resume = {
        "name": "Full Match",
        "summary": "Experienced engineer.",
        "skills": ["Python", "PostgreSQL", "Docker", "React", "AWS"],
        "projects": [],
        "experience": [{"title": "Eng", "description": "Worked with Python, PostgreSQL, Docker, React, AWS."}],
        "education": [{"degree": "Bachelor"}],
        "certifications": [],
        "achievements": [],
    }
    result = compute_score(resume, sample_job)
    assert result["score"]["skill_match"] == WEIGHTS["skill_match"]


def test_no_matching_skills_yields_zero_skill_score():
    resume = {"name": "No Match", "summary": "x", "skills": ["Excel", "PowerPoint"]}
    job = {"title": "Job", "required_skills": ["Python"], "preferred_skills": ["Go"], "keywords": []}
    result = compute_score(resume, job)
    assert result["score"]["skill_match"] == 0


def test_empty_resume_does_not_crash_and_scores_low():
    resume = {"name": "", "summary": "", "skills": []}
    job = {"title": "Job", "required_skills": ["Python"], "preferred_skills": [], "keywords": ["scalability"]}
    result = compute_score(resume, job)
    assert result["score"]["overall"] < 30


def test_job_with_no_requirements_gives_full_skill_and_keyword_marks():
    resume = {"name": "Someone", "summary": "A summary.", "skills": ["Python"]}
    job = {"title": "Job", "required_skills": [], "preferred_skills": [], "keywords": []}
    result = compute_score(resume, job)
    assert result["score"]["skill_match"] == WEIGHTS["skill_match"]
    assert result["score"]["keyword_match"] == WEIGHTS["keyword_match"]


def test_score_breakdown_explanations_are_present(sample_resume, sample_job):
    result = compute_score(sample_resume, sample_job)
    for category, data in result["score_breakdown"].items():
        assert data["explanation"]
        assert data["max"] == WEIGHTS[category]
        assert 0 <= data["points"] <= data["max"]
