# AI Data Assistant — Project Documentation

## Overview
A Python CLI and Streamlit web tool that lets the user ask natural language questions about data stored in a CSV file. The AI generates SQL, queries the data via DuckDB, renders a chart if useful, and formulates a plain-English answer.

---

## File Structure

```
ofl-running-analysis/
├── .env                  # API credentials and config (not committed)
├── .venv                 # Python virtual environment
├── requirements.txt      # Python dependencies
├── data.csv              # Source data (Garmin running activities export)
├── data.parquet          # Auto-generated from data.csv (faster queries)
├── app.py                # Streamlit web UI (main chat interface)
├── pages/
│   └── config.py         # Configuration page (model + data upload/download + prompt editing)
├── src/                  # Utility modules
│   ├── __init__.py
│   ├── core.py           # Shared logic: DuckDB, LLM calls, chart rendering
│   ├── prompt_manager.py # Prompt loading, saving, and rendering
│   └── query_assistant.py # CLI entry point
├── prompts/              # AI prompt files (Markdown format)
│   ├── sql_guidelines.md # Shared block: DuckDB SQL rules
│   ├── generate_sql.md   # SQL generation prompt
│   ├── fix_sql.md        # SQL fixing prompt
│   ├── generate_chart_code.md # Chart code generation prompt
│   ├── formulate_answer.md # Answer formulation prompt
│   └── user/             # User overrides (gitignored)
├── queries/              # Pre-defined queries (selectable from sidebar)
│   ├── default_queries/
│   │   ├── query_1.md   # Pre-defined query 1
│   │   ├── query_2.md   # Pre-defined query 2
│   │   ├── query_3.md   # Pre-defined query 3
│   │   ├── query_4.md   # Pre-defined query 4
│   │   └── query_5.md   # Pre-defined query 5
│   └── user/             # User overrides (gitignored)
├── Dockerfile            # Container image definition
├── docker-compose.yml    # Compose config for container deployment
├── .dockerignore         # Excludes local dev artifacts from Docker build context
├── deploy.sh             # One-command deploy script
├── documentation/
│   ├── DEPLOYMENT.md     # Deployment guide
│   ├── PROJECT.md        # This file
│   └── implementation_notes/
│       └── PROMPT_SYSTEM_MIGRATION.md
└── .pi/skills/           # AI coding agent skills
    └── developing-with-streamlit/
```

---

## Data
- **Source:** Garmin Connect activity export (CSV)
- **File:** `data.csv` → auto-converted to `data.parquet` on startup
- **Content:** Running activities with columns like:
  - `Activity Type`, `Date`, `Title`, `Distance`, `Calories`, `Time`
  - `Avg HR`, `Max HR`, `Avg Pace`, `Best Pace`
  - `Total Ascent`, `Total Descent`, `Avg Run Cadence`, `Max Run Cadence`
  - `Avg Stride Length`, `Avg Vertical Ratio`, `Avg Vertical Oscillation`
  - `Avg Ground Contact Time`, `Avg GAP`, `Normalized Power® (NP®)`
  - `Training Stress Score®`, `Avg Power`, `Max Power`, `Steps`
  - `Body Battery Drain`, `Decompression`, `Best Lap Time`, `Number of Laps`
  - `Moving Time`, `Elapsed Time`, `Min Elevation`, `Max Elevation`
- **Locations in data:** Hamburg (majority), Gremersdorf, Kungälv
- **Date range:** October 2023 – August 2026
- **Total runs:** 358

### CSV Quirks
- Decimal separator is `,` (e.g. `"8,76"` for distance) — handled via `TRY_CAST(REPLACE(Distance, ',', '.') AS DOUBLE)` in SQL
- `Body Battery Drain` contains values like `'-15` — handled via `sample_size=-1, ignore_errors=true` in `read_csv_auto()`

---

## Configuration

### `.env`
```
OPENAI_API_KEY=<your-key>
OPENAI_BASE_URL=https://api.mistral.ai/v1
OPENAI_MODEL=mistral-medium-latest
APP_PASSWORD=<your-password>   # If set, enables a simple password gate
```

