"""SQL Browser page for AI Data Assistant.

Run SQL directly against data.parquet. The table is registered as `data`.
"""
import streamlit as st

from src import core
from src import ui_utils

st.set_page_config(page_title="SQL Browser", page_icon="🔍", layout="wide")

if not ui_utils.check_password():
    st.stop()

st.title("🔍 SQL Browser")
st.caption("Run SQL directly against `data.parquet`. The table is registered as `data`.")

# ── Sidebar: schema + sample queries ─────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📋 Schema")
    schema_df = st.session_state.get("schema_df")
    if schema_df is not None:
        st.dataframe(
            schema_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Column": st.column_config.TextColumn("Column", width="medium"),
                "Type":   st.column_config.TextColumn("Type",   width="small"),
            },
        )
    else:
        st.caption("Schema not loaded — open the main page first.")

    st.markdown("---")
    st.markdown("### 💡 Sample queries")

    SAMPLES = [
        "SELECT * FROM data LIMIT 100",
        "DESCRIBE data",
        "SELECT COUNT(*) AS total_rows FROM data",
        "SELECT \"Activity Type\", COUNT(*) AS cnt FROM data GROUP BY 1 ORDER BY cnt DESC",
        "SELECT strftime(Date, '%Y-%m') AS month, COUNT(*) AS runs FROM data GROUP BY 1 ORDER BY 1",
        "SELECT Title, Date, Distance, \"Avg HR\", \"Avg Pace\" FROM data ORDER BY Date DESC LIMIT 20",
    ]

    for sample in SAMPLES:
        if st.button(sample, use_container_width=True, key=f"sample_{hash(sample)}"):
            st.session_state["sql_browser_query"] = sample
            st.rerun()

# ── Session state default ─────────────────────────────────────────────────────
st.session_state.setdefault("sql_browser_query", "SELECT * FROM data LIMIT 100")

# ── SQL editor ────────────────────────────────────────────────────────────────
sql = st.text_area(
    "SQL query",
    value=st.session_state["sql_browser_query"],
    height=150,
    placeholder="SELECT * FROM data LIMIT 100",
    label_visibility="collapsed",
)

col_run, col_clear, _ = st.columns([1, 1, 5])
with col_run:
    run = st.button("▶️ Run", type="primary", use_container_width=True)
with col_clear:
    if st.button("✖️ Clear", use_container_width=True):
        st.session_state["sql_browser_query"] = ""
        st.rerun()

# ── Execute & display ─────────────────────────────────────────────────────────
if run and sql.strip():
    st.session_state["sql_browser_query"] = sql
    try:
        with st.spinner("Running query..."):
            df = core.run_query(sql.strip())

        row_count = len(df)
        col_count = len(df.columns)
        st.success(
            f"{row_count:,} row{'s' if row_count != 1 else ''} "
            f"× {col_count} column{'s' if col_count != 1 else ''}"
        )

        st.dataframe(df, use_container_width=True, hide_index=True)

        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download as CSV",
            data=csv_bytes,
            file_name="query_result.csv",
            mime="text/csv",
        )

    except Exception as e:
        st.error(f"**Query error:** {e}")
