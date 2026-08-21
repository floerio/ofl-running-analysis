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

# Import prompt_manager for prompt rendering
import prompt_manager

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

# Load prompts at module level (shared across all instances)
# This is loaded once when core.py is first imported
PROMPTS = prompt_manager.load_all()

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


# ── Data Upload Functions ──────────────────────────────────────────────────
# Unique key columns for duplicate detection (Option A: Date + Title + Activity Type)
UNIQUE_KEY_COLS = ["Date", "Title", "Activity Type"]


def validate_csv_structure(uploaded_df: pd.DataFrame, existing_df: pd.DataFrame) -> tuple[bool, str]:
    """Validate that uploaded CSV has the same column structure as existing data.
    
    Args:
        uploaded_df: DataFrame from uploaded CSV
        existing_df: DataFrame from existing parquet
        
    Returns:
        Tuple of (is_valid: bool, error_message: str)
    """
    uploaded_cols = set(uploaded_df.columns)
    existing_cols = set(existing_df.columns)
    
    # Debug logging
    logger.info(f"Uploaded CSV columns: {sorted(uploaded_cols)}")
    logger.info(f"Existing data columns: {sorted(existing_cols)}")
    
    if uploaded_cols == existing_cols:
        return True, ""
    
    missing_in_upload = existing_cols - uploaded_cols
    extra_in_upload = uploaded_cols - existing_cols
    
    error_parts = []
    if missing_in_upload:
        error_parts.append(f"Missing columns: {sorted(missing_in_upload)}")
    if extra_in_upload:
        error_parts.append(f"Extra columns: {sorted(extra_in_upload)}")
    
    return False, " | ".join(error_parts)


