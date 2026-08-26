# Implementation Plan: Missing Features from kn-query-assistant

This document describes step-by-step implementation plans for each of the 12 features
present in `kn-query-assistant` that are currently missing from `ofl-running-analysis`.

Features are ordered from least to most invasive — earlier features lay groundwork
that later ones build on.

---

## Feature Overview

| # | Feature | Effort | Depends on | Status |
|---|---------|--------|------------|--------|
| 1 | LLM Result Truncation | 🟢 Small | — | ✅ Done |
| 2 | Structured Answer Format | 🟢 Small | — | ✅ Done |
| 3 | Prompt Placeholder Reference Table | 🟢 Small | — | ✅ Done |
| 4 | `src/ui_utils.py` Shared UI Module | 🟡 Medium | — | ✅ Done |
| 5 | PDF Export | 🟡 Medium | #4 | ✅ Done |
| 6 | Business Glossary | 🟡 Medium | — | ✅ Done |
| 7 | `src/query_manager.py` Dedicated Module | 🟢 Small | — | ✅ Done |
| 8 | SQL Browser Page | 🟡 Medium | — | ✅ Done |
| 9 | Log Viewer Page | 🟢 Small | — | ✅ Done |
| 10 | Follow-up Suggestions | 🟡 Medium | — | ⬜ Pending |
| 11 | Chat Mode (Intent Classification) | 🔴 Large | #10 | ⬜ Pending |
| 12 | Data Dictionary (Markdown format) | 🔴 Large | — | ✅ Done |

---

## Feature 1 — LLM Result Truncation (`format_result_for_prompt()`) ✅ Done

### What
Add a helper that caps DataFrame results to 200 rows before injecting them into
LLM prompts, with an explanatory note when truncated.

### Why
Large query results can exceed the LLM's context window and degrade answer quality.

### Files to change
- `src/core.py` — add `format_result_for_prompt()`, use it in `formulate_answer()`
  and `generate_chart_code()`

### Steps

1. **Add constant** to `src/core.py`:
   ```python
   LLM_RESULT_ROW_LIMIT = 200
   ```

2. **Add helper function** to `src/core.py`:
   ```python
   def format_result_for_prompt(df: pd.DataFrame) -> str:
       if df.empty:
           return "No results found."
       if len(df) <= LLM_RESULT_ROW_LIMIT:
           return df.to_string(index=False)
       truncated = df.head(LLM_RESULT_ROW_LIMIT).to_string(index=False)
       return (
           f"{truncated}\n\n"
           f"[Result truncated: showing {LLM_RESULT_ROW_LIMIT} of {len(df)} rows. "
           "The full result is available in the data table below.]"
       )
   ```

3. **Replace** `result_df.to_string(index=False)` calls in `formulate_answer()` and
   `generate_chart_code()` with `format_result_for_prompt(result_df)`.

### Acceptance criteria
- Asking a question that returns >200 rows passes only 200 rows to the LLM
- The truncation note is visible in the rendered prompt (check via prompt history)
- Questions returning ≤200 rows are unaffected

---

## Feature 2 — Structured Answer Format (Facts / Summary / Analysis / Suggestions) ✅ Done

### What
Update the `formulate_answer.md` prompt to produce a structured response with
four named sections: **Facts**, **Summary**, **Analysis**, **Suggestions**.

### Why
A structured format is more scannable, consistent, and useful than a free-form
paragraph.

### Files to change
- `prompts/formulate_answer.md` — rewrite prompt instructions

### Steps

1. **Open** `prompts/formulate_answer.md`.

2. **Rewrite the instructions** to ask the LLM to respond using this structure:
   ```
   ### Facts
   Bullet-point list of raw findings directly from the data.

   ### Summary
   One or two sentences summarising the overall picture.

   ### Analysis
   Patterns, trends, comparisons, or anomalies worth noting.

   ### Suggestions
   Optional: actionable recommendations or follow-up ideas based on the data.
   ```

3. **Test** with several questions; verify the four sections appear in the UI.

4. **No code changes required** — `app.py` renders the answer via `st.write()` which
   handles Markdown headings natively.

### Acceptance criteria
- Every answer contains the four section headings
- Sections are rendered as Markdown in the chat UI
- Existing `{question}`, `{result_str}`, `{history_section}` placeholders still work

---

## Feature 3 — Prompt Placeholder Reference Table in Config UI ✅ Done

