"""AI Data Assistant - Main application page.

Ask questions about your running data in plain English.
Configuration is done on the separate Config page.
"""
import os
import json
import matplotlib

matplotlib.use("Agg")  # headless backend — must be set before importing core (which imports pyplot)

import matplotlib.pyplot as plt
import streamlit as st

from src import core
from src import prompt_manager

PROMPT_HISTORY_FILE = "prompt_history.json"


def load_prompt_history() -> list[str]:
    """Load persisted prompt history from disk. Most recent first."""
    if not os.path.exists(PROMPT_HISTORY_FILE):
        return []
    try:
        with open(PROMPT_HISTORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def save_prompt_history(prompts: list[str]) -> None:
    """Persist prompt history to disk."""
    try:
        with open(PROMPT_HISTORY_FILE, "w") as f:
            json.dump(prompts, f, indent=2)
    except Exception:
        pass


def add_to_prompt_history(prompt: str) -> None:
    """Add a prompt to history (deduplicates, keeps most recent first, max 100)."""
    prompts = load_prompt_history()
    # Remove duplicate if already present, then prepend
    prompts = [p for p in prompts if p != prompt]
    prompts.insert(0, prompt)
    prompts = prompts[:100]
    save_prompt_history(prompts)
    # Keep session state in sync so the sidebar reflects the change immediately
    st.session_state.prompt_history = prompts


st.set_page_config(page_title="AI Data Assistant", page_icon="📊", layout="wide")


# ── Prompt management ───────────────────────────────────────────────────────
# Load prompts at startup (once per server process)
if "prompts" not in st.session_state:
    st.session_state["prompts"] = prompt_manager.load_all()


def get_prompts():
    """Helper to get current prompts."""
    return st.session_state.get("prompts", prompt_manager.load_all())


# ── Simple password gate ─────────────────────────────────────────────────────
def check_password() -> bool:
    app_password = os.getenv("APP_PASSWORD")
    if not app_password:
        return True  # no password configured -> open access (fine for local dev only)

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


# ── Cached setup (runs once per server process / data change) ───────────────
@st.cache_resource(show_spinner="Preparing data...")
def setup():
    core.ensure_parquet()
    return core.get_schema(), core.get_schema_df()


schema, schema_df = setup()

st.title("📊 AI Data Assistant")
st.caption("Ask questions about the running data in plain English.")

if "history" not in st.session_state:
    st.session_state.history = []  # list of dicts: question, sql, df, answer, fig
if "generate_chart" not in st.session_state:
    st.session_state.generate_chart = True
if "prompt_prefill" not in st.session_state:
    st.session_state.prompt_prefill = None  # set by prompt history click
if "prompt_history" not in st.session_state:
    st.session_state.prompt_history = load_prompt_history()

# Initialize selected_model from session state or default
if "selected_model" not in st.session_state:
    st.session_state.selected_model = core.MODEL

with st.sidebar:
    st.header("Settings")
    
    # Show currently selected model at the top
    st.markdown(f"**Model:** `{st.session_state.selected_model}`")
    st.markdown("---")

    # Note: Model selector, Data upload, and Data download are now on the Config page
    # Keeping generate_chart toggle and clear conversation here for convenience
    st.session_state.generate_chart = st.toggle(
        "Generate chart",
        value=st.session_state.generate_chart,
        help="When enabled, a chart is automatically generated after each answer. When disabled, a button appears so you can generate a chart on demand.",
    )
    if st.button("🗑️ Clear conversation"):
        st.session_state.history = []
        st.rerun()
    st.markdown("---")

    # ── Prompt history ────────────────────────────────────
    prompt_history = st.session_state.prompt_history
    with st.expander(f"Prompt history ({len(prompt_history)})", expanded=False):
        if not prompt_history:
            st.caption("No prompts yet.")
        else:
            with st.container(height=300):
                for i, p in enumerate(prompt_history):
                    if st.button(p, key=f"ph_{i}", use_container_width=True):
                        st.session_state.prompt_prefill = p
                        st.rerun()

    st.markdown("---")
    with st.expander("Schema"):
        st.dataframe(
            schema_df,
            hide_index=True,
            column_config={
                "Column": st.column_config.TextColumn("Column", width="medium"),
                "Type": st.column_config.TextColumn("Type", width="small"),
            },
        )


# ── Per-history-item chart button (rendered as a fragment to avoid full rerun) ──
def _render_chart_button(idx: int):
    item = st.session_state.history[idx]
    if item["fig"] is not None:
        st.pyplot(item["fig"])
    elif item.get("chart_on_demand"):
        if st.button("Generate chart", key=f"chart_btn_{idx}"):
            with st.spinner("Generating chart..."):
                chart_code = core.generate_chart_code(item["question"], item["df"], model=st.session_state.selected_model, prompts=get_prompts())
                if chart_code:
                    fig = core.render_chart(chart_code, item["question"], item["df"])
                    st.session_state.history[idx]["fig"] = fig
                    st.session_state.history[idx]["chart_on_demand"] = False
                    if fig is not None:
                        st.pyplot(fig)
                    else:
                        st.warning("Chart generation failed (see app.log)")
                else:
                    st.info("The data doesn\'t lend itself to a chart.")
                    st.session_state.history[idx]["chart_on_demand"] = False


# ── Render history ───────────────────────────────────────────────────────────
for i, item in enumerate(st.session_state.history):
    with st.chat_message("user"):
        st.write(item["question"])
    with st.chat_message("assistant"):
        st.write(item["answer"])
        if not item["df"].empty:
            st.dataframe(item["df"], width="stretch")
        _render_chart_button(i)
        with st.expander("SQL", expanded=False):
            st.code(item["final_sql"], language="sql")


# ── New question ───────────────────────────────────────────────────────────
question = None

if st.session_state.prompt_prefill:
    # Show an editable text input pre-filled with the history entry.
    # The user can modify it before running — only submits on button click.
    col1, col2 = st.columns([5, 1])
    with col1:
        edited = st.text_input(
            "Edit and run",
            value=st.session_state.prompt_prefill,
            label_visibility="collapsed",
            key="prefill_input",
        )
    with col2:
        if st.button("Run", use_container_width=True):
            st.session_state.prompt_prefill = None
            question = edited
else:
    question = st.chat_input("Ask a question about your running data...")

if question:
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Generating SQL..."):
            sql = core.generate_sql(question, schema, history=st.session_state.history, model=st.session_state.selected_model, prompts=get_prompts())

        with st.spinner("Querying data..."):
            try:
                df, final_sql, attempts_log = core.run_query_with_retries(sql, schema, model=st.session_state.selected_model, prompts=get_prompts())
                for line in attempts_log:
                    st.warning(line)
            except Exception as e:
                st.error(f"Failed after retries: {e}")
                st.stop()

        with st.spinner("Formulating answer..."):
            answer = core.formulate_answer(question, df, history=st.session_state.history, model=st.session_state.selected_model, prompts=get_prompts())
        st.write(answer)

        if not df.empty:
            st.dataframe(df, width="stretch")

        fig = None
        chart_on_demand = False
        if st.session_state.generate_chart:
            with st.spinner("Checking if a chart makes sense..."):
                chart_code = core.generate_chart_code(question, df, model=st.session_state.selected_model, prompts=get_prompts())
                if chart_code:
                    fig = core.render_chart(chart_code, question, df)
                    if fig is not None:
                        st.pyplot(fig)
                    else:
                        st.warning("Chart generation failed (see app.log)")
        else:
            chart_on_demand = True
            new_idx = len(st.session_state.history)
            if st.button("Generate chart", key=f"chart_btn_{new_idx}"):
                with st.spinner("Generating chart..."):
                    chart_code = core.generate_chart_code(question, df, model=st.session_state.selected_model, prompts=get_prompts())
                    if chart_code:
                        fig = core.render_chart(chart_code, question, df)
                        chart_on_demand = False
                        if fig is not None:
                            st.pyplot(fig)
                        else:
                            st.warning("Chart generation failed (see app.log)")
                    else:
                        st.info("The data doesn\'t lend itself to a chart.")
                        chart_on_demand = False

        with st.expander("SQL", expanded=False):
            st.code(final_sql, language="sql")

    add_to_prompt_history(question)
    st.session_state.history.append(
        {
            "question": question,
            "final_sql": final_sql,
            "answer": answer,
            "df": df,
            "fig": fig,
            "chart_on_demand": chart_on_demand,
        }
    )
    st.rerun()
