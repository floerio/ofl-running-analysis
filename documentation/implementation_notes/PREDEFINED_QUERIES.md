# Pre-defined Queries Feature — Implementation Guide

This document describes how to implement a pre-defined queries feature similar to the one in the OFL Running Analysis project. This feature allows users to select from a set of pre-configured query templates, with the ability to edit them at runtime.

## Overview

The pre-defined queries feature provides:
- A set of 5 default queries stored as Markdown files
- User ability to edit queries through a configuration UI
- User overrides saved separately from defaults (not committed to git)
- Query selector in the sidebar that pre-fills the chat input when clicked

## File Structure

```
queries/
├── default_queries/
│   ├── query_1.md
│   ├── query_2.md
│   ├── query_3.md
│   ├── query_4.md
│   └── query_5.md
└── user/
    (empty initially, gitignored - user overrides go here)
```

## Implementation Steps

### Step 1: Create the directory structure and default query files

```bash
mkdir -p queries/default_queries queries/user
for i in 1 2 3 4 5; do echo "to be defined later" > queries/default_queries/query_$i.md; done
```

### Step 2: Add to .gitignore

```
# Query system - user overrides
queries/user/
```

### Step 3: Create the query manager module

Create `src/query_manager.py`:

```python
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
```

### Step 4: Add query loading to app startup

In `app.py`, add the import and loading:

```python
from src import query_manager

# After other session state initialization:
if "queries" not in st.session_state:
    st.session_state.queries = query_manager.load_all()
```

### Step 5: Add query selector to sidebar

In `app.py`, add the query selector expander in the sidebar, above the prompt history:

```python
# ── Pre-defined queries ────────────────────────────────────
queries = st.session_state.queries
with st.expander("Pre-defined queries", expanded=False):
    for name in query_manager.QUERY_NAMES:
        query_text = queries.get(name, query_manager.get(name))
        if st.button(query_text, key=f"query_{name}", use_container_width=True):
            st.session_state.prompt_prefill = query_text
            st.rerun()

st.markdown("---")
```

**Note:** The button text shows the actual query content (like prompt history), not just the title.

### Step 6: Add query editor to config page

In `pages/config.py`, add:

```python
from src import query_manager

# After prompts loading:
if "queries" not in st.session_state:
    st.session_state["queries"] = query_manager.load_all()

def get_queries():
    """Helper to get current queries."""
    return st.session_state.get("queries", query_manager.load_all())
```

Then add the query editor section after the prompt editor:

```python
st.markdown("---")

# ── Query editor ─────────────────────────────────────────────────────────────
st.header("🔍 Pre-defined Queries")
st.caption(
    "Edit the pre-defined queries. Changes take effect immediately and are saved to "
    "`queries/user/`. The original files in `queries/default_queries/` are never modified. "
    "Revert restores the original at any time."
)

queries = get_queries()

for name in query_manager.QUERY_NAMES:
    meta = query_manager.QUERY_META[name]
    modified = query_manager.is_modified(name)

    badge = "📝 **Modified**" if modified else "✅ Original"
    with st.expander(f"**{meta['title']}** — {badge}", expanded=False):
        st.caption(meta["description"])

        current_text = queries.get(name, query_manager.get(name))
        edited_text = st.text_area(
            "Query text",
            value=current_text,
            height=100,
            key=f"query_editor_{name}",
            label_visibility="collapsed",
        )

        col_save, col_revert, _ = st.columns([1, 1, 4])

        with col_save:
            if st.button("Save", key=f"save_query_{name}", use_container_width=True):
                query_manager.save_user(name, edited_text)
                st.session_state["queries"] = query_manager.load_all()
                st.success("Saved.")
                st.rerun()

        with col_revert:
            if modified:
                if st.button(
                    "Revert",
                    key=f"revert_query_{name}",
                    use_container_width=True,
                ):
                    query_manager.revert(name)
                    st.session_state["queries"] = query_manager.load_all()
                    st.success("Reverted to original.")
                    st.rerun()
```

## Key Design Decisions

1. **Separate from prompts**: Queries are stored separately from prompts because they represent complete user questions, not LLM instruction templates.

2. **Same pattern as prompts**: The implementation follows the exact same pattern as the prompt system for consistency:
   - Defaults in `default_queries/` subfolder
   - User overrides in `user/` subfolder
   - Same loading, saving, reverting logic

3. **Button text shows query content**: Like prompt history, the query selector buttons display the actual query text, not just a title. This makes it easy for users to see what they're selecting.

4. **Pre-fill, not auto-execute**: Clicking a query pre-fills the chat input, allowing the user to review and modify before sending. This matches the prompt history behavior.

## Integration Points

1. **Session state**: Queries are loaded into `st.session_state.queries` at app startup
2. **Sidebar**: Query selector appears as an expander above prompt history
3. **Config page**: Full query editor with Save/Revert functionality
4. **Pre-fill mechanism**: Uses existing `prompt_prefill` session state variable

## Customization

To adapt this feature for another app:

1. **Change number of queries**: Modify `QUERY_NAMES` list in `query_manager.py`
2. **Change query names**: Update both `QUERY_NAMES` and `QUERY_META` dictionaries
3. **Change file locations**: Update `QUERIES_DIR`, `DEFAULT_QUERIES_DIR`, and `USER_DIR` constants
4. **Change UI labels**: Update the expander titles and captions in `app.py` and `pages/config.py`

## Dependencies

- Requires Streamlit for the UI components
- Requires the existing session state pattern for `prompt_prefill`
- No additional Python packages required