### What
Add a table of available `{placeholder}` variables and their descriptions beneath
each prompt's title in the Config page expander.

### Why
Editors currently have no in-UI reference for which placeholders are valid per
prompt. They must read the source code or markdown files.

### Files to change
- `src/prompt_manager.py` — verify/expand `PROMPT_META` `placeholders` entries
- `pages/config.py` — render the placeholder table inside each prompt expander

### Steps

1. **Audit `PROMPT_META`** in `src/prompt_manager.py`.  
   Ensure all prompts list their placeholders accurately. Add any that are missing
   (e.g. `{schema_description}`, `{history_section}` in `generate_sql`).

2. **Add rendering logic** in `pages/config.py` inside the prompt expander loop
   (already partially present — the `if meta["placeholders"]:` block exists but may
   need styling improvements to match kn-project):
   - Use an HTML table for compact two-column layout (Placeholder | Description)
   - Show the table only when `meta["placeholders"]` is non-empty

3. **Verify** the `sql_guidelines` prompt shows "No placeholders" or is omitted
   gracefully (it has `"placeholders": []`).

### Acceptance criteria
- Each prompt expander shows a placeholder table with all valid variables
- `sql_guidelines` expander either shows an empty state or skips the table
- The table renders correctly in Streamlit (no raw HTML visible)

---

## Feature 4 — `src/ui_utils.py` Shared UI Utilities Module ✅ Done

### What
Create `src/ui_utils.py` to hold shared UI helper functions, starting with
prompt history management (currently inlined in `app.py`).

### Why
- `app.py` currently contains prompt-history logic that will also be needed by
  other pages (e.g. after PDF export is added)
- Prepares for Feature 5 (PDF export helpers)

### Files to change
- `src/ui_utils.py` — **new file**
- `src/__init__.py` — no change needed (file is importable automatically)
- `app.py` — import from `src.ui_utils` instead of defining inline

### Steps

1. **Create `src/ui_utils.py`** with:
   ```python
   PROMPT_HISTORY_FILE = "prompt_history.json"

   def load_prompt_history() -> list[str]: ...
   def save_prompt_history(prompts: list[str]) -> None: ...
   def add_to_prompt_history(prompt: str) -> None: ...
   ```
   Move the existing implementations verbatim from `app.py`.

2. **Update `app.py`**:
   - Add `from src import ui_utils`
   - Remove the three function definitions
   - Replace all call sites:  
     `load_prompt_history()` → `ui_utils.load_prompt_history()`  
     `save_prompt_history(...)` → `ui_utils.save_prompt_history(...)`  
     `add_to_prompt_history(...)` → `ui_utils.add_to_prompt_history(...)`

3. **Run the app** and verify prompt history still works end-to-end.

### Acceptance criteria
- Prompt history loads, saves, and deduplicates correctly
- No code duplication between `app.py` and `ui_utils.py`
- Module is importable: `from src import ui_utils`

---

## Feature 5 — PDF Export per Answer ✅ Done

### What
Add a "Download as PDF" button below each answer that exports the question,
answer text (Markdown rendered), optional chart (as PNG), and the SQL query.

### Why
Users want to share or archive individual answers without exporting the whole
conversation.

### Files to change
- `requirements.txt` — add `reportlab`
- `src/ui_utils.py` — add `export_answer_as_pdf(question, answer, fig, sql) -> bytes`
- `app.py` — add `st.download_button` below each rendered answer

### Steps

1. **Add `reportlab` to `requirements.txt`** and install:
   ```
   pip install reportlab
   ```

2. **Add `export_answer_as_pdf()` to `src/ui_utils.py`**:
   - Accept: `question: str`, `answer: str`, `fig` (matplotlib Figure or None),
     `sql: str`
   - Build a PDF using `reportlab.platypus` (SimpleDocTemplate):
     - Bold heading: the question
     - Body paragraph: answer text (strip Markdown syntax for plain PDF rendering,
       or render Markdown headings as bold paragraphs)
     - If `fig` is not None: save figure to an in-memory PNG buffer,
       embed as `reportlab.platypus.Image`
     - Monospace block: the SQL
   - Return the PDF as `bytes`

