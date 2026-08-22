"""Prompt manager.

Prompts are stored as .md files under prompts/ (originals, never modified by the app)
and prompts/user/ (user overrides, created only when the user saves a change).

Public API
----------
load_all()             -> dict[str, str]   load all active prompts (called at startup)
get(name)              -> str              return active prompt text for a given name
save_user(name, text)                     write a user override file
revert(name)                              delete the user override file
is_modified(name)      -> bool             True if a user override exists
original_text(name)    -> str              always returns the original (unmodified) prompt
render(name, prompts, **kwargs) -> str     substitute placeholders and return final prompt
"""

import os
import re

PROMPTS_DIR = "prompts"
USER_DIR = os.path.join(PROMPTS_DIR, "user")

# List all prompt names in order; shared blocks must come first
PROMPT_NAMES = [
    "sql_guidelines",      # shared block — injected into other prompts
    "generate_sql",
    "fix_sql",
    "generate_chart_code",
    "formulate_answer",
]

# Human-readable metadata shown in the config UI
PROMPT_META = {
    "sql_guidelines": {
        "title": "SQL Guidelines",
        "description": "DuckDB-specific SQL rules and best practices that are injected into SQL-related prompts.",
        "placeholders": [],  # shared blocks have no placeholders
    },
    "generate_sql": {
        "title": "SQL Generation",
        "description": "Prompt used to generate DuckDB SQL queries from user questions.",
        "placeholders": [
            ("{question}", "The user's question in plain English."),
            ("{schema}", "Database schema with column names, types, and sample rows."),
            ("{sql_guidelines}", "The SQL guidelines shared block (see above)."),
            ("{history_section}", "Optional context from previous questions and their SQL."),
        ],
    },
    "fix_sql": {
        "title": "SQL Fixing",
        "description": "Prompt used to fix SQL queries that failed with errors.",
        "placeholders": [
            ("{sql}", "The failed SQL query."),
            ("{error}", "The error message from DuckDB."),
            ("{schema}", "Database schema with column names, types, and sample rows."),
            ("{sql_guidelines}", "The SQL guidelines shared block (see above)."),
        ],
    },
    "generate_chart_code": {
        "title": "Chart Code Generation",
        "description": "Prompt used to decide if a chart is useful and generate matplotlib code.",
        "placeholders": [
            ("{question}", "The user's question in plain English."),
            ("{result_str}", "The query result as a string representation of the DataFrame."),
        ],
    },
    "formulate_answer": {
        "title": "Answer Formulation",
        "description": "Prompt used to write a plain-English answer based on query results.",
        "placeholders": [
            ("{question}", "The user's question in plain English."),
            ("{result_str}", "The query result as a string representation of the DataFrame."),
            ("{history_section}", "Optional context from previous questions."),
        ],
    },
}


def _original_path(name: str) -> str:
    return os.path.join(PROMPTS_DIR, f"{name}.md")


def _user_path(name: str) -> str:
    return os.path.join(USER_DIR, f"{name}.md")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _strip_comment(text: str) -> str:
    """Remove all <!-- ... --> HTML comments from a prompt file."""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()


def original_text(name: str) -> str:
    """Return the original (unmodified) prompt text, comment stripped."""
    return _strip_comment(_read(_original_path(name)))


def is_modified(name: str) -> bool:
    """True if the user has saved an override for this prompt."""
    return os.path.exists(_user_path(name))


def get(name: str) -> str:
    """Return the active prompt text (user override if it exists, else original)."""
    path = _user_path(name) if is_modified(name) else _original_path(name)
    return _strip_comment(_read(path))


def load_all() -> dict[str, str]:
    """Load all active prompts. Returns a dict keyed by prompt name."""
    return {name: get(name) for name in PROMPT_NAMES}


def save_user(name: str, text: str) -> None:
    """Write a user override. Creates prompts/user/ if needed."""
    os.makedirs(USER_DIR, exist_ok=True)
    with open(_user_path(name), "w", encoding="utf-8") as f:
        f.write(text)


def revert(name: str) -> None:
    """Delete the user override, reverting to the original."""
    path = _user_path(name)
    if os.path.exists(path):
        os.remove(path)


def render(name: str, prompts: dict[str, str], **kwargs) -> str:
    """Substitute placeholders in a prompt and return the final string.

    Shared blocks are injected first (they cannot themselves contain further
    placeholders). All other kwargs are substituted afterwards.
    Missing keys are left as-is — no error is raised.
    """
    text = prompts[name]

    # Inject shared blocks by name before other substitutions
    text = text.replace("{sql_guidelines}", prompts.get("sql_guidelines", ""))

    # Substitute remaining placeholders; ignore unknown keys
    for key, value in kwargs.items():
        text = text.replace(f"{{{key}}}", value if value is not None else "")

    return text
