from utils.normalize import normalize_skill, normalize_skill_set, basic_normalize, tokenize_for_search


def test_js_and_javascript_are_equivalent():
    assert normalize_skill("JS") == normalize_skill("JavaScript")


def test_postgres_and_postgresql_are_equivalent():
    assert normalize_skill("Postgres") == normalize_skill("PostgreSQL")


def test_case_and_punctuation_are_ignored():
    assert normalize_skill("  Node.JS  ") == normalize_skill("nodejs")


def test_unknown_skill_is_not_merged_with_anything():
    assert normalize_skill("Figma") == "figma"
    assert normalize_skill("Figma") != normalize_skill("Sketch")


def test_no_unsafe_semantic_substitution():
    # React and Vue must never normalize to the same canonical skill just
    # because they're both frontend frameworks.
    assert normalize_skill("React") != normalize_skill("Vue")


def test_normalize_skill_set_deduplicates():
    result = normalize_skill_set(["JS", "javascript", "Js", "Python"])
    assert result == {"javascript", "python"}


def test_basic_normalize_strips_punctuation_and_case():
    assert basic_normalize("C++ Developer!") == "cplusplus developer"


def test_tokenize_for_search_is_substring_friendly():
    text = tokenize_for_search("Built a REST API using Docker & Kubernetes.")
    assert "docker" in text
    assert "kubernetes" in text
