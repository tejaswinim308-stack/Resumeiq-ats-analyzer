"""
Text and skill normalization utilities.

These are deliberately conservative: normalization only folds together
strings that are unambiguously the same skill under a different spelling
or punctuation (case, punctuation, whitespace, a small curated alias
table). It never performs "semantic" substitutions that could change
meaning (e.g. "React" is never treated as equal to "Vue" just because
both are frontend frameworks).
"""

import re
import unicodedata

# Curated alias table: canonical_form -> set of known equivalent spellings.
# Keys and values are already in "normalized" form (lowercase, no punctuation)
# so lookups happen after basic normalization.
_SKILL_ALIASES = {
    "javascript": {"js", "javascript", "ecmascript", "es6", "es2015"},
    "typescript": {"ts", "typescript"},
    "python": {"python", "python3", "py"},
    "postgresql": {"postgresql", "postgres", "psql"},
    "mysql": {"mysql"},
    "mongodb": {"mongodb", "mongo"},
    "nodejs": {"nodejs", "node", "nodejs", "node js"},
    "reactjs": {"react", "reactjs", "react js"},
    "vuejs": {"vue", "vuejs", "vue js"},
    "angular": {"angular", "angularjs", "angular js"},
    "nextjs": {"next", "nextjs", "next js"},
    "csharp": {"c#", "csharp", "c sharp"},
    "cplusplus": {"c++", "cplusplus", "cpp"},
    "golang": {"go", "golang"},
    "kubernetes": {"kubernetes", "k8s"},
    "docker": {"docker", "dockerized", "dockerize"},
    "amazonwebservices": {"aws", "amazon web services"},
    "googlecloudplatform": {"gcp", "google cloud platform", "google cloud"},
    "microsoftazure": {"azure", "microsoft azure"},
    "restapi": {"rest", "restful", "rest api", "restful api"},
    "graphql": {"graphql", "graph ql"},
    "html": {"html", "html5"},
    "css": {"css", "css3"},
    "tailwindcss": {"tailwind", "tailwindcss", "tailwind css"},
    "expressjs": {"express", "expressjs", "express js"},
    "django": {"django"},
    "flask": {"flask"},
    "firebase": {"firebase"},
    "git": {"git"},
    "github": {"github"},
    "sql": {"sql"},
    "nosql": {"nosql", "no sql"},
    "machinelearning": {"ml", "machine learning"},
    "artificialintelligence": {"ai", "artificial intelligence"},
    "tensorflow": {"tensorflow", "tf"},
    "pytorch": {"pytorch", "torch"},
    "ci_cd": {"ci/cd", "cicd", "ci cd", "continuous integration"},
}

# Reverse index for O(1) alias -> canonical lookups.
_ALIAS_TO_CANONICAL = {}
for _canonical, _aliases in _SKILL_ALIASES.items():
    for _alias in _aliases:
        _ALIAS_TO_CANONICAL[_alias] = _canonical


def basic_normalize(text: str) -> str:
    """Lowercase, strip accents/punctuation noise, collapse whitespace.

    Keeps internal word characters and single spaces only. Used as the
    first pass before alias lookups and for general keyword comparison.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    # Preserve a few meaningful symbols (c++, c#, ci/cd) before stripping.
    text = text.replace("c++", "cplusplus").replace("c#", "csharp")
    text = text.replace("node.js", "nodejs").replace("next.js", "nextjs")
    text = text.replace("react.js", "reactjs").replace("vue.js", "vuejs")
    text = text.replace("express.js", "expressjs")
    text = re.sub(r"[^\w\s/]", " ", text)  # drop punctuation except '/'
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_skill(skill: str) -> str:
    """Return the canonical form of a skill string for comparison.

    Example: "JS" -> "javascript", "Postgres" -> "postgresql",
    "React.js" -> "reactjs". Unknown skills are returned in their
    basic-normalized (lowercase, no punctuation) form, unchanged
    otherwise -- we never guess at equivalence for skills we don't
    recognize.
    """
    normalized = basic_normalize(skill)
    if not normalized:
        return ""
    # Try direct alias match first.
    if normalized in _ALIAS_TO_CANONICAL:
        return _ALIAS_TO_CANONICAL[normalized]
    # Try with spaces collapsed (e.g. "node js" -> "nodejs").
    collapsed = normalized.replace(" ", "")
    if collapsed in _ALIAS_TO_CANONICAL:
        return _ALIAS_TO_CANONICAL[collapsed]
    if collapsed in _SKILL_ALIASES:
        return collapsed
    return normalized


def normalize_skill_set(skills):
    """Normalize a list of skill strings into a deduplicated set of
    canonical forms, dropping empty entries."""
    out = set()
    for s in skills or []:
        n = normalize_skill(s)
        if n:
            out.add(n)
    return out


def normalize_keyword_set(keywords):
    """Normalize a list of free-text keywords/phrases for matching against
    resume body text. Less aggressive than skill normalization -- keeps
    multi-word phrases intact after basic_normalize."""
    out = set()
    for k in keywords or []:
        n = basic_normalize(k)
        if n:
            out.add(n)
    return out


def tokenize_for_search(text: str) -> str:
    """Normalize a larger block of free text (resume body, project
    descriptions) into a single lowercase, punctuation-light string
    suitable for substring/keyword containment checks."""
    return basic_normalize(text or "")
