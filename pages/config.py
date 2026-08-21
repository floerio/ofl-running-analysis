"""Configuration page for AI Data Assistant.

This page allows users to:
- Select the AI model
- Edit prompts at runtime
"""
import os
import streamlit as st

import core
import prompt_manager

st.set_page_config(page_title="Configuration", page_icon="⚙️")

# ── Load prompts at startup ───────────────────────────────────────────────────
if "prompts" not in st.session_state:
    st.session_state["prompts"] = prompt_manager.load_all()


def get_prompts():
    """Helper to get current prompts."""
    return st.session_state.get("prompts", prompt_manager.load_all())


# ── Password gate (same as app.py) ──────────────────────────────────────────
def check_password() -> bool:
    app_password = os.getenv("APP_PASSWORD")
    if not app_password:
        return True  # no password configured -> open access

    if st.session_state.get("authenticated"):
        return True

    st.title("🔒 AI Data Assistant")
    pwd = st.text_input("Password", type="password")
    if st.button("Log in"):
        if pwd == app_password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Wrong password")
    return False


if not check_password():
    st.stop()


st.title("⚙️ Configuration")
st.markdown("Configure the AI model and edit prompts used by the assistant.")

# ── Model selector ───────────────────────────────────────────────────────────
st.header("🤖 AI Model")

@st.cache_data(show_spinner=False)
def fetch_models():
    return core.get_available_models()

available_models = fetch_models()

if "selected_model" not in st.session_state:
    st.session_state.selected_model = core.MODEL

default_idx = available_models.index(st.session_state.selected_model) if st.session_state.selected_model in available_models else 0
st.session_state.selected_model = st.selectbox(
    "Select the LLM to use for SQL generation and answering.",
    options=available_models,
    index=default_idx,
)

st.markdown("---")

# ── Prompt editor ────────────────────────────────────────────────────────────
st.header("📝 Prompt Configuration")
st.caption(
    "Edit the prompts used by the AI. Changes take effect immediately and are saved to "
    "`prompts/user/`. The original files in `prompts/` are never modified. "
    "Revert restores the original at any time."
)

prompts = get_prompts()

for name in prompt_manager.PROMPT_NAMES:
    meta = prompt_manager.PROMPT_META[name]
    modified = prompt_manager.is_modified(name)

    badge = "📝 **Modified**" if modified else "✅ Original"
    with st.expander(f"**{meta['title']}** — {badge}", expanded=False):
        st.caption(meta["description"])

        if meta["placeholders"]:
            st.markdown("**Available placeholders:**")
            rows = "".join(
                f"<tr><td><code>{ph}</code></td><td>{desc}</td></tr>"
                for ph, desc in meta["placeholders"]
            )
            st.markdown(
                f"""<table style='font-size:0.85em;border-collapse:collapse;width:100%'>
                <thead><tr>
                <th style='text-align:left;padding:4px 8px;border-bottom:1px solid #ddd;width:180px'>Placeholder</th>
                <th style='text-align:left;padding:4px 8px;border-bottom:1px solid #ddd'>Description</th>
                </tr></thead>
                <tbody>{rows}</tbody></table>""",
                unsafe_allow_html=True,
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
            if st.button("Save", key=f"save_{name}", use_container_width=True):
                prompt_manager.save_user(name, edited_text)
                st.session_state["prompts"] = prompt_manager.load_all()
                st.success("Saved.")
                st.rerun()

        with col_revert:
            if modified:
                if st.button(
                    "Revert",
                    key=f"revert_{name}",
                    use_container_width=True,
                ):
                    prompt_manager.revert(name)
                    st.session_state["prompts"] = prompt_manager.load_all()
                    st.success("Reverted to original.")
                    st.rerun()
