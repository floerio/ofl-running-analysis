# Prompt Configuration System — Implementation Guide

> **✅ STATUS: Implemented** - This system has been fully implemented in the OFL Running Analysis project.
> See `src/prompt_manager.py`, `pages/config.py`, and the `prompts/` directory.

This document describes how to implement the runtime-editable prompt system used in the KN Query Assistant. Follow these steps in order. Each step is self-contained and verifiable.

---

## Overview

The goal is to move all hardcoded LLM prompt strings out of Python code and into Markdown files, then expose a UI editor so prompts can be changed at runtime without modifying code or restarting the app.

### End result

```
prompts/
├── <prompt_a>.md         ← original prompt files (never modified by the app)
├── <prompt_b>.md
└── user/                 ← user overrides (created only on first save, gitignored)
    └── <prompt_a>.md     ← only files that were actually changed exist here
src/prompt_manager.py         ← load / save / revert / render
```

- On startup: for each prompt, use `prompts/user/<name>.md` if it exists, otherwise `prompts/<name>.md`
- Prompts use `{placeholder}` syntax; substitution happens at call time via `prompt_manager.render()`
- Some prompts are **shared blocks** (no placeholders themselves) that are injected into other prompts as `{block_name}`
- The config page shows one expander per prompt with a text area, Save and Revert buttons

---

## Step 1 — Audit the existing prompts

Find every place in the codebase where an LLM is called and a prompt string is assembled.

For each prompt, record:
- A short **name** (snake_case, used as the filename, e.g. `sql_generation`)
- The **placeholders** it needs (e.g. `{question}`, `{schema}`)
- Whether it is a **shared block** (reused by injection into other prompts) or a **standalone prompt** (sent directly to the LLM)

Shared blocks have no placeholders of their own — they are plain text inserted into other prompts via a `{block_name}` placeholder.

---

## Step 2 — Create the prompt files

Create a `prompts/` directory in the project root. Create one `.md` file per prompt.

### File format

```
<!-- Available placeholders: {placeholder_a}, {placeholder_b} -->
Your prompt text here.

{placeholder_a}

More text with {placeholder_b}.
```

- The `<!-- ... -->` comment on line 1 is for human reference only — it is stripped before the text is sent to the LLM. Shared block files (no placeholders) do not need this comment.
- Use `{curly_brace}` syntax for all placeholders.
- If a prompt injects a shared block, use `{block_name}` where the block should appear.

### Shared blocks

Shared blocks are prompt files whose entire content is injected into other prompts. They are listed first in `PROMPT_NAMES` so they are loaded before the prompts that reference them.

Example: if you have a `guidelines.md` shared block, other prompt files reference it as `{guidelines}`.

### `.gitignore`

Add the user overrides directory:

```
prompts/user/
```

---

## Step 3 — Create `src/prompt_manager.py`

Create this file in the project root. Replace the `PROMPT_NAMES`, `PROMPT_META`, and shared-block injection lines with the values appropriate for your project.

```python
"""Prompt manager.

Prompts are stored as .md files under prompts/ (originals, never modified by the app)
and prompts/user/ (user overrides, created only when the user saves a change).

Public API
----------
load_all()             → dict[str, str]   load all active prompts (called at startup)
get(name)              → str              return active prompt text for a given name
save_user(name, text)                     write a user override file
revert(name)                              delete the user override file
is_modified(name)      → bool             True if a user override exists
original_text(name)    → str              always returns the original (unmodified) prompt
render(name, prompts, **kwargs) → str     substitute placeholders and return final prompt
"""

import os
import re

PROMPTS_DIR = "prompts"
USER_DIR = os.path.join(PROMPTS_DIR, "user")

# !! ADAPT: list all prompt names in order; shared blocks must come first
PROMPT_NAMES = [
    "shared_block_a",   # shared block — injected into other prompts
    "prompt_one",
    "prompt_two",
]

# !! ADAPT: human-readable metadata shown in the config UI
PROMPT_META = {
    "shared_block_a": {
        "title": "Shared block A",
        "description": "Description of what this block contains and which prompts use it.",
        "placeholders": [],  # shared blocks have no placeholders
    },
    "prompt_one": {
        "title": "Prompt one",
        "description": "Description of when this prompt is used.",
        "placeholders": [
            ("{placeholder_a}", "Description of placeholder_a."),
            ("{shared_block_a}", "The shared block A (see above)."),
        ],
    },
    "prompt_two": {
        "title": "Prompt two",
        "description": "Description of when this prompt is used.",
        "placeholders": [
            ("{placeholder_b}", "Description of placeholder_b."),
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

    # !! ADAPT: inject shared blocks by name before other substitutions
    text = text.replace("{shared_block_a}", prompts.get("shared_block_a", ""))

    # Substitute remaining placeholders; ignore unknown keys
    for key, value in kwargs.items():
        text = text.replace(f"{{{key}}}", value if value is not None else "")

    return text
```

---

## Step 4 — Load prompts at app startup

In the Streamlit entry point (`app.py`), load all prompts once at startup and store them in `st.session_state`. Use the existing startup/caching pattern of the project.

```python
from src import prompt_manager

# Inside your startup block (after other initialisation):
if "prompts" not in st.session_state:
    st.session_state["prompts"] = prompt_manager.load_all()
```

