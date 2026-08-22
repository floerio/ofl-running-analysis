"""Data dictionary manager.

The data dictionary describes the attributes of the data file to help the LLM
understand the schema. It is stored as a YAML frontmatter file and can be edited
at runtime through the config page.

Public API
----------
load()                     → dict              Load the data dictionary YAML
save_user(text)               → None            Save user override
revert()                    → None            Delete user override, revert to default
is_modified()              → bool            True if user has saved an override
format_schema(dictionary) → str              Format dictionary as plain text for LLM
get_schema_description()   → str              Get formatted schema description (convenience)
"""

import os
import yaml

DATA_DICT_DIR = "data_dictionary"
DEFAULT_FILE = os.path.join(DATA_DICT_DIR, "default.md")
USER_FILE = os.path.join(DATA_DICT_DIR, "user", "default.md")


def _read_yaml(path: str) -> dict:
    """Read YAML frontmatter from a markdown file."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Extract YAML frontmatter (between --- delimiters)
    if content.startswith("---"):
        # Find the end of frontmatter
        end_idx = content.find("---", 3)  # Skip the opening ---
        if end_idx != -1:
            yaml_content = content[3:end_idx].strip()
            return yaml.safe_load(yaml_content) or {}
    
    # If no frontmatter, try parsing the whole file as YAML
    return yaml.safe_load(content) or {}


def _write_yaml(path: str, data: dict) -> None:
    """Write YAML frontmatter to a markdown file."""
    yaml_content = yaml.dump(data, sort_keys=False, default_flow_style=False, allow_unicode=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write(yaml_content)
        f.write("---\n")


def load() -> dict:
    """Load the data dictionary. Returns dict with 'attributes' key."""
    if is_modified():
        return _read_yaml(USER_FILE)
    return _read_yaml(DEFAULT_FILE)


def save_user(text: str) -> None:
    """Save user override. Creates data_dictionary/user/ if needed."""
    os.makedirs(os.path.dirname(USER_FILE), exist_ok=True)
    # Parse the YAML from the text and write it back (to ensure proper formatting)
    try:
        data = yaml.safe_load(text)
        if data is None:
            data = {}
    except yaml.YAMLError:
        # If text is not valid YAML, save as-is
        with open(USER_FILE, "w", encoding="utf-8") as f:
            f.write(text)
        return
    _write_yaml(USER_FILE, data)


def revert() -> None:
    """Delete the user override, reverting to default."""
    if os.path.exists(USER_FILE):
        os.remove(USER_FILE)


def is_modified() -> bool:
    """True if the user has saved an override."""
    return os.path.exists(USER_FILE)


def format_schema(dictionary: dict) -> str:
    """Format the data dictionary as plain text for LLM consumption.
    
    Args:
        dictionary: Dict with 'attributes' key containing list of attribute dicts
    
    Returns:
        Plain text string describing the schema
    """
    if not dictionary or "attributes" not in dictionary:
        return "No schema information available."
    
    lines = ["Schema:"]
    for attr in dictionary["attributes"]:
        name = attr.get("name", "")
        data_type = attr.get("type", "")
        description = attr.get("description", "")
        optional_names = attr.get("optional_names", "")
        
        # Build the main line
        main_line = f"{name} ({data_type}): {description}"
        
        # Add optional names if present
        if optional_names and optional_names != "null" and optional_names != "":
            # Handle both string and list
            if isinstance(optional_names, str):
                names_list = [n.strip() for n in optional_names.split(",") if n.strip()]
            else:
                names_list = optional_names
            
            if names_list:
                main_line += f" Optional names: {', '.join(names_list)}"
        
        lines.append(main_line)
    
    return "\n".join(lines)


def get_schema_description() -> str:
    """Convenience function to get the formatted schema description."""
    dictionary = load()
    return format_schema(dictionary)