`OPENAI_BASE_URL` must point to an OpenAI-compatible API. The app uses the Mistral API directly.
Any OpenAI-compatible provider works — just change `OPENAI_BASE_URL` and `OPENAI_MODEL` accordingly.

### Script constants (`src/core.py`)
```python
CSV_FILE = "data.csv"
PARQUET_FILE = "data.parquet"
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")  # fallback if env not set
```

---

## Setup

```bash
cd ofl-running-analysis
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### `requirements.txt`
```
openai
duckdb
pandas
python-dotenv
matplotlib
streamlit
```

> **Note:** Python 3.10+ syntax (`X | Y` type unions) is not used — the code is compatible with Python 3.9+.

---

## Usage

### Streamlit web UI
```bash
cd ofl-running-analysis
source .venv/bin/activate
streamlit run app.py
```
Opens in the browser at `http://localhost:8501`. Supports:
- Chat-style interface with full conversation history
- SQL display, plain-English answer, data table, and chart per question
- Schema viewer in the sidebar
- Prompt history (persisted to `prompt_history.json`)
- Pre-defined queries selector in the sidebar
- Toggle to enable/disable automatic chart generation
- Optional password gate via `APP_PASSWORD` env var
- Clear conversation button

### Configuration Page
Access via sidebar navigation → **Config** page. Provides:
- **Model selector** — fetches available models live from the configured provider
- **Data upload** — upload Garmin CSV to merge new activities (duplicates skipped)
- **Data download** — export current dataset as CSV
- **Prompt editor** — edit all AI prompts at runtime
- **Query editor** — edit all pre-defined queries at runtime

### Pre-defined Queries
The app includes 5 pre-defined queries that users can select from the sidebar. These appear as buttons showing the query text, and clicking one pre-fills the chat input. Queries can be edited on the Config page, with user overrides saved to `queries/user/`. The original defaults in `queries/default_queries/` are never modified.

### CLI — Interactive mode
```bash
python -m src.query_assistant
```
Type questions at the prompt. Exit with `/exit`, `exit`, or `quit`.

### CLI — Single question mode
```bash
python -m src.query_assistant "how many runs have i done"
python -m src.query_assistant "show my total distance per month"
python -m src.query_assistant "list the runs grouped by location"
```

---

## Pipeline (Step by Step)

```
User Question
     │
     ▼
1. ensure_parquet()            → converts data.csv → data.parquet if CSV is newer
     │
     ▼
2. get_schema()                → reads column names/types + 5 sample rows from Parquet
     │
     ▼
3. generate_sql()              → LLM generates DuckDB SQL (temperature=0)
     │
     ▼
4. run_query_with_retries()    → DuckDB executes SQL on data.parquet → DataFrame
     │  (on error)               calls fix_sql() → LLM fixes broken SQL, retries up to 3×
     │
     ▼
5. formulate_answer()          → LLM writes plain-English answer (temperature=0)
     │
     ▼
6. generate_chart_code()       → LLM decides if chart is useful, returns matplotlib code
     │                            (or None if not worth visualising)
     ▼
   render_chart()              → patches code, execs with df in scope, returns Figure
                                 - User question injected as bold suptitle
                                 - Code patched before exec to fix known LLM mistakes
                                 - Web UI: renders via st.pyplot()
                                 - CLI: calls plt.show() for a pop-up window
```

All LLM calls pass the currently selected model — switchable at runtime via the Config page.

---

## Data Management

The app supports uploading and downloading CSV data via the Config page.

### Upload Feature
- **Merge mode**: New activities are added, duplicates are skipped
- **Duplicate detection**: Uses `Date + Title + Activity Type` as unique key
- **Column validation**: Ensures uploaded CSV matches existing structure
- **Date normalization**: Handles different date formats automatically
- **Whitespace handling**: Strips extra spaces from string columns

### Download Feature
- Exports current `data.csv` file
- One-click download via browser

---

## Prompt System

