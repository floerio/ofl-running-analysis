"""Shared logic for the AI Data Assistant.

Used by both the CLI (query_assistant.py) and the web app (app.py).
Keeps all OpenAI/DuckDB/matplotlib logic in one place.
"""
import os
import re
import logging
from typing import Optional
import duckdb
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    filename="app.log",
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

CSV_FILE = "data.csv"
PARQUET_FILE = "data.parquet"
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# Models that are NOT chat/completion models — excluded from the selector
_EXCLUDED_MODEL_KEYWORDS = [
    "embedding", "embed", "rerank", "tts", "whisper", "image", "vision",
    "bge", "ada", "realtime",
]


def get_available_models() -> list[str]:
    """Fetch available chat models from the provider, excluding non-chat models."""
    try:
        models = client.models.list()
        result = []
        for m in sorted(models, key=lambda x: x.id):
            mid = m.id.lower()
            if any(kw in mid for kw in _EXCLUDED_MODEL_KEYWORDS):
                continue
            result.append(m.id)
        return result
    except Exception:
        return [MODEL]  # fallback to env-configured model


# ── Step 0: Convert CSV to Parquet if needed ─────────────────────────────────
def ensure_parquet(csv_file: str = CSV_FILE, parquet_file: str = PARQUET_FILE) -> str:
    csv_mtime = os.path.getmtime(csv_file)
    parquet_exists = os.path.exists(parquet_file)
    parquet_mtime = os.path.getmtime(parquet_file) if parquet_exists else 0

    if not parquet_exists or csv_mtime > parquet_mtime:
        con = duckdb.connect()
        con.execute(
            f"COPY (SELECT * FROM read_csv_auto('{csv_file}', sample_size=-1, ignore_errors=true)) "
            f"TO '{parquet_file}' (FORMAT PARQUET)"
        )
        return f"Converted {csv_file} → {parquet_file}"
    return f"Using existing {parquet_file}"


# ── Step 1: Inspect Parquet schema for the LLM ──────────────────────────────
def get_schema(parquet_file: str = PARQUET_FILE) -> str:
    con = duckdb.connect()
    con.execute(f"CREATE VIEW data AS SELECT * FROM read_parquet('{parquet_file}')")
    col_info_df = con.execute("DESCRIBE data").df()
    col_info = ", ".join(f"{row['column_name']} ({row['column_type']})" for _, row in col_info_df.iterrows())
    sample = con.execute("SELECT * FROM data LIMIT 5").df().to_string(index=False)
    return f"Columns: {col_info}\n\nSample rows:\n{sample}"


def get_schema_df(parquet_file: str = PARQUET_FILE) -> pd.DataFrame:
    """Returns the schema as a clean DataFrame with columns: Column, Type."""
    con = duckdb.connect()
    con.execute(f"CREATE VIEW data AS SELECT * FROM read_parquet('{parquet_file}')")
    df = con.execute("DESCRIBE data").df()[["column_name", "column_type"]]
    df.columns = ["Column", "Type"]
    return df


# ── Shared SQL writing guidelines to avoid common LLM mistakes ──────────────
SQL_GUIDELINES = """Important DuckDB SQL rules to follow:
- Many numeric-looking columns are stored as VARCHAR because the source data is messy \
(decimal commas like "8,76", placeholder values like "--" for missing data, stray characters). \
Always convert them with TRY_CAST(REPLACE(column, ',', '.') AS DOUBLE), NEVER plain CAST — \
CAST will error out on non-numeric values, TRY_CAST returns NULL instead.
- Never nest a window function (OVER (...)) inside an aggregate function call, \
e.g. SUM((x - AVG(x) OVER()) * y) is INVALID SQL. If you need a value computed via a window \
function as part of an aggregation (e.g. computing a correlation/regression manually), \
first compute the window function result in a CTE or subquery, then aggregate over that \
result in an outer query. Alternatively, prefer DuckDB's built-in aggregate statistics \
functions when they fit (e.g. corr(y, x), regr_slope(y, x), regr_intercept(y, x), stddev, \
variance) instead of manually reimplementing them.
"""


