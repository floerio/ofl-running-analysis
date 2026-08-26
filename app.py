"""AI Data Assistant - Main application page.

Ask questions about your running data in plain English.
Configuration is done on the separate Config page.
"""
import matplotlib

matplotlib.use("Agg")  # headless backend — must be set before importing core (which imports pyplot)

import matplotlib.pyplot as plt
import streamlit as st

from src import core
from src import prompt_manager
from src import data_dictionary_manager
from src import business_glossary_manager
from src import query_manager
from src import ui_utils


st.set_page_config(page_title="AI Data Assistant", page_icon="📊", layout="wide")


# ── Prompt management ───────────────────────────────────────────────────────
# Load prompts at startup (once per server process)
if "prompts" not in st.session_state:
    _prompts = prompt_manager.load_all()
    _prompts["data_dictionary"] = data_dictionary_manager.load()
    _prompts["business_glossary"] = business_glossary_manager.load()
    st.session_state["prompts"] = _prompts


def get_prompts():
    """Helper to get current prompts."""
    return st.session_state.get("prompts", prompt_manager.load_all())


if not ui_utils.check_password():
    st.stop()


# ── Cached setup (runs once per server process / data change) ───────────────
@st.cache_resource(show_spinner="Preparing data...")
def setup():
    core.ensure_parquet()
    return core.get_schema(), core.get_schema_df()


schema, schema_df = setup()

# Make schema available to all pages via session state
st.session_state["schema"] = schema
st.session_state["schema_df"] = schema_df

st.title("📊 AI Data Assistant")
st.caption("Ask questions about the running data in plain English.")

if "history" not in st.session_state:
    st.session_state.history = []  # list of dicts: question, sql, df, answer, fig
if "generate_chart" not in st.session_state:
    st.session_state.generate_chart = False
if "prompt_prefill" not in st.session_state:
    st.session_state.prompt_prefill = None  # set by prompt history click
if "prompt_history" not in st.session_state:
    st.session_state.prompt_history = ui_utils.load_prompt_history()
if "queries" not in st.session_state:
    st.session_state.queries = query_manager.load_all()
if "suggestions" not in st.session_state:
    st.session_state.suggestions = []
if "show_suggestions" not in st.session_state:
    st.session_state.show_suggestions = True
if "chat_mode" not in st.session_state:
    st.session_state.chat_mode = False

# Initialize selected_model from session state or default
if "selected_model" not in st.session_state:
    st.session_state.selected_model = core.MODEL

with st.sidebar:
    st.header("Settings")
    
    # Show currently selected model at the top
    st.markdown(f"**Model:** `{st.session_state.selected_model}`")
    st.markdown("---")

    # Note: Model selector, Data upload, Data download, and chart toggle are on the Config page
    if st.button("🗑️ Clear conversation"):
        st.session_state.history = []
        st.session_state.suggestions = []
        st.rerun()

    # Chat Mode status indicator
    if st.session_state.chat_mode:
        st.markdown("💬 **Chat Mode** `ON`")
    else:
        st.markdown("⚪ **Chat Mode** `OFF`")
    st.markdown("---")

    # ── Pre-defined queries ────────────────────────────────────
    queries = st.session_state.queries
    with st.expander("Pre-defined queries", expanded=False):
        for name in query_manager.QUERY_NAMES:
            query_text = queries.get(name, query_manager.get(name))
            if st.button(query_text, key=f"query_{name}", use_container_width=True):
                st.session_state.prompt_prefill = query_text
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


# ── Per-history-item chart button ────────────────────────────────────────────
def _render_chart_button(idx: int):
    item = st.session_state.history[idx]
    if item["fig"] is not None:
        st.pyplot(item["fig"])
    elif item.get("chart_on_demand"):
        col_btn, col_hint = st.columns([2, 5])
        with col_btn:
            clicked = st.button("📊 Generate chart", key=f"chart_btn_{idx}", use_container_width=True)
        with col_hint:
            st.caption("Auto-selects chart type · bar charts include a trend line for time series")
        if clicked:
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