def merge_data(new_csv_path: str, csv_file: str = CSV_FILE, parquet_file: str = PARQUET_FILE) -> tuple[int, str]:
    """Merge new CSV data with existing data, skipping duplicates.
    
    Uses UNIQUE_KEY_COLS (Date + Title + Activity Type) to identify duplicates.
    
    Args:
        new_csv_path: Path to uploaded CSV file
        csv_file: Path to existing CSV (will be updated)
        parquet_file: Path to parquet file (will be regenerated)
        
    Returns:
        Tuple of (rows_added: int, message: str)
    """
    # Load existing data
    if not os.path.exists(parquet_file):
        # If no existing data, just copy the new file
        import shutil
        shutil.copy(new_csv_path, csv_file)
        ensure_parquet(csv_file, parquet_file)
        # Count rows in new file
        new_df = pd.read_csv(new_csv_path, on_bad_lines='skip')
        return len(new_df), f"✅ Created new dataset with {len(new_df)} activities"
    
    existing_df = pd.read_parquet(parquet_file)
    
    # Load new data
    # Use on_bad_lines='skip' to handle any problematic rows
    new_df = pd.read_csv(new_csv_path, on_bad_lines='skip')
    
    # Validate structure
    is_valid, error_msg = validate_csv_structure(new_df, existing_df)
    if not is_valid:
        return 0, f"❌ Column structure mismatch: {error_msg}"
    
    # Check for required unique key columns
    for col in UNIQUE_KEY_COLS:
        if col not in new_df.columns:
            return 0, f"❌ Missing required column for duplicate detection: {col}"
    
    # Normalize string columns: strip whitespace and convert to string
    for col in UNIQUE_KEY_COLS:
        if col in existing_df.columns:
            existing_df[col] = existing_df[col].astype(str).str.strip()
        if col in new_df.columns:
            new_df[col] = new_df[col].astype(str).str.strip()
    
    # Normalize Date column to consistent format (YYYY-MM-DD HH:MM:SS)
    # Handle various Garmin date formats
    if "Date" in existing_df.columns:
        existing_df["Date"] = pd.to_datetime(existing_df["Date"], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')
    if "Date" in new_df.columns:
        new_df["Date"] = pd.to_datetime(new_df["Date"], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # Create unique keys for both DataFrames
    existing_df["__merge_key__"] = existing_df[UNIQUE_KEY_COLS].astype(str).apply("|".join, axis=1)
    new_df["__merge_key__"] = new_df[UNIQUE_KEY_COLS].astype(str).apply("|".join, axis=1)
    
    # Find new rows (not in existing data)
    new_rows = new_df[~new_df["__merge_key__"].isin(existing_df["__merge_key__"])]
    
    if new_rows.empty:
        return 0, "ℹ️ No new activities found in uploaded file"
    
    # Merge: existing + new rows
    merged_df = pd.concat([existing_df, new_rows], ignore_index=True)
    
    # Remove temporary key column
    merged_df = merged_df.drop(columns=["__merge_key__"])
    new_df = new_df.drop(columns=["__merge_key__"])
    
    # Save merged data to CSV
    merged_df.to_csv(csv_file, index=False)
    
    # Regenerate parquet
    ensure_parquet(csv_file, parquet_file)
    
    return len(new_rows), f"✅ Added {len(new_rows)} new activities"


def save_uploaded_file(uploaded_file, save_path: str) -> str:
    """Save an uploaded Streamlit file to disk.
    
    Args:
        uploaded_file: Streamlit UploadedFile object
        save_path: Where to save the file
        
    Returns:
        Path to saved file
    """
    with open(save_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return save_path


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
# Now stored in prompts/sql_guidelines.md and loaded via prompt_manager
# Kept here for backward compatibility if needed, but no longer used
SQL_GUIDELINES = prompt_manager.original_text("sql_guidelines")


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


def call_llm(prompt: str, model: str = MODEL) -> str:
    """Call the LLM with a fully-rendered prompt string."""
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def generate_sql(question: str, schema: str, history: Optional[list] = None, model: str = MODEL, prompts: Optional[dict] = None) -> str:
    """Generate DuckDB SQL query from a user question.
    
    Args:
        question: User's question in plain English
        schema: Database schema information
        history: Optional conversation history for context
        model: LLM model to use
        prompts: Optional prompts dict (defaults to module-level PROMPTS)
    """
    if prompts is None:
        prompts = PROMPTS
    
    history_block = _format_history_for_prompt(history or [])
    history_section = f"""
{history_block}

The user may refer to previous questions (e.g. "split that by month", "now filter by year").
Use the context above to resolve what "that" or "this" refers to.
""" if history_block else ""

    rendered_prompt = prompt_manager.render(
        "generate_sql",
        prompts,
        question=question,
        schema=schema,
        sql_guidelines=prompts.get("sql_guidelines", ""),
        history_section=history_section,
    )
    
    result = call_llm(rendered_prompt, model=model)
    result = result.removeprefix("```sql").removeprefix("```").removesuffix("```").strip()
    return result


# ── Step 3: Run SQL with DuckDB ──────────────────────────────────────────────
def run_query(sql: str, parquet_file: str = PARQUET_FILE) -> pd.DataFrame:
    con = duckdb.connect()
    con.execute(f"CREATE VIEW data AS SELECT * FROM read_parquet('{parquet_file}')")
    return con.execute(sql).df()


# ── Step 3b: LLM fixes broken SQL ────────────────────────────────────────────
def fix_sql(sql: str, error: str, schema: str, model: str = MODEL, prompts: Optional[dict] = None) -> str:
    """Fix a failed SQL query using the LLM.
    
    Args:
        sql: The failed SQL query
        error: The error message from DuckDB
        schema: Database schema information
        model: LLM model to use
        prompts: Optional prompts dict (defaults to module-level PROMPTS)
    """
    if prompts is None:
        prompts = PROMPTS
    
    rendered_prompt = prompt_manager.render(
        "fix_sql",
        prompts,
        sql=sql,
        error=error,
        schema=schema,
        sql_guidelines=prompts.get("sql_guidelines", ""),
    )
    
    result = call_llm(rendered_prompt, model=model)
    result = result.removeprefix("```sql").removeprefix("```").removesuffix("```").strip()
    return result


def run_query_with_retries(sql: str, schema: str, parquet_file: str = PARQUET_FILE, max_retries: int = 3, model: str = MODEL, prompts: Optional[dict] = None):
    """Runs the SQL, asking the LLM to fix it on failure. Returns (df, final_sql, attempts_log).
    
    Args:
        sql: SQL query to execute
        schema: Database schema information
        parquet_file: Path to parquet file
        max_retries: Maximum number of retry attempts
        model: LLM model to use
        prompts: Optional prompts dict (defaults to module-level PROMPTS)
    """
    if prompts is None:
        prompts = PROMPTS
    
    attempts_log = []
    for attempt in range(1, max_retries + 1):
        try:
            df = run_query(sql, parquet_file)
            return df, sql, attempts_log
        except Exception as e:
            attempts_log.append(f"Attempt {attempt}/{max_retries} failed: {e}")
            logger.warning("SQL error (attempt %d/%d): %s\nSQL:\n%s", attempt, max_retries, e, sql)
            if attempt < max_retries:
                sql = fix_sql(sql, str(e), schema, model=model, prompts=prompts)
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


def generate_chart_code(question: str, result_df: pd.DataFrame, model: str = MODEL, prompts: Optional[dict] = None) -> Optional[str]:
    """Ask the LLM if a chart makes sense. Returns cleaned Python code, or None.
    
    Args:
        question: User's question in plain English
        result_df: The query result DataFrame
        model: LLM model to use
        prompts: Optional prompts dict (defaults to module-level PROMPTS)
    """
    if prompts is None:
        prompts = PROMPTS
    
    result_str = result_df.to_string(index=False)
    rendered_prompt = prompt_manager.render(
        "generate_chart_code",
        prompts,
        question=question,
        result_str=result_str,
    )
    
    result = call_llm(rendered_prompt, model=model)
    result = result.removeprefix("```python").removeprefix("```").removesuffix("```").strip()

    if result.upper() == "NO":
        return None
    return result


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
def formulate_answer(question: str, result_df: pd.DataFrame, history: Optional[list] = None, model: str = MODEL, prompts: Optional[dict] = None) -> str:
    """Generate a plain-English answer from query results.
    
    Args:
        question: User's question in plain English
        result_df: The query result DataFrame
        history: Optional conversation history for context
        model: LLM model to use
        prompts: Optional prompts dict (defaults to module-level PROMPTS)
    """
    if prompts is None:
        prompts = PROMPTS
    
    result_str = result_df.to_string(index=False) if not result_df.empty else "No results found."
    history_block = _format_history_for_prompt(history or [])
    history_section = f"""
{history_block}

The user may refer to previous questions. Use the context above if needed.
""" if history_block else ""

    rendered_prompt = prompt_manager.render(
        "formulate_answer",
        prompts,
        question=question,
        result_str=result_str,
        history_section=history_section,
    )
    
    return call_llm(rendered_prompt, model=model)


def answer_question(question: str, schema: str, history: Optional[list] = None, max_retries: int = 3, model: str = MODEL, prompts: Optional[dict] = None):
    """High-level orchestration: SQL -> query -> answer -> chart.
    Returns a dict with keys: sql, df, answer, chart_code, fig (fig may be None).
    
    Args:
        question: User's question in plain English
        schema: Database schema information
        history: Optional conversation history for context
        max_retries: Maximum number of retry attempts for SQL
        model: LLM model to use
        prompts: Optional prompts dict (defaults to module-level PROMPTS)
    """
    if prompts is None:
        prompts = PROMPTS
    
    sql = generate_sql(question, schema, history=history, model=model, prompts=prompts)
    df, final_sql, attempts_log = run_query_with_retries(sql, schema, max_retries=max_retries, model=model, prompts=prompts)
    answer = formulate_answer(question, df, history=history, model=model, prompts=prompts)
    chart_code = generate_chart_code(question, df, model=model, prompts=prompts)
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