# ── Step 2: LLM generates SQL ────────────────────────────────────────────────
def _format_history_for_prompt(history: list[dict]) -> str:
    """Format conversation history into a readable context block for the LLM."""
    if not history:
        return ""
    lines = ["Previous questions and their SQL queries for context:"]
    for i, item in enumerate(history, 1):
        lines.append(f"\n[{i}] Question: {item['question']}")
        lines.append(f"    SQL: {item['final_sql']}")
        if not item['df'].empty:
            lines.append(f"    Result preview: {item['df'].head(3).to_string(index=False)}")
    return "\n".join(lines)


def generate_sql(question: str, schema: str, history: Optional[list] = None, model: str = MODEL) -> str:
    history_block = _format_history_for_prompt(history or [])
    history_section = f"""
{history_block}

The user may refer to previous questions (e.g. "split that by month", "now filter by year").
Use the context above to resolve what "that" or "this" refers to.
""" if history_block else ""

    prompt = f"""You are a SQL expert. The user has a CSV file loaded into DuckDB as a table called 'data'.

Schema:
{schema}

{SQL_GUIDELINES}{history_section}
Write a single DuckDB SQL query to answer this question. Return ONLY the SQL, no explanation.

Question: {question}"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    sql = response.choices[0].message.content.strip()
    sql = sql.removeprefix("```sql").removeprefix("```").removesuffix("```").strip()
    return sql


# ── Step 3: Run SQL with DuckDB ──────────────────────────────────────────────
def run_query(sql: str, parquet_file: str = PARQUET_FILE) -> pd.DataFrame:
    con = duckdb.connect()
    con.execute(f"CREATE VIEW data AS SELECT * FROM read_parquet('{parquet_file}')")
    return con.execute(sql).df()


# ── Step 3b: LLM fixes broken SQL ────────────────────────────────────────────
def fix_sql(sql: str, error: str, schema: str, model: str = MODEL) -> str:
    prompt = f"""You are a SQL expert using DuckDB. The following SQL query failed with an error.

Schema:
{schema}

{SQL_GUIDELINES}
Failed SQL:
{sql}

Error:
{error}

Fix the SQL query, following the rules above. Return ONLY the corrected SQL, no explanation."""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    fixed = response.choices[0].message.content.strip()
    fixed = fixed.removeprefix("```sql").removeprefix("```").removesuffix("```").strip()
    return fixed


def run_query_with_retries(sql: str, schema: str, parquet_file: str = PARQUET_FILE, max_retries: int = 3, model: str = MODEL):
    """Runs the SQL, asking the LLM to fix it on failure. Returns (df, final_sql, attempts_log)."""
    attempts_log = []
    for attempt in range(1, max_retries + 1):
        try:
            df = run_query(sql, parquet_file)
            return df, sql, attempts_log
        except Exception as e:
            attempts_log.append(f"Attempt {attempt}/{max_retries} failed: {e}")
            logger.warning("SQL error (attempt %d/%d): %s\nSQL:\n%s", attempt, max_retries, e, sql)
            if attempt < max_retries:
                sql = fix_sql(sql, str(e), schema, model=model)
            else:
                logger.error("SQL failed after %d attempts: %s\nFinal SQL:\n%s", max_retries, e, sql)
                raise
    return None, sql, attempts_log


# ── Step 4: LLM generates chart code ─────────────────────────────────────────
def _safe_pace_to_seconds(val):
    """Convert a pace string like '6:30', '6:30.', '6.' to total seconds."""
    if pd.isna(val):
        return None
    s = str(val).strip().rstrip(".")
    parts = s.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1].rstrip("."))
        return int(float(parts[0])) * 60
    except (ValueError, IndexError):
        return None


def generate_chart_code(question: str, result_df: pd.DataFrame, model: str = MODEL) -> Optional[str]:
    """Ask the LLM if a chart makes sense. Returns cleaned Python code, or None."""
    result_str = result_df.to_string(index=False)
    prompt = f"""You are a data visualisation expert using Python and matplotlib.

The user asked: "{question}"

The query result is:
{result_str}

Decide if this data is worth visualising as a chart (e.g. time series, grouped counts, distributions → yes; single scalar values → no).