# ── Render history ───────────────────────────────────────────
is_last_idx = len(st.session_state.history) - 1
for i, item in enumerate(st.session_state.history):
    with st.chat_message("user"):
        st.write(item["question"])
    with st.chat_message("assistant"):
        st.write(item["answer"])
        if not item.get("is_followup"):
            if not item["df"].empty:
                st.dataframe(item["df"], width="stretch")
            _render_chart_button(i)
            with st.expander("SQL", expanded=False):
                st.code(item["final_sql"], language="sql")
            try:
                filename, content_pdf = ui_utils.build_pdf_export(item)
                st.download_button(
                    label="📄 Export as PDF",
                    data=content_pdf,
                    file_name=filename,
                    mime="application/pdf",
                    key=f"dl_{i}",
                )
            except Exception as _pdf_err:
                import logging as _logging
                _logging.getLogger(__name__).error(
                    "PDF export failed for history item %d (question: %r): %s",
                    i, item.get("question", "")[:80], _pdf_err,
                )

    # Show follow-up suggestions below the last answer
    if i == is_last_idx and st.session_state.suggestions:
        st.markdown("**💡 Follow-up suggestions:**")
        for j, suggestion in enumerate(st.session_state.suggestions):
            if st.button(suggestion, key=f"suggestion_{i}_{j}"):
                st.session_state.prompt_prefill = suggestion
                st.session_state.suggestions = []
                st.rerun()

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
    # Clear suggestions whenever a new question is submitted
    st.session_state.suggestions = []

    with st.chat_message("user"):
        st.write(question)

    # ── Chat Mode intent classification ─────────────────────────────────
    intent = "NEW_QUERY"
    if st.session_state.chat_mode and st.session_state.history:
        last_item = st.session_state.history[-1]
        last_question = last_item.get("question", "")
        last_result_preview = last_item["df"].head(5).to_string(index=False) if not last_item.get("is_followup") and not last_item["df"].empty else last_item.get("answer", "")[:300]
        with st.spinner("Classifying intent..."):
            intent = core.classify_intent(
                question,
                last_question=last_question,
                last_result_preview=last_result_preview,
                history=st.session_state.history,
                model=st.session_state.selected_model,
                prompts=get_prompts(),
            )

    # ── FOLLOWUP: conversational answer, no SQL ───────────────────────────
    if intent == "FOLLOWUP":
        last_item = st.session_state.history[-1]
        last_question = last_item.get("question", "")
        last_result = last_item["df"].to_string(index=False) if not last_item.get("is_followup") and not last_item["df"].empty else last_item.get("answer", "")
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                answer = core.formulate_followup_answer(
                    question,
                    last_question=last_question,
                    last_result=last_result,
                    history=st.session_state.history,
                    model=st.session_state.selected_model,
                    prompts=get_prompts(),
                )
            st.write(answer)
        ui_utils.add_to_prompt_history(question)
        st.session_state.history.append({
            "question": question,
            "answer": answer,
            "is_followup": True,
            "df": __import__("pandas").DataFrame(),
            "fig": None,
            "final_sql": "",
            "chart_on_demand": False,
        })
        st.rerun()

    # ── UNCLEAR: general conversational answer ────────────────────────────
    elif intent == "UNCLEAR":
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                answer = core.formulate_general_answer(
                    question,
                    history=st.session_state.history,
                    model=st.session_state.selected_model,
                    prompts=get_prompts(),
                )
            st.write(answer)
        ui_utils.add_to_prompt_history(question)
        st.session_state.history.append({
            "question": question,
            "answer": answer,
            "is_followup": True,
            "df": __import__("pandas").DataFrame(),
            "fig": None,
            "final_sql": "",
            "chart_on_demand": False,
        })
        st.rerun()

    # ── NEW_QUERY: full SQL pipeline ───────────────────────────────────────
    else:
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
                col_btn, col_hint = st.columns([2, 5])
                with col_btn:
                    clicked = st.button("📊 Generate chart", key=f"chart_btn_{new_idx}", use_container_width=True)
                with col_hint:
                    st.caption("Auto-selects chart type · bar charts include a trend line for time series")
                if clicked:
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
                            st.info("The data doesn't lend itself to a chart.")
                            chart_on_demand = False
            with st.expander("SQL", expanded=False):
                st.code(final_sql, language="sql")

        ui_utils.add_to_prompt_history(question)
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

        # Generate follow-up suggestions if enabled
        if st.session_state.show_suggestions:
            st.session_state.suggestions = core.generate_followup_suggestions(
                question, df,
                model=st.session_state.selected_model,
                prompts=get_prompts(),
            )

        st.rerun()
