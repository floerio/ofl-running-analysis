"""Query manager.

Pre-defined queries are stored as .md files under queries/default_queries/ (originals, never modified by the app)
and queries/user/ (user overrides, created only when the user saves a change).

Public API
----------
load_all()             → dict[str, str]   load all active queries (called at startup)
get(name)              → str              return active query text for a given name
save_user(name, text)                     write a user override file
revert(name)                              delete the user override file
is_modified(name)      → bool             True if a user override exists
original_text(name)    → str              always returns the original (unmodified) query
"""

import os

QUERIES_DIR = "queries"
DEFAULT_QUERIES_DIR = os.path.join(QUERIES_DIR, "default_queries")
USER_DIR = os.path.join(QUERIES_DIR, "user")

# List of query names (must match filenames in default_queries/)
QUERY_NAMES = [
    "query_1",
    "query_2",
    "query_3",
    "query_4",
    "query_5",
]

# Human-readable metadata shown in the config UI
QUERY_META = {
    "query_1": {
        "title": "Query 1",
        "description": "Pre-defined query 1",
    },
    "query_2": {
        "title": "Query 2",
        "description": "Pre-defined query 2",
    },
    "query_3": {
        "title": "Query 3",
        "description": "Pre-defined query 3",
    },
    "query_4": {
        "title": "Query 4",
        "description": "Pre-defined query 4",
    },
    "query_5": {
        "title": "Query 5",
        "description": "Pre-defined query 5",
    },
}


def _original_path(name: str) -> str:
    return os.path.join(DEFAULT_QUERIES_DIR, f"{name}.md")


def _user_path(name: str) -> str:
    return os.path.join(USER_DIR, f"{name}.md")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def original_text(name: str) -> str:
    """Return the original (unmodified) query text."""
    return _read(_original_path(name))


def is_modified(name: str) -> bool:
    """True if the user has saved an override for this query."""
    return os.path.exists(_user_path(name))


def get(name: str) -> str:
    """Return the active query text (user override if it exists, else original)."""
    path = _user_path(name) if is_modified(name) else _original_path(name)
    return _read(path)


def load_all() -> dict[str, str]:
    """Load all active queries. Returns a dict keyed by query name."""
    return {name: get(name) for name in QUERY_NAMES}


def save_user(name: str, text: str) -> None:
    """Write a user override. Creates queries/user/ if needed."""
    os.makedirs(USER_DIR, exist_ok=True)
    with open(_user_path(name), "w", encoding="utf-8") as f:
        f.write(text)


def revert(name: str) -> None:
    """Delete the user override, reverting to the original."""
    path = _user_path(name)
    if os.path.exists(path):
        os.remove(path)