If YES: return ONLY executable Python code that:
- Uses the variable `df` (a pandas DataFrame already in memory with the columns shown above)
- Creates a clear, labelled matplotlib chart (title, axis labels, tight_layout)
- Ends with plt.show()
- Does NOT import pandas or re-create df

If NO: return exactly the word NO and nothing else."""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    code = response.choices[0].message.content.strip()
    code = code.removeprefix("```python").removeprefix("```").removesuffix("```").strip()

    if code.upper() == "NO":
        return None
    return code


def render_chart(code: str, question: str, result_df: pd.DataFrame):
    """Executes LLM-generated chart code and returns the matplotlib Figure (does NOT call plt.show()).
    Returns None on error."""
    try:
        # Fix common LLM mistakes in generated matplotlib code

        # set_formatter → set_major_formatter (bare axes)
        code = code.replace(".set_formatter(", ".set_major_formatter(")

        # xaxis.set_formatter / yaxis.set_formatter → set_major_formatter
        code = re.sub(
            r"\.(x|y)axis\.set_formatter\(",
            lambda m: f".{m.group(1)}axis.set_major_formatter(",
            code,
        )

        # Fragile pace lambda → safe_pace_to_seconds
        code = re.sub(
            r"lambda x:\s*int\(x\.split\(':'\)\[0\]\)\s*\*\s*60\s*\+\s*int\(x\.split\(':'\)\[1\][^)]*\)",
            "safe_pace_to_seconds",
            code,
        )

        # Remove plt.show() — caller decides how/whether to display the figure
        code = code.replace("plt.show()", "")

        # Pre-process DataFrame before handing it to LLM code
        df_clean = result_df.copy()

        # Convert datetime columns to string so LLM .str accessor calls work
        dt_cols = df_clean.select_dtypes(include=["datetime64[ns]", "datetimetz"]).columns
        for col in dt_cols:
            df_clean[col] = df_clean[col].astype(str)

        # Strip emojis/non-ASCII from string columns to avoid matplotlib font warnings
        str_cols = df_clean.select_dtypes(include=["object", "string"]).columns
        for col in str_cols:
            df_clean[col] = (
                df_clean[col].astype(str).str.encode("ascii", errors="ignore").str.decode("ascii").str.strip()
            )

        question_escaped = question.replace('"', '\\"')
        code += (
            f"\nplt.gcf().suptitle('Q: \"{question_escaped}\"', fontsize=13, fontweight='bold', y=1.02)"
            f"\nplt.tight_layout()"
        )

        plt.close("all")
        exec(
            code,
            {
                "df": df_clean,
                "plt": plt,
                "pd": pd,
                "FuncFormatter": FuncFormatter,
                "np": np,
                "safe_pace_to_seconds": _safe_pace_to_seconds,
            },
        )
        return plt.gcf()
    except Exception as e:
        logger.error("Chart rendering failed: %s\nCode:\n%s", e, code)
        return None


# ── Step 5: LLM formulates a nice answer ─────────────────────────────────────
def formulate_answer(question: str, result_df: pd.DataFrame, history: Optional[list] = None, model: str = MODEL) -> str:
    result_str = result_df.to_string(index=False) if not result_df.empty else "No results found."
    history_block = _format_history_for_prompt(history or [])
    history_section = f"""
{history_block}

The user may refer to previous questions. Use the context above if needed.
""" if history_block else ""

    prompt = f"""The user asked: "{question}"
{history_section}
The SQL query returned this data:
{result_str}

Write a clear, concise, well-formulated answer in plain English based on the data above."""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def answer_question(question: str, schema: str, history: Optional[list] = None, max_retries: int = 3):
    """High-level orchestration: SQL -> query -> answer -> chart.
    Returns a dict with keys: sql, df, answer, chart_code, fig (fig may be None)."""
    sql = generate_sql(question, schema, history=history)
    df, final_sql, attempts_log = run_query_with_retries(sql, schema, max_retries=max_retries)
    answer = formulate_answer(question, df, history=history)
    chart_code = generate_chart_code(question, df)
    fig = render_chart(chart_code, question, df) if chart_code else None
    return {
        "sql": sql,
        "final_sql": final_sql,
        "attempts_log": attempts_log,
        "df": df,
        "answer": answer,
        "chart_code": chart_code,
        "fig": fig,
    }
