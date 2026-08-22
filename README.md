# 🏃 OFL Running Analysis

A personal AI-powered data assistant for Garmin running data. Ask questions in plain English — the app generates SQL, queries your data with DuckDB, writes a clear answer, and renders a chart automatically.

**Live demo:** [ofl-running.duckdns.org](https://ofl-running.duckdns.org) *(password protected)*

---

## Features

- 💬 **Chat interface** — ask questions in plain English about your running history
- 🤖 **LLM-powered SQL** — automatically generates and self-corrects DuckDB SQL queries
- 📊 **Auto charts** — matplotlib charts generated and rendered per answer
- 🔀 **Model selector** — switch between available LLMs at runtime via the Config page
- ✏️ **Runtime-editable prompts** — edit all AI prompts via the Config page without code changes
- 📥 **Data upload** — upload Garmin CSV files to merge new activities (duplicates skipped)
- 📤 **Data download** — download current dataset as CSV
- 🕓 **Conversation history** — multi-turn questions with full context
- 📋 **Prompt history** — persisted across sessions, re-run with one click
- 🔒 **Password gate** — optional login screen for public deployments

---

## Stack

| Layer | Technology |
|---|---|
| UI | [Streamlit](https://streamlit.io) |
| Query engine | [DuckDB](https://duckdb.org) |
| LLM | OpenAI-compatible API (Mistral, Claude, GPT, …) |
| Charts | matplotlib |
| Data | Garmin Connect CSV export |

---

## Quick Start

**Prerequisites:** Python 3.9+, an OpenAI-compatible API key

```bash
git clone https://github.com/floerio/ofl-running-analysis.git
cd ofl-running-analysis

python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file:
```env
OPENAI_API_KEY=<your-key>
OPENAI_BASE_URL=https://api.mistral.ai/v1
OPENAI_MODEL=mistral-medium-latest
APP_PASSWORD=<optional-password>
```

Launch the web UI:
```bash
streamlit run app.py
```

Or use the CLI:
```bash
python -m src.query_assistant "how many runs have I done?"
python -m src.query_assistant "show my total distance per month"
```

---

## How It Works

```
User Question
     │
     ▼
1. ensure_parquet()       CSV → Parquet (only when data.csv is newer)
     │
     ▼
2. get_schema()           Column names, types + 5 sample rows → passed to LLM
     │
     ▼
3. generate_sql()         LLM generates DuckDB SQL (temperature=0)
     │
     ▼
4. run_query()            DuckDB executes SQL → DataFrame
     │  on error          fix_sql() → LLM self-corrects, retries up to 3×
     │
     ▼
5. formulate_answer()     LLM writes a plain-English answer
     │
     ▼
6. generate_chart_code()  LLM decides if a chart is useful, returns matplotlib code
     │
     ▼
   render_chart()         Code patched + executed, Figure returned
```

---

## Data

Garmin Connect running export with 358 activities (Oct 2023 – Aug 2026), including:
distance, pace, heart rate, cadence, power, elevation, stride length, and more.

Locations: Hamburg, Gremersdorf, Kungälv.

---

## Configuration

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | API key for your LLM provider |
| `OPENAI_BASE_URL` | Provider base URL (e.g. `https://api.mistral.ai/v1`) |
| `OPENAI_MODEL` | Default model (e.g. `mistral-medium-latest`) |
| `APP_PASSWORD` | Optional — enables password gate in the web UI |

Any OpenAI-compatible provider works. The model selector on the Config page fetches available models live from the configured `OPENAI_BASE_URL`.

### Data Management
- **Upload**: Merge new Garmin CSV data via the Config page. Duplicates (based on Date + Title + Activity Type) are automatically skipped.
- **Download**: Export your current dataset as CSV from the Config page.

### Prompt System
All LLM prompts are stored as Markdown files in `prompts/` and can be edited at runtime via the Config page. User overrides are saved to `prompts/user/` (gitignored).

---

## Deployment

The app is containerized and deployed to a Hetzner VPS via GitHub Container Registry and Traefik.

```bash
./deploy.sh   # build → push to GHCR → pull & restart on VPS
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for the full setup guide.

---

## Project Structure

```
ofl-running-analysis/
├── app.py                # Streamlit web UI (main chat interface)
├── pages/
│   └── config.py         # Configuration page (model + prompt editing)
├── src/                  # Utility modules
│   ├── __init__.py
│   ├── core.py           # Shared logic: DuckDB, LLM calls, chart rendering
│   ├── prompt_manager.py # Prompt loading, saving, and rendering
│   └── query_assistant.py # CLI entry point
├── prompts/              # AI prompt files (Markdown format)
│   ├── sql_guidelines.md
│   ├── generate_sql.md
│   ├── fix_sql.md
│   ├── generate_chart_code.md
│   └── formulate_answer.md
│   └── user/             # User overrides (gitignored)
├── queries/              # Pre-defined queries
│   ├── default_queries/
│   │   ├── query_1.md
│   │   ├── query_2.md
│   │   ├── query_3.md
│   │   ├── query_4.md
│   │   └── query_5.md
│   └── user/             # User overrides (gitignored)
├── data.csv              # Garmin running export
├── requirements.txt      # Python dependencies
├── Dockerfile
├── docker-compose.yml
├── deploy.sh
├── documentation/
│   ├── PROJECT.md        # Detailed project documentation
│   ├── DEPLOYMENT.md     # Deployment guide
│   └── implementation_notes/
│       └── PROMPT_SYSTEM_MIGRATION.md
└── .pi/skills/           # AI coding agent skills
    └── developing-with-streamlit/
```

---

## License

Personal project — not intended for public reuse.