3. **Update `app.py`** — in both the history render loop and the new-question block,
   add after the answer and dataframe:
   ```python
   pdf_bytes = ui_utils.export_answer_as_pdf(
       question=item["question"],
       answer=item["answer"],
       fig=item["fig"],
       sql=item["final_sql"],
   )
   st.download_button(
       label="⬇️ Download as PDF",
       data=pdf_bytes,
       file_name="answer.pdf",
       mime="application/pdf",
       key=f"pdf_{i}",
   )
   ```

### Acceptance criteria
- "Download as PDF" button appears below every answer in the chat
- Downloaded PDF contains the question, answer, chart (if present), and SQL
- Button works for both new answers and history items
- App does not break if `reportlab` is missing (graceful import guard)

---

## Feature 6 — Business Glossary ✅ Done

### What
Add a `business_glossary/default.md` file with domain terms (activity types,
locations, Garmin metrics) injected into prompts as `{business_glossary}`.
Editable at runtime via the Config page.

### Why
Helps the LLM interpret ambiguous user questions like "trail runs", "Hamburg
sessions", "easy runs", "Z2" etc. without needing to hardcode them in prompts.

### Files to change
- `business_glossary/default.md` — **new file** (domain content)
- `business_glossary/user/` — **new directory** (created on first save, gitignored)
- `src/business_glossary_manager.py` — **new file** (load/save/revert/is_modified)
- `src/core.py` — load glossary at startup, expose as `BUSINESS_GLOSSARY`
- `src/prompt_manager.py` — add `{business_glossary}` to `render()` injection
- `prompts/generate_sql.md` — add `{business_glossary}` placeholder
- `prompts/formulate_answer.md` — add `{business_glossary}` placeholder
- `pages/config.py` — add Business Glossary editor section

### Steps

1. **Create `business_glossary/default.md`** with running-specific terms:
   - Activity types: Running, Trail Running, Indoor Running, Race, Long Run
   - Locations: Hamburg, Gremersdorf, Kungälv
   - Garmin metrics: HR zones, TSS, NP, GAP, cadence, vertical oscillation
   - Common user phrasing: "easy run" = Avg HR < 140, "race" = Title contains "Race"

2. **Create `src/business_glossary_manager.py`** following the exact same pattern
   as `src/data_dictionary_manager.py`:
   ```python
   GLOSSARY_DIR = "business_glossary"
   USER_DIR = os.path.join(GLOSSARY_DIR, "user")
   DEFAULT_FILE = os.path.join(GLOSSARY_DIR, "default.md")
   USER_FILE = os.path.join(USER_DIR, "default.md")

   def load() -> str: ...        # returns active text (user override or default)
   def save_user(text: str): ... # writes to user/default.md
   def revert(): ...             # deletes user/default.md
   def is_modified() -> bool: ...
   ```

3. **Update `src/core.py`**:
   - Add `from . import business_glossary_manager`
   - Add `BUSINESS_GLOSSARY = business_glossary_manager.load()` at module level
     (next to `SCHEMA_DESCRIPTION`)

4. **Update `src/prompt_manager.py` `render()`**:
   - Inject `{business_glossary}` as a shared block (like `{sql_guidelines}`)
   - Accept `business_glossary` as a kwarg or inject from `prompts` dict

5. **Update prompts**:
   - `prompts/generate_sql.md` — add `{business_glossary}` section
   - `prompts/formulate_answer.md` — add `{business_glossary}` section
   - Update `PROMPT_META` in `prompt_manager.py` to document the new placeholder

6. **Add Business Glossary editor to `pages/config.py`**:
   - New section `st.header("📖 Business Glossary")`
   - `st.text_area` pre-filled with current glossary text
   - Save / Revert buttons with Modified/Original badge
   - On save: write via `business_glossary_manager.save_user()` and update
     `st.session_state`

7. **Update `.gitignore`** to exclude `business_glossary/user/`.

### Acceptance criteria
- `{business_glossary}` is injected into SQL generation and answer prompts
- Editing the glossary on Config page takes effect immediately
- Revert restores the default
- `business_glossary/user/` is gitignored

---

## Feature 7 — Dedicated `src/query_manager.py` Module ✅ Done

### What
The current `src/query_manager.py` exists but is a thin wrapper. Ensure it fully
follows the same load/save/revert/override pattern as `prompt_manager.py`,
including `QUERY_META` with descriptions and `is_modified()` per query.

### Why
Consistency across all manager modules; enables the Config page to show
Modified/Original badges per query (already shown for prompts).

### Files to check / change
- `src/query_manager.py` — audit and complete if needed

