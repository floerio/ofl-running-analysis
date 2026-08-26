"""Business glossary manager.

The business glossary defines running-specific terms, Garmin metric names, and
common user phrasings to help the LLM correctly interpret ambiguous questions.
It is stored as a plain Markdown file and can be edited at runtime through the
Configuration page.

Originals live in business_glossary/ and are never modified by the app.
User overrides are written to business_glossary/user/ (gitignored).

Public API
----------
load()              → str    Load the active glossary text (user override or default)
save_user(text)              Save a user override to business_glossary/user/default.md
revert()                     Delete the user override, revert to default
is_modified()       → bool   True if a user override exists
original_text()     → str    Always returns the original (unmodified) text
"""

import os
import re

GLOSSARY_DIR = "business_glossary"
DEFAULT_FILE = os.path.join(GLOSSARY_DIR, "default.md")
USER_FILE = os.path.join(GLOSSARY_DIR, "user", "default.md")


def _strip_comment(text: str) -> str:
    """Remove all <!-- ... --> HTML comments from a Markdown file."""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def is_modified() -> bool:
    """True if the user has saved an override."""
    return os.path.exists(USER_FILE)


def original_text() -> str:
    """Return the original (unmodified) glossary text."""
    return _strip_comment(_read(DEFAULT_FILE))


def load() -> str:
    """Return the active glossary text (user override if present, else default)."""
    path = USER_FILE if is_modified() else DEFAULT_FILE
    return _strip_comment(_read(path))


def save_user(text: str) -> None:
    """Write a user override. Creates business_glossary/user/ if needed."""
    os.makedirs(os.path.dirname(USER_FILE), exist_ok=True)
    with open(USER_FILE, "w", encoding="utf-8") as f:
        f.write(text)


def revert() -> None:
    """Delete the user override, reverting to the original."""
    if os.path.exists(USER_FILE):
        os.remove(USER_FILE)
