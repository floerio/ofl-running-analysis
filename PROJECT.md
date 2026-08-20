# AI Data Assistant — Project Documentation

## Overview
A Python CLI tool that lets the user ask natural language questions about data stored in a CSV file. The AI generates SQL, queries the data via DuckDB, renders a chart if useful, and formulates a plain-English answer.

---

## File Structure

```
KN_query_assistant/
├── .env                  # API credentials and config (not committed)
├── .env_example          # Example env file for onboarding
├── .venv                 # Python virtual environment
├── requirements.txt      # Python dependencies
├── data.csv              # Source data (Garmin running activities export)
├── data.parquet          # Auto-generated from data.csv (faster queries)
├── core.py               # Shared logic: DuckDB, LLM calls, chart rendering
├── app.py                # Streamlit web UI
├── query_assistant.py    # CLI entry point
├── Dockerfile            # Container image definition
├── docker-compose.yml    # Compose config for container deployment
├── DEPLOYMENT.md         # Deployment guide
└── PROJECT.md            # This file
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
OPENAI_BASE_URL=https://api.iteragpt.iteratec.de
OPENAI_MODEL=gcp/claude-sonnet-4-6
```

### Script constants (`core.py`)
```python
CSV_FILE = "data.csv"
PARQUET_FILE = "data.parquet"
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")  # fallback if env not set
```

Optional env var for the web UI:
```
APP_PASSWORD=<your-password>   # If set, enables a simple password gate
```

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python query_assistant.py
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

---

## Usage

### Streamlit web UI
```bash
streamlit run app.py
```
Opens in the browser at `http://localhost:8501`. Supports:
- Chat-style interface with full conversation history
- SQL display, plain-English answer, data table, and chart per question
- Schema viewer in the sidebar
- Optional password gate via `APP_PASSWORD` env var
- Clear conversation button

### CLI — Interactive mode
```bash
python query_assistant.py
```
Type questions at the prompt. Exit with `/exit`, `exit`, or `quit`.

### CLI — Single question mode
```bash
python query_assistant.py "how many runs have i done"
python query_assistant.py "show my total distance per month"
python query_assistant.py "list the runs grouped by location"
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

---

## Design Decisions

| Decision | Reason |
|----------|--------|
| **DuckDB** | Reads Parquet/CSV directly, no DB setup, fast on large files |
| **Parquet over CSV** | Binary columnar format: 3–10x faster queries, smaller file, typed schema |
| **Auto CSV→Parquet conversion** | Compares file mtimes — regenerates only when `data.csv` is newer |
| **Schema passed to LLM** | Gives column names, types and sample rows → better SQL generation |
| **`core.py` shared module** | All LLM/DuckDB/chart logic lives here; both CLI and web UI import it — no duplication |
| **Two LLM calls (SQL + answer)** | Clean separation of concerns |
| **`temperature=0` everywhere** | Fully deterministic output across all LLM calls |
| **SQL retry loop (3 attempts)** | LLM receives broken SQL + error and fixes it automatically |
| **Chart via `exec()`** | LLM generates matplotlib code, executed in-process with `df`, `plt`, `pd`, `np`, `FuncFormatter`, and `safe_pace_to_seconds` in scope |
| **Chart code patching** | Generated code is patched before exec to fix known LLM mistakes (e.g. `set_formatter` → `set_major_formatter`, fragile pace parsers replaced with `safe_pace_to_seconds`) |
| **Matplotlib `Agg` backend** | Set in `app.py` before any pyplot import so chart rendering is headless (no display required); figures returned as objects and rendered via `st.pyplot()` |
| **Emoji stripping** | String columns stripped of non-ASCII before charting to avoid matplotlib font warnings |
| **Question as suptitle** | User question injected as bold title above chart so context is always visible |
| **Password gate** | Optional `APP_PASSWORD` env var enables a simple login screen in the web UI; skipped if not set (suitable for local dev) |
| **File logging** | Warnings and errors written to `app.log` with timestamps for debugging |
| **CLI arg support** | `python query_assistant.py "question"` for scripting/testing |

---

## Known Issues / Future Work
- [x] ~~Add Streamlit web UI (charts embedded in browser)~~
- [ ] Save chart images to disk as an option
- [ ] Support multiple CSV/data files
- [ ] Add conversation history (multi-turn questions)
- [ ] Handle very large DataFrames in answer formulation (token limit)
