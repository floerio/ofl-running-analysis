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
    "suggest_followups",
    "chat_intent",
    "chat_followup",
    "chat_general",
]

# Human-readable metadata shown in the config UI
PROMPT_META = {
    "sql_guidelines": {
        "title": "SQL Guidelines",
        "description": "DuckDB-specific SQL rules and best practices. Injected as {sql_guidelines} into the SQL Generation and SQL Fixing prompts. No placeholders of its own.",
        "placeholders": [],  # shared block — no placeholders
    },
    "generate_sql": {
        "title": "SQL Generation",
        "description": "Prompt sent to the LLM to generate a DuckDB SQL query from the user's question.",
        "placeholders": [
            ("{question}", "The user's question in plain English."),
            ("{schema}", "Live database schema: column names, types, and 5 sample rows."),
            ("{data_dictionary}", "Injected shared block: human-readable column descriptions (see Data Dictionary in Config)."),
            ("{business_glossary}", "Injected shared block: domain terms and metric aliases (see Business Glossary in Config)."),
            ("{sql_guidelines}", "Injected shared block: DuckDB SQL rules (see SQL Guidelines above)."),
            ("{history_section}", "Previous questions and their SQL, for multi-turn context. Empty on first question."),
        ],
    },
    "fix_sql": {
        "title": "SQL Fixing",
        "description": "Prompt sent to the LLM when a generated SQL query fails. The LLM receives the broken SQL and the error message and returns a corrected query.",
        "placeholders": [
            ("{sql}", "The SQL query that failed."),
            ("{error}", "The DuckDB error message."),
            ("{schema}", "Live database schema: column names, types, and 5 sample rows."),
            ("{data_dictionary}", "Injected shared block: human-readable column descriptions (see Data Dictionary in Config)."),
            ("{sql_guidelines}", "Injected shared block: DuckDB SQL rules (see SQL Guidelines above)."),
        ],
    },
    "generate_chart_code": {
        "title": "Chart Code Generation",
        "description": "Prompt sent to the LLM to decide whether a chart is useful and, if so, generate executable matplotlib Python code.",
        "placeholders": [
            ("{question}", "The user's question in plain English."),
            ("{result_str}", "The query result as a plain-text table (truncated to 200 rows)."),
            ("{data_dictionary}", "Injected shared block: human-readable column descriptions (see Data Dictionary in Config)."),
        ],
    },
    "formulate_answer": {
        "title": "Answer Formulation",
        "description": "Prompt sent to the LLM to write a structured answer from the query results. Produces four sections: Facts, Summary, Analysis, Suggestions.",
        "placeholders": [
            ("{question}", "The user's question in plain English."),
            ("{result_str}", "The query result as a plain-text table (truncated to 200 rows)."),
            ("{data_dictionary}", "Injected shared block: human-readable column descriptions (see Data Dictionary in Config)."),
            ("{business_glossary}", "Injected shared block: domain terms and metric aliases (see Business Glossary in Config)."),
            ("{history_section}", "Previous questions and answers, for multi-turn context. Empty on first question."),
        ],
    },
    "suggest_followups": {
        "title": "Follow-up Suggestions",
        "description": "Prompt sent to the LLM to generate 5 clickable follow-up question suggestions after each answer.",
        "placeholders": [
            ("{question}", "The user's question in plain English."),
            ("{result_str}", "The query result as a plain-text table (truncated to 200 rows)."),
        ],
    },
    "chat_intent": {
        "title": "Chat Intent Classifier",
        "description": "Classifies a question as NEW_QUERY, FOLLOWUP, or UNCLEAR. Used by Chat Mode to decide whether to run SQL or answer conversationally.",
        "placeholders": [
            ("{question}", "The current user question."),
            ("{last_question}", "The previous question asked."),
            ("{last_result_preview}", "A short preview of the previous query result."),
            ("{history_section}", "Conversation history for context."),
        ],
    },
    "chat_followup": {
        "title": "Chat Follow-up Answer",
        "description": "Conversational answer for follow-up questions that don't need a new SQL query. Used in Chat Mode.",
        "placeholders": [
            ("{question}", "The current follow-up question."),
            ("{last_question}", "The previous question asked."),
            ("{last_result}", "The full previous query result."),
            ("{history_section}", "Conversation history for context."),
            ("{business_glossary}", "Injected shared block: domain terms and metric aliases."),
        ],
    },
    "chat_general": {
        "title": "Chat General Answer",
        "description": "Conversational answer for UNCLEAR questions that don't map to the database. Used in Chat Mode.",
        "placeholders": [
            ("{question}", "The current question."),
            ("{history_section}", "Conversation history for context."),
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

    # Inject shared blocks first (before other substitutions)
    text = text.replace("{sql_guidelines}", prompts.get("sql_guidelines", ""))
    text = text.replace("{data_dictionary}", prompts.get("data_dictionary", ""))
    text = text.replace("{business_glossary}", prompts.get("business_glossary", ""))

    # Substitute remaining placeholders; ignore unknown keys
    for key, value in kwargs.items():
        text = text.replace(f"{{{key}}}", value if value is not None else "")

    return text
