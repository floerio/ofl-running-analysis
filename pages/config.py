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
from src import query_manager
from src import data_dictionary_manager
from src import business_glossary_manager
from src import ui_utils

logger = logging.getLogger(__name__)

st.set_page_config(page_title="Configuration", page_icon="⚙️")

# ── Load prompts, queries, and data dictionary at startup ──────────────────
if "prompts" not in st.session_state:
    _prompts = prompt_manager.load_all()
    _prompts["data_dictionary"] = data_dictionary_manager.load()
    _prompts["business_glossary"] = business_glossary_manager.load()
    st.session_state["prompts"] = _prompts
if "queries" not in st.session_state:
    st.session_state["queries"] = query_manager.load_all()


def get_prompts():
    """Helper to get current prompts."""
    return st.session_state.get("prompts", prompt_manager.load_all())


def get_queries():
    """Helper to get current queries."""
    return st.session_state.get("queries", query_manager.load_all())


if not ui_utils.check_password():
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

# ── Chart generation ────────────────────────────────────────────────────
st.header("📊 Chart Generation")
st.caption(
    "When enabled, a chart is automatically generated after each answer. "
    "When disabled, a ‘📊 Generate chart’ button appears on the chat page so you can trigger it on demand."
)
st.session_state.setdefault("generate_chart", False)
st.session_state.generate_chart = st.toggle(
    "Auto-generate charts",
    value=st.session_state.generate_chart,
)

st.markdown("---")

# ── Follow-up Suggestions ────────────────────────────────────────
st.header("💡 Follow-up Suggestions")
st.caption(
    "When enabled, the AI generates 5 clickable follow-up questions after each answer. "
    "Click any suggestion to pre-fill the chat input."
)
st.session_state.setdefault("show_suggestions", True)
st.session_state.show_suggestions = st.toggle(
    "Enable follow-up suggestions",
    value=st.session_state.show_suggestions,
)

st.markdown("---")

# ── Chat Mode ───────────────────────────────────────────────────
st.header("💬 Chat Mode")
st.caption(
    "When enabled, the AI classifies each question as a new data query or a follow-up. "
    'Follow-up questions (e.g. "why is that?", "explain this") are answered conversationally '
    "without running a new SQL query."
)
st.session_state.setdefault("chat_mode", False)
st.session_state.chat_mode = st.toggle(
    "Enable Chat Mode",
    value=st.session_state.chat_mode,
)
if st.session_state.chat_mode:
    st.success("💬 Chat Mode is **ON** — follow-up questions skip the SQL pipeline")
else:
    st.info("⚪ Chat Mode is **OFF** — every question runs a full SQL query")

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
            rows_html = "".join(
                f"""
                <tr style='background:{'#f9f9f9' if i % 2 == 0 else 'transparent'}'>
                  <td style='padding:5px 10px;font-family:monospace;font-size:0.85em;
                             white-space:nowrap;vertical-align:top;width:200px'>{ph}</td>
                  <td style='padding:5px 10px;font-size:0.85em;vertical-align:top'>{desc}</td>
                </tr>"""
                for i, (ph, desc) in enumerate(meta["placeholders"])
            )
            st.markdown(
                f"""<table style='border-collapse:collapse;width:100%;margin-bottom:8px'>
                <thead><tr style='border-bottom:2px solid #ddd'>
                  <th style='text-align:left;padding:5px 10px;font-size:0.85em;width:200px'>Placeholder</th>
                  <th style='text-align:left;padding:5px 10px;font-size:0.85em'>Description</th>
                </tr></thead>
                <tbody>{rows_html}</tbody></table>""",
                unsafe_allow_html=True,
            )
        else:
            st.caption("ℹ️ This is a shared block injected into other prompts. It has no placeholders of its own.")

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

st.markdown("---")

# ── Data Dictionary editor ───────────────────────────────────────────────────
dd_modified = data_dictionary_manager.is_modified()
dd_badge = "📝 **Modified**" if dd_modified else "✅ Original"

st.header(f"📝 Data Dictionary — {dd_badge}")
st.caption(
    "Describes each column in plain English. Injected into all LLM prompts as `{data_dictionary}` "
    "so the AI understands ambiguous column names, units, and quirks. "
    "Changes take effect immediately. The original `data_dictionary/default.md` is never modified."
)
st.caption(
    "Format: use `## Exact Column Name` as headings, then `**Label:**` and `**Description:**` fields."
)

current_dd = data_dictionary_manager.load()
edited_dd = st.text_area(
    "Data Dictionary",
    value=current_dd,
    height=500,
    key="data_dict_editor",
    label_visibility="collapsed",
)

col_save, col_revert, _ = st.columns([1, 1, 4])

with col_save:
    if st.button("Save", key="save_data_dict", use_container_width=True):
        data_dictionary_manager.save_user(edited_dd)
        # Re-inject into prompts session state so it takes effect immediately
        prompts = get_prompts()
        prompts["data_dictionary"] = data_dictionary_manager.load()
        st.session_state["prompts"] = prompts
        st.success("Saved.")
        st.rerun()

with col_revert:
    if dd_modified:
        if st.button("Revert", key="revert_data_dict", use_container_width=True):
            data_dictionary_manager.revert()
            prompts = get_prompts()
            prompts["data_dictionary"] = data_dictionary_manager.load()
            st.session_state["prompts"] = prompts
            st.success("Reverted to original.")
            st.rerun()

st.markdown("---")

# ── Business Glossary editor ─────────────────────────────────────────────────
bg_modified = business_glossary_manager.is_modified()
bg_badge = "📝 **Modified**" if bg_modified else "✅ Original"

st.header(f"📖 Business Glossary — {bg_badge}")
st.caption(
    "Defines running-specific terms, Garmin metric names, and common phrasings. "
    "Injected into SQL generation and answer formulation prompts as `{business_glossary}` "
    "so the AI correctly maps informal questions to the right columns. "
    "Changes take effect immediately. The original `business_glossary/default.md` is never modified."
)
st.caption(
    "Format: use `## Term Name` as headings, then `**Refers to:**`, `**Maps to:**`, and optional `**Notes:**` fields."
)

current_bg = business_glossary_manager.load()
edited_bg = st.text_area(
    "Business Glossary",
    value=current_bg,
    height=500,
    key="business_glossary_editor",
    label_visibility="collapsed",
)

col_save, col_revert, _ = st.columns([1, 1, 4])

with col_save:
    if st.button("Save", key="save_business_glossary", use_container_width=True):
        business_glossary_manager.save_user(edited_bg)
        prompts = get_prompts()
        prompts["business_glossary"] = business_glossary_manager.load()
        st.session_state["prompts"] = prompts
        st.success("Saved.")
        st.rerun()

with col_revert:
    if bg_modified:
        if st.button("Revert", key="revert_business_glossary", use_container_width=True):
            business_glossary_manager.revert()
            prompts = get_prompts()
            prompts["business_glossary"] = business_glossary_manager.load()
            st.session_state["prompts"] = prompts
            st.success("Reverted to original.")
            st.rerun()
