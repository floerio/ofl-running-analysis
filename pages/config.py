"""Configuration page for AI Data Assistant.

This page allows users to:
- Select the AI model
- Upload/Download data
- Edit prompts at runtime
"""
import os
import logging
import streamlit as st

from src import core
from src import prompt_manager

logger = logging.getLogger(__name__)

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

# ── Data Management ───────────────────────────────────────────────────────
st.header("📁 Data Management")

col_upload, col_download = st.columns(2)

with col_upload:
    uploaded_file = st.file_uploader(
        "Upload CSV",
        type=["csv"],
        help="Upload a Garmin CSV to merge new activities (duplicates skipped)",
        key="data_upload",
    )
    
    if uploaded_file is not None:
        with st.spinner("Processing upload..."):
            try:
                # Save uploaded file to temp location
                temp_path = "temp_upload.csv"
                core.save_uploaded_file(uploaded_file, temp_path)
                
                # Merge data
                rows_added, message = core.merge_data(temp_path)
                
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                
                st.success(message)
                
                # Always rerun to reload fresh data and schema
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error processing upload: {e}")

with col_download:
    if st.button("📥 Download Current Data", use_container_width=True):
        with open(core.CSV_FILE, "rb") as f:
            st.download_button(
                label="Download data.csv",
                data=f,
                file_name="running_data.csv",
                mime="text/csv",
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