### Steps

1. **Read `src/query_manager.py`** fully and compare to `src/prompt_manager.py`.

2. **Ensure the following exist**:
   - `QUERY_NAMES` list
   - `QUERY_META` dict with `title` and `description` per query
   - `load_all() -> dict[str, str]`
   - `get(name) -> str`
   - `save_user(name, text)`
   - `revert(name)`
   - `is_modified(name) -> bool`
   - `original_text(name) -> str`

3. **Add any missing pieces** by following the pattern in `src/prompt_manager.py`.

4. **Update `pages/config.py` query editor section** if any API calls need updating.

### Acceptance criteria
- All 5 queries have a `QUERY_META` entry with title and description
- Modified/Original badge appears correctly in the Config page
- Save / Revert works correctly for all 5 queries

---

## Feature 8 — SQL Browser Page ✅ Done

### What
Add a new page `pages/sql_browser.py` where users can run arbitrary DuckDB SQL
directly against `data.parquet`.

### Why
Power users and developers benefit from direct SQL access for ad-hoc exploration
without involving the LLM.

### Files to change
- `pages/sql_browser.py` — **new file**
- `app.py` — register the new page in navigation (if using `st.navigation`)

### Steps

1. **Create `pages/sql_browser.py`** with:

   **Sidebar:**
   - Schema viewer: `core.get_schema_df()` displayed as a dataframe
   - 4 hardcoded sample queries as clickable buttons to prefill the editor:
     ```sql
     SELECT * FROM data LIMIT 10
     SELECT COUNT(*) AS total_runs FROM data
     SELECT DISTINCT "Activity Type" FROM data ORDER BY 1
     SELECT strftime(Date, '%Y-%m') AS month, COUNT(*) AS runs FROM data GROUP BY 1 ORDER BY 1
     ```

   **Main area:**
   - `st.text_area` for SQL input, pre-filled from `st.session_state["sql_browser_query"]`
   - "Run Query" button
   - On run: call `core.run_query(sql)` inside try/except
     - On success: show row × column badge, `st.dataframe(df)`, CSV download button
     - On error: `st.error(str(e))`

2. **Register the page** in `app.py` (or let Streamlit's file-based routing pick it up
   automatically from `pages/`).
   
   If using `st.navigation`, add:
   ```python
   st.Page("pages/sql_browser.py", title="SQL Browser", icon="🔍")
   ```
   Otherwise the file in `pages/` is auto-discovered.

3. **Add password gate** (same `check_password()` pattern as other pages).

### Acceptance criteria
- `/sql_browser` page is accessible from the sidebar navigation
- Running valid SQL returns a dataframe and a CSV download button
- Running invalid SQL shows an inline error message
- Schema viewer shows all columns and types
- Sample queries prefill the editor when clicked

---

## Feature 9 — Log Viewer Page ✅ Done

### What
Add a new page `pages/log.py` that displays the contents of `app.log` with
level filtering, a refresh button, and a clear button.

### Why
Operational visibility without SSH access — useful for debugging LLM or SQL
failures in production.

### Files to change
- `pages/log.py` — **new file**
- `app.py` — register in navigation (same as Feature 8)

### Steps

1. **Update logging level in `src/core.py`** from `WARNING` to `INFO`
   so successful SQL executions are also recorded (matching kn-project behaviour).

2. **Create `pages/log.py`**:

   **Controls (top of page):**
   - Multiselect for log levels: `["INFO", "WARNING", "ERROR"]` (all selected by default)
   - "🔄 Refresh" button — reruns the page
   - "🗑️ Clear log" button — truncates `app.log`

   **Log display:**
   - Read `app.log` lines from disk
   - Group multi-line entries (e.g. SQL blocks, tracebacks) — a new entry starts
     when a line matches the timestamp pattern `^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}`
   - Filter grouped entries by selected levels
   - Show matching count vs. total count
   - Display each entry in reverse order (most recent first) using `st.code()` or
     `st.text()`

3. **Register the page** in `app.py` navigation.

4. **Add password gate**.

### Acceptance criteria
- `/log` page shows `app.log` contents
- Level filter works correctly (INFO / WARNING / ERROR)
- Most recent entries appear at the top
- "Refresh" reloads the log without losing filter state
- "Clear log" empties the file and refreshes the view
- Multi-line log entries (SQL, tracebacks) are grouped as single entries

