import pytest

from schemas.response_schema import validate_extraction, SchemaValidationError


def test_valid_extraction_passes():
    data = {
        "resume": {"name": "Jane", "summary": "A summary.", "skills": ["Python"]},
        "job": {"title": "Engineer", "required_skills": ["Python"], "keywords": []},
    }
    result = validate_extraction(data)
    assert result["resume"]["name"] == "Jane"
    assert result["resume"]["email"] == ""  # defaulted
    assert result["job"]["preferred_skills"] == []  # coerced from missing -> []


def test_missing_resume_key_raises():
    data = {"job": {"title": "Engineer", "required_skills": [], "keywords": []}}
    with pytest.raises(SchemaValidationError):
        validate_extraction(data)


def test_missing_required_scalar_field_raises():
    data = {
        "resume": {"summary": "A summary.", "skills": []},  # missing "name"
        "job": {"title": "Engineer", "required_skills": [], "keywords": []},
    }
    with pytest.raises(SchemaValidationError):
        validate_extraction(data)


def test_wrong_type_for_list_field_raises():
    data = {
        "resume": {"name": "Jane", "summary": "x", "skills": "Python"},  # should be a list
        "job": {"title": "Engineer", "required_skills": [], "keywords": []},
    }
    with pytest.raises(SchemaValidationError):
        validate_extraction(data)


def test_non_dict_top_level_raises():
    with pytest.raises(SchemaValidationError):
        validate_extraction(["not", "a", "dict"])


def test_none_list_fields_are_coerced_to_empty_list():
    data = {
        "resume": {"name": "Jane", "summary": "x", "skills": ["Python"], "projects": None},
        "job": {"title": "Engineer", "required_skills": [], "keywords": None},
    }
    result = validate_extraction(data)
    assert result["resume"]["projects"] == []
    assert result["job"]["keywords"] == []