The `if` guard ensures prompts are loaded only once per server process, not on every page rerun. They are refreshed explicitly when the user saves a change on the config page.

---

## Step 5 — Refactor the LLM-calling functions

For each function that assembles a prompt and calls the LLM, change the signature so it receives the **fully rendered prompt string** as a parameter instead of assembling it internally.

### Before

```python
def call_llm(question: str, context: str) -> str:
    prompt = f"Answer this: {question}\nContext: {context}"
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()
```

### After

```python
def call_llm(prompt: str) -> str:
    """Call the LLM with a fully-rendered prompt string."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()
```

The caller (the Streamlit page) is now responsible for rendering the prompt before passing it in:

```python
# In the page:
prompt = prompt_manager.render(
    "prompt_one",
    st.session_state["prompts"],
    placeholder_a="some value",
)
result = core.call_llm(prompt)
```

---

## Step 6 — Add the prompt editor to the config page

Add the following block to your configuration page (or create one if none exists). The only project-specific part is the `import` of `core` for the model selector — if your project has no model selector, omit that section.

```python
import streamlit as st
from src import prompt_manager

st.subheader("Prompts")
st.caption(
    "Edit the prompts used by the AI. Changes take effect immediately and are saved to "
    "`prompts/user/`. The original files in `prompts/` are never modified. "
    "Revert restores the original at any time."
)

prompts = st.session_state.get("prompts", prompt_manager.load_all())

for name in prompt_manager.PROMPT_NAMES:
    meta = prompt_manager.PROMPT_META[name]
    modified = prompt_manager.is_modified(name)

    badge = ":material/edit: **Modified**" if modified else ":material/check_circle: Original"
    with st.expander(f"**{meta['title']}** — {badge}", expanded=False):
        st.caption(meta["description"])

        if meta["placeholders"]:
            st.markdown("**Available placeholders:**")
            rows = "".join(
                f"<tr><td><code>{ph}</code></td><td>{desc}</td></tr>"
                for ph, desc in meta["placeholders"]
            )
            st.html(
                f"<table style='font-size:0.85em;border-collapse:collapse;width:100%'>"
                f"<thead><tr>"
                f"<th style='text-align:left;padding:4px 8px;border-bottom:1px solid #ddd;width:180px'>Placeholder</th>"
                f"<th style='text-align:left;padding:4px 8px;border-bottom:1px solid #ddd'>Description</th>"
                f"</tr></thead>"
                f"<tbody>{rows}</tbody></table>"
            )
            st.markdown("")

        current_text = prompts.get(name, prompt_manager.get(name))
        edited_text = st.text_area(
            "Prompt text",
            value=current_text,
            height=300,
            key=f"prompt_editor_{name}",
            label_visibility="collapsed",
        )

        col_save, col_revert, _ = st.columns([1, 1, 4])

        with col_save:
            if st.button(":material/save: Save", key=f"save_{name}", use_container_width=True):
                prompt_manager.save_user(name, edited_text)
                st.session_state["prompts"] = prompt_manager.load_all()
                st.success("Saved.")
                st.rerun()

        with col_revert:
            if modified:
                if st.button(
                    ":material/restart_alt: Revert to original",
                    key=f"revert_{name}",
                    use_container_width=True,
                ):
                    prompt_manager.revert(name)
                    st.session_state["prompts"] = prompt_manager.load_all()
                    st.success("Reverted to original.")
                    st.rerun()
```

---

## Step 7 — Verify

Run the following checks:

1. **Syntax** — all modified files parse without errors:
   ```bash
   python -c "import ast; [ast.parse(open(f).read()) for f in ['src/prompt_manager.py', 'app.py', 'src/core.py']]"
   ```

2. **Load** — all prompts load correctly:
   ```python
   from src import prompt_manager
   prompts = prompt_manager.load_all()
   assert set(prompts.keys()) == set(prompt_manager.PROMPT_NAMES)
   print("Loaded:", list(prompts.keys()))
   ```

3. **Render** — a rendered prompt contains no unresolved `{placeholder}` for known placeholders:
   ```python
   rendered = prompt_manager.render("prompt_one", prompts, placeholder_a="test value")
   assert "{placeholder_a}" not in rendered
   print(rendered)
   ```

4. **Save / revert cycle**:
   ```python
   prompt_manager.save_user("prompt_one", "test override")
   assert prompt_manager.is_modified("prompt_one")
   assert prompt_manager.get("prompt_one") == "test override"
   prompt_manager.revert("prompt_one")
   assert not prompt_manager.is_modified("prompt_one")
   ```

5. **App** — start the app, open the config page, edit a prompt, save, verify the badge changes to "Modified", revert, verify it returns to "Original".

---

## Notes

- The `prompts/` directory (originals) should be committed to git. The `prompts/user/` directory must be gitignored.
- HTML comments (`<!-- ... -->`) anywhere in a prompt file are stripped before the text is used. Use them freely for notes, examples, and placeholder documentation inside the file itself.
- Shared blocks (injected via `{block_name}`) are resolved before other placeholder substitution. This means a shared block cannot itself contain `{placeholders}` that are resolved at render time — they are treated as literal text.
- If the other project does not use Streamlit, the `src/prompt_manager.py` module (Steps 2–3) is framework-agnostic and can be reused as-is. Only the config page UI (Step 6) is Streamlit-specific.