---

## Feature 10 — Follow-up Suggestions ⬜ Pending

### What
After the first answer in a conversation, generate and display 5 AI-generated
follow-up question suggestions as clickable buttons below the result. Clicking
one prefills the chat input.

### Why
Reduces the blank-slate problem for users who don't know what to ask next.

### Files to change
- `prompts/suggest_followups.md` — **new file**
- `src/prompt_manager.py` — add `suggest_followups` to `PROMPT_NAMES` and `PROMPT_META`
- `src/core.py` — add `generate_followup_suggestions(prompt) -> list[str]`
- `app.py` — call and render suggestions after first answer; add toggle state
- `pages/config.py` — add Follow-up Suggestions toggle section

### Steps

1. **Create `prompts/suggest_followups.md`**:
   - Instruct the LLM to generate exactly 5 short follow-up questions
   - Each should be a plausible next question given the question and result
   - Output format: one question per line, no numbering, no bullet points
   - Placeholders: `{question}`, `{result_str}`

2. **Register in `src/prompt_manager.py`**:
   - Add `"suggest_followups"` to `PROMPT_NAMES`
   - Add entry to `PROMPT_META` with placeholders `{question}` and `{result_str}`

3. **Add `generate_followup_suggestions()` to `src/core.py`**:
   ```python
   def generate_followup_suggestions(prompt: str, model: str = MODEL) -> list[str]:
       # Call LLM at temperature=0.3
       # Parse response: one suggestion per non-empty line
       # Strip leading numbering ("1. ", "- ", etc.)
       # Return up to 5 suggestions
       # Return [] on any error
   ```

4. **Update `app.py`**:
   - Add to session state init: `st.session_state.suggestions = []`
   - Add to session state init: `st.session_state.show_suggestions = True`
     (toggled from Config page)
   - After the **first** answer in a conversation (i.e. `len(history) == 0` before
     appending), if `show_suggestions` is True:
     - Call `generate_followup_suggestions(rendered_prompt, model=...)`
     - Store result in `st.session_state.suggestions`
   - In the history render loop, after the most recent answer (index == last):
     - If `st.session_state.suggestions` is non-empty, render as buttons:
       ```python
       st.markdown("**💡 Follow-up suggestions:**")
       for i, s in enumerate(st.session_state.suggestions):
           if st.button(s, key=f"suggestion_{i}"):
               st.session_state.prompt_prefill = s
               st.session_state.suggestions = []
               st.rerun()
       ```
   - On any new question submission: `st.session_state.suggestions = []`
   - On "Clear conversation": `st.session_state.suggestions = []`

5. **Add toggle to `pages/config.py`**:
   - New section `st.header("💡 Follow-up Suggestions")`
   - `st.toggle("Enable follow-up suggestions", value=True)` stored in
     `st.session_state.show_suggestions`

### Acceptance criteria
- Suggestions appear below the first answer only
- Each suggestion is a clickable button that prefills the chat input
- Suggestions disappear when any new question is submitted
- Toggle on Config page enables/disables the feature
- Feature works correctly when suggestions are disabled (no LLM call made)
- Errors in suggestion generation are silently swallowed (never break the main flow)

---

## Feature 11 — Chat Mode (Intent Classification) ⬜ Pending

