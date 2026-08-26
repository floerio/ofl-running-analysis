"""Log Viewer page for AI Data Assistant.

Live view of app.log with level filtering, refresh, and clear.
"""
import os
from typing import Optional
import streamlit as st

from src import ui_utils

st.set_page_config(page_title="App Log", page_icon="📋")

if not ui_utils.check_password():
    st.stop()

LOG_FILE = "app.log"

st.title("📋 App Log")
st.caption("Live view of `app.log`. Most recent entries at the top.")

col_refresh, col_clear, _ = st.columns([1, 1, 6])

with col_refresh:
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()

with col_clear:
    if st.button("🗑️ Clear log", use_container_width=True):
        try:
            open(LOG_FILE, "w").close()
            st.success("Log cleared.")
            st.rerun()
        except Exception as e:
            st.error(f"Could not clear log: {e}")

st.markdown("---")

# ── Level filter ──────────────────────────────────────────────────────────────
selected_levels = st.multiselect(
    "Filter by level",
    options=["INFO", "WARNING", "ERROR"],
    default=["INFO", "WARNING", "ERROR"],
    format_func=lambda l: {"INFO": "🟢 INFO", "WARNING": "🟡 WARNING", "ERROR": "🔴 ERROR"}[l],
)

st.markdown("---")

if not os.path.exists(LOG_FILE):
    st.info("No log file found yet. The log is created when the app first writes an entry.")
else:
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if not lines:
        st.info("Log is empty.")
    else:
        def _level(line: str) -> Optional[str]:
            if "[ERROR]" in line:
                return "ERROR"
            if "[WARNING]" in line:
                return "WARNING"
            if "[INFO]" in line:
                return "INFO"
            return None

        def _level_icon(level: str) -> str:
            return {"INFO": "🟢", "WARNING": "🟡", "ERROR": "🔴"}.get(level, "⚪")

        # Group lines into multi-line entries: a new entry starts whenever a line
        # has a recognised level tag; continuation lines belong to the preceding entry.
        entries: list[list] = []
        for line in lines:
            lvl = _level(line)
            if lvl is not None:
                entries.append([lvl, line])
            elif entries:
                entries[-1][1] += line  # append continuation to current entry

        # Filter by selected levels and reverse (most recent first)
        filtered = [e for e in entries if e[0] in selected_levels]
        filtered = list(reversed(filtered))

        if not filtered:
            st.info("No log entries match the selected levels.")
        else:
            st.caption(f"Showing {len(filtered)} of {len(entries)} entries.")
            log_text = "".join(f"{_level_icon(lvl)}  {text}" for lvl, text in filtered)
            st.code(log_text, language=None)