All LLM prompts have been externalized from the code into Markdown files for runtime editing.

### Architecture
- **Prompt files**: Stored in `prompts/` as `.md` files with `{placeholder}` syntax
- **Shared blocks**: Reusable text (e.g., `sql_guidelines.md`) injected into other prompts
- **User overrides**: Saved to `prompts/user/` (gitignored), originals never modified
- **Prompt manager**: `src/prompt_manager.py` handles loading, rendering, saving, and reverting

### Available Prompts

| Prompt | Purpose | Key Placeholders |
|--------|---------|------------------|
| `sql_guidelines` | DuckDB SQL rules (shared block) | None |
| `generate_sql` | SQL query generation | `{question}`, `{schema}`, `{sql_guidelines}`, `{history_section}` |
| `fix_sql` | SQL error fixing | `{sql}`, `{error}`, `{schema}`, `{sql_guidelines}` |
| `generate_chart_code` | Chart code generation | `{question}`, `{result_str}` |
| `formulate_answer` | Answer formulation | `{question}`, `{result_str}`, `{history_section}` |

### Usage
1. Navigate to the **Config** page via sidebar
2. Select your AI model from the dropdown
3. Expand any prompt section to edit its text
4. Click **Save** to apply changes (immediate effect)
5. Click **Revert** to restore the original

---

## Design Decisions

## Design Decisions

| Decision | Reason |
|----------|--------|
| **DuckDB** | Reads Parquet/CSV directly, no DB setup, fast on large files |
| **Parquet over CSV** | Binary columnar format: 3–10x faster queries, smaller file, typed schema |
| **Auto CSV→Parquet conversion** | Compares file mtimes — regenerates only when `data.csv` is newer |
| **Schema passed to LLM** | Gives column names, types and sample rows → better SQL generation |
| **`src/core.py` shared module** | All LLM/DuckDB/chart logic lives here; both CLI and web UI import it — no duplication |
| **Two LLM calls (SQL + answer)** | Clean separation of concerns |
| **`temperature=0` everywhere** | Fully deterministic output across all LLM calls |
| **SQL retry loop (3 attempts)** | LLM receives broken SQL + error and fixes it automatically |
| **Model selector** | Available models fetched live from the provider API; non-chat models (embeddings, rerankers, TTS, etc.) filtered out; selection persisted in session state and passed to all LLM calls |
| **Chart via `exec()`** | LLM generates matplotlib code, executed in-process with `df`, `plt`, `pd`, `np`, `FuncFormatter`, and `safe_pace_to_seconds` in scope |
| **Chart code patching** | Generated code is patched before exec to fix known LLM mistakes (e.g. `set_formatter` → `set_major_formatter`, fragile pace parsers replaced with `safe_pace_to_seconds`) |
| **Datetime → string conversion** | datetime64 columns converted to strings before charting so LLM `.str` accessor calls don't fail |
| **Matplotlib `Agg` backend** | Set in `app.py` before any pyplot import so chart rendering is headless (no display required); figures returned as objects and rendered via `st.pyplot()` |
| **Emoji stripping** | String columns stripped of non-ASCII before charting to avoid matplotlib font warnings |
| **Question as suptitle** | User question injected as bold title above chart so context is always visible |
| **Password gate** | Optional `APP_PASSWORD` env var enables a simple login screen in the web UI; skipped if not set (suitable for local dev) |
| **File logging** | Warnings and errors written to `app.log` with timestamps for debugging |
| **CLI arg support** | `python -m src.query_assistant "question"` for scripting/testing |
| **Python 3.9 compatibility** | `X \| Y` union type hints replaced with `Optional[X]` from `typing` |

---

## Known Issues / Future Work
- [x] ~~Add Streamlit web UI (charts embedded in browser)~~
- [x] ~~Add conversation history (multi-turn questions)~~
- [x] ~~Model selector for switching LLMs at runtime~~
- [ ] Save chart images to disk as an option
- [ ] Support multiple CSV/data files
- [ ] Handle very large DataFrames in answer formulation (token limit)