### What
Add an optional "Chat Mode" toggle. When on, follow-up questions (e.g. "why is
that?", "what does this mean?") are answered conversationally without re-running
a SQL query. The LLM classifies each question as `NEW_QUERY`, `FOLLOWUP`, or
`UNCLEAR`.

### Why
Not every follow-up needs a database round-trip. Conversational answers feel
more natural for explanatory questions.

### Files to change
- `prompts/chat_intent.md` — **new file**
- `prompts/chat_followup.md` — **new file**
- `prompts/chat_general.md` — **new file**
- `src/prompt_manager.py` — add 3 new prompt entries
- `src/core.py` — add `classify_intent()` and `formulate_followup_answer()`
- `app.py` — add Chat Mode branching logic
- `pages/config.py` — add Chat Mode toggle section

### Steps

1. **Create `prompts/chat_intent.md`**:
   - Instruct LLM to classify the question as exactly `NEW_QUERY`, `FOLLOWUP`,
     or `UNCLEAR`
   - Provide context: `{question}`, `{last_question}`, `{last_result_preview}`,
     `{history_section}`
   - Guidance: classify as `FOLLOWUP` only if the question clearly references or
     builds on the previous result; default to `NEW_QUERY` when uncertain

2. **Create `prompts/chat_followup.md`**:
   - Conversational tone (no structured Facts/Summary/Analysis sections)
   - Provide context: `{question}`, `{last_question}`, `{last_result}`,
     `{history_section}`, `{business_glossary}` (if implemented)
   - Instruct: answer without running new SQL; use only the data already returned

3. **Create `prompts/chat_general.md`**:
   - For out-of-scope questions that have no answer in the data
   - Provide context: `{question}`, `{history_section}`
   - Instruct: answer as a helpful assistant; acknowledge there is no data for this

4. **Register all three in `src/prompt_manager.py`**:
   - Add to `PROMPT_NAMES` (after `formulate_answer`)
   - Add to `PROMPT_META` with placeholders

5. **Add two functions to `src/core.py`**:

   ```python
   def classify_intent(prompt: str, model: str = MODEL) -> str:
       # Call LLM at temperature=0
       # Return one of: 'NEW_QUERY', 'FOLLOWUP', 'UNCLEAR'
       # Fall back to 'NEW_QUERY' on any unexpected response or error

   def formulate_followup_answer(prompt: str, model: str = MODEL) -> str:
       # Call LLM at temperature=0
       # Return the conversational response string
   ```

6. **Update `app.py`**:
   - Add to session state init: `st.session_state.chat_mode = False`
   - In the question-handling block, after the user submits a question:
     ```python
     if st.session_state.chat_mode and len(st.session_state.history) > 0:
         intent = core.classify_intent(rendered_intent_prompt, model=...)
     else:
         intent = "NEW_QUERY"
     ```
   - Branch on intent:
     - `NEW_QUERY` / `UNCLEAR` → existing full pipeline (SQL → query → answer)
     - `FOLLOWUP` → call `core.formulate_followup_answer(rendered_followup_prompt)`
       and display answer only (no SQL expander, no dataframe, no chart)
   - Store follow-up answers in history with a `is_followup=True` flag so the SQL
     expander is omitted for them

7. **Add Chat Mode toggle to `pages/config.py`**:
   - New section `st.header("🗨️ Chat Mode")`
   - `st.toggle("Enable Chat Mode", value=False)` stored in
     `st.session_state.chat_mode`
   - Status badge: `🟢 Chat Mode ON` / `⚪ Chat Mode OFF`
   - Caption explaining the behaviour

### Acceptance criteria
- Chat Mode off (default): every question runs the full pipeline (no change to current behaviour)
- Chat Mode on: follow-up questions are answered without SQL
- `classify_intent()` always returns a valid value (never raises)
- Follow-up answers in history do not show an SQL expander
- "Clear conversation" resets history; Chat Mode setting persists
- Toggle appears on Config page and takes effect immediately

---

## Feature 12 — Data Dictionary (Markdown format, inline with prompts) ✅ Done

### What
Replace the current YAML-based `data_dictionary_manager` with a Markdown-based
approach that matches the kn-project. The data dictionary uses `## column_name`
headings with `**Label:**` and `**Description:**` fields, and is injected into
prompts as `{data_dictionary}` plain text.

### Why
- The current YAML format in `ofl-running-analysis` is structurally different from
  the Markdown format used in kn-project
- Markdown is easier for non-technical editors to read and write
- Consistent injection pattern with `{sql_guidelines}` and `{business_glossary}`

### Files to change
- `data_dictionary/default.md` — **rewrite** in Markdown format (or create if absent)
- `src/data_dictionary_manager.py` — **rewrite** to plain-text load/save/revert
  (drop YAML parsing)
- `src/core.py` — update `SCHEMA_DESCRIPTION` loading
- `src/prompt_manager.py` — ensure `{data_dictionary}` is injected in `render()`
- `prompts/generate_sql.md` — add `{data_dictionary}` placeholder if not present
- `prompts/formulate_answer.md` — add `{data_dictionary}` placeholder if not present
- `pages/config.py` — simplify Data Dictionary editor (remove YAML instructions,
  use plain Markdown text area)

### Steps

1. **Create/rewrite `data_dictionary/default.md`** in Markdown format:
   ```markdown
   ## Activity Type
   **Label:** Activity Type
   **Description:** The type of activity (e.g. Running, Trail Running, Indoor Running).

   ## Date
   **Label:** Date
   **Description:** Date and time the activity was recorded (format: YYYY-MM-DD HH:MM:SS).

   ## Distance
   **Label:** Distance (km)
   **Description:** Total distance in kilometres. Stored with comma decimal separator in the
   source CSV; always use REPLACE(Distance, ',', '.') before casting.

   ## Avg HR
   **Label:** Average Heart Rate (bpm)
   **Description:** Average heart rate during the activity.

   ## Avg Pace
   **Label:** Average Pace (min/km)
   **Description:** Average pace in MM:SS format per kilometre.
   ```
   Continue for all ~30 columns in the dataset.

2. **Rewrite `src/data_dictionary_manager.py`** as a plain-text manager:
   ```python
   DICT_DIR = "data_dictionary"
   USER_DIR = os.path.join(DICT_DIR, "user")
   DEFAULT_FILE = os.path.join(DICT_DIR, "default.md")
   USER_FILE = os.path.join(USER_DIR, "default.md")

   def load() -> str:              # returns active text (user override or default)
   def save_user(text: str):       # writes text to USER_FILE
   def revert():                   # deletes USER_FILE
   def is_modified() -> bool:      # True if USER_FILE exists
   ```
   Remove all YAML parsing (`yaml` import, `yaml.dump()`, `yaml.safe_load()`).

3. **Update `src/core.py`**:
   - Change `SCHEMA_DESCRIPTION = data_dictionary_manager.get_schema_description()`
     to `DATA_DICTIONARY = data_dictionary_manager.load()`
   - Update all usages of `schema_description=SCHEMA_DESCRIPTION` in `generate_sql()`,
     `fix_sql()`, `formulate_answer()`, `generate_chart_code()` to pass
     `data_dictionary=DATA_DICTIONARY`

4. **Update `src/prompt_manager.py`**:
   - Add `{data_dictionary}` as an injected shared block in `render()`:
     ```python
     text = text.replace("{data_dictionary}", prompts.get("data_dictionary", ""))
     ```
   - The data dictionary is stored in the prompts dict under key `"data_dictionary"`
     (loaded separately from the prompt files)

5. **Update `pages/chat.py` / `app.py`** prompt-loading startup:
   - After `prompt_manager.load_all()`, inject data dictionary:
     ```python
     prompts = prompt_manager.load_all()
     prompts["data_dictionary"] = data_dictionary_manager.load()
     st.session_state["prompts"] = prompts
     ```

6. **Update `pages/config.py` Data Dictionary editor**:
   - Remove YAML instructions and `yaml.dump()` / `yaml.safe_load()` calls
   - Replace with plain `st.text_area` pre-filled with `data_dictionary_manager.load()`
   - Save calls `data_dictionary_manager.save_user(edited_text)` directly
   - On save: reload prompts dict and re-inject data dictionary into session state

7. **Update `prompts/generate_sql.md` and `prompts/formulate_answer.md`**:
   - Add `{data_dictionary}` placeholder where column context is helpful
   - Update `PROMPT_META` entries with the new placeholder

8. **Update `.gitignore`** to include `data_dictionary/user/`.

9. **Remove `yaml` dependency** from `requirements.txt` if it was added only for
   this manager and is not used elsewhere.

### Acceptance criteria
- `data_dictionary/default.md` contains human-readable descriptions for all columns
- `{data_dictionary}` is injected into SQL generation and answer prompts
- Data Dictionary editor on Config page shows Markdown (no YAML)
- Save / Revert works; Modified/Original badge is correct
- No YAML parsing anywhere in the data dictionary code path
- `data_dictionary/user/` is gitignored

---

## Implementation Order (Recommended)

```
1  → LLM Result Truncation          (standalone, immediate value)
2  → Structured Answer Format        (standalone, immediate value)
3  → Prompt Placeholder Table        (standalone, polish)
7  → query_manager.py audit          (standalone, housekeeping)
12 → Data Dictionary (Markdown)      (refactor before adding more prompts)
6  → Business Glossary               (builds on 12's pattern)
4  → ui_utils.py module              (prerequisite for 5)
5  → PDF Export                      (builds on 4)
9  → Log Viewer Page                 (standalone new page)
8  → SQL Browser Page                (standalone new page)
10 → Follow-up Suggestions           (new LLM call, new prompt)
11 → Chat Mode                       (most complex, builds on 10)
```
