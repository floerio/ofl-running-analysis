"""Shared UI utilities for the AI Data Assistant.

Imported by both app.py and pages/config.py.
Contains: prompt history persistence, password gate, PDF export.
"""
import io
import json
import os
import re
import textwrap

import streamlit as st

PROMPT_HISTORY_FILE = "prompt_history.json"


# ── Prompt history ─────────────────────────────────────────────────────────

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
    """Add a prompt to history (deduplicates, most recent first, max 100)."""
    prompts = load_prompt_history()
    prompts = [p for p in prompts if p != prompt]
    prompts.insert(0, prompt)
    prompts = prompts[:100]
    save_prompt_history(prompts)
    st.session_state.prompt_history = prompts


# ── Password gate ──────────────────────────────────────────────────────────

def check_password() -> bool:
    """Return True if the app is open or the user is authenticated."""
    app_password = os.getenv("APP_PASSWORD")
    if not app_password:
        return True  # no password configured — open access (fine for local dev)

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


# ── PDF export ─────────────────────────────────────────────────────────────

def _md_to_flowables(md_text: str, styles: dict) -> list:
    """Convert a markdown string to a list of ReportLab flowables.

    Handles: headings (#/##/###), bold/italic inline, bullet lists (- / *),
    numbered lists, pipe tables, fenced code blocks, horizontal rules, and
    plain paragraphs.
    """
    from reportlab.platypus import HRFlowable, Paragraph, Preformatted, Spacer
    from reportlab.lib.units import cm

    def _escape(text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _inline(text: str) -> str:
        """Convert inline markdown to ReportLab XML tags.

        Backtick spans are extracted first so that any * or _ inside them
        cannot be misprocessed as bold/italic markers.
        """
        text = _escape(text)

        # Step 1: extract backtick spans into placeholders
        placeholders = []
        def _stash_code(m):
            idx = len(placeholders)
            placeholders.append(f'<font name="Courier">{m.group(1)}</font>')
            return f"\x00CODE{idx}\x00"
        text = re.sub(r"`([^`]+)`", _stash_code, text)

        # Step 2: bold/italic substitutions
        text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", text)
        text = re.sub(r"___(.+?)___",        r"<b><i>\1</i></b>", text)
        text = re.sub(r"\*\*(.+?)\*\*",      r"<b>\1</b>",        text)
        text = re.sub(r"__(.+?)__",          r"<b>\1</b>",        text)
        text = re.sub(r"\*(.+?)\*",          r"<i>\1</i>",        text)
        text = re.sub(r"_(.+?)_",            r"<i>\1</i>",        text)

        # Step 3: restore backtick spans
        for idx, snippet in enumerate(placeholders):
            text = text.replace(f"\x00CODE{idx}\x00", snippet)

        return text

    flowables = []
    lines = md_text.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]

        # Fenced code block
        if line.strip().startswith("```"):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            code = "\n".join(code_lines)
            wrapped = "\n".join(
                "\n".join(textwrap.wrap(l, width=90)) if len(l) > 90 else l
                for l in code.splitlines()
            )
            flowables.append(Preformatted(wrapped, styles["code"]))
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^[-*_]{3,}\s*$", line.strip()):
            flowables.append(HRFlowable(width="100%", thickness=0.5))
            i += 1
            continue

        # Headings
        m = re.match(r"^(#{1,3})\s+(.*)", line)
        if m:
            level = len(m.group(1))
            text = _inline(m.group(2))
            style_key = {1: "md_h1", 2: "md_h2", 3: "md_h3"}[level]
            flowables.append(Paragraph(text, styles[style_key]))
            i += 1
            continue

        # Pipe table
        if "|" in line and line.strip().startswith("|"):
            from reportlab.lib import colors as rl_colors
            from reportlab.platypus import Table, TableStyle

            table_lines = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip().startswith("|"):
                row = lines[i].strip().strip("|")
                if re.match(r"^[\s|:\-]+$", row):
                    i += 1
                    continue
                cells = [_inline(c.strip()) for c in row.split("|")]
                table_lines.append(cells)
                i += 1

            if table_lines:
                para_rows = [
                    [Paragraph(cell, styles["table_cell"]) for cell in row]
                    for row in table_lines
                ]
                tbl = Table(para_rows, repeatRows=1)
                tbl.setStyle(TableStyle([
                    ("BACKGROUND",     (0, 0), (-1, 0),  rl_colors.HexColor("#e8e8e8")),
                    ("FONTNAME",       (0, 0), (-1, 0),  "Helvetica-Bold"),
                    ("FONTSIZE",       (0, 0), (-1, -1), 9),
                    ("GRID",           (0, 0), (-1, -1), 0.5, rl_colors.HexColor("#cccccc")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                     [rl_colors.white, rl_colors.HexColor("#f9f9f9")]),
                    ("VALIGN",         (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING",     (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING",  (0, 0), (-1, -1), 4),
                    ("LEFTPADDING",    (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING",   (0, 0), (-1, -1), 6),
                ]))
                flowables.append(tbl)
                flowables.append(Spacer(1, 0.2 * cm))
            continue

        # Bullet list
        if re.match(r"^[\-\*\+]\s+", line):
            while i < len(lines) and re.match(r"^[\-\*\+]\s+", lines[i]):
                text = _inline(lines[i][2:].strip())
                flowables.append(Paragraph(f"\u2022\u00a0\u00a0{text}", styles["bullet"]))
                i += 1
            continue

        # Numbered list
        if re.match(r"^\d+\.\s+", line):
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i]):
                text = _inline(re.sub(r"^\d+\.\s+", "", lines[i]))
                num = re.match(r"^(\d+)\.", lines[i]).group(1)
                flowables.append(Paragraph(f"{num}.\u00a0\u00a0{text}", styles["bullet"]))
                i += 1
            continue

        # Blank line
        if line.strip() == "":
            flowables.append(Spacer(1, 0.15 * cm))
            i += 1
            continue

        # Plain paragraph
        flowables.append(Paragraph(_inline(line), styles["body"]))
        i += 1

    return flowables


def build_pdf_export(item: dict) -> tuple[str, bytes]:
    """Build a PDF for a history item (question, answer, chart, SQL).
    Returns (filename, bytes).
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        HRFlowable, Image, Paragraph, Preformatted, SimpleDocTemplate, Spacer,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm,  bottomMargin=2 * cm,
    )

    base = getSampleStyleSheet()
    styles = {
        "h1":         ParagraphStyle("H1",     parent=base["Heading1"], fontSize=16, spaceAfter=6),
        "h2":         ParagraphStyle("H2",     parent=base["Heading2"], fontSize=13, spaceBefore=14, spaceAfter=4),
        "md_h1":      ParagraphStyle("MdH1",   parent=base["Heading1"], fontSize=13, spaceBefore=10, spaceAfter=4),
        "md_h2":      ParagraphStyle("MdH2",   parent=base["Heading2"], fontSize=11, spaceBefore=8,  spaceAfter=3),
        "md_h3":      ParagraphStyle("MdH3",   parent=base["Heading3"], fontSize=10, spaceBefore=6,  spaceAfter=2),
        "body":       ParagraphStyle("Body",   parent=base["Normal"],   fontSize=10, leading=14, spaceAfter=4),
        "bullet":     ParagraphStyle("Bullet", parent=base["Normal"],   fontSize=10, leading=14,
                                     leftIndent=14, spaceAfter=2),
        "table_cell": ParagraphStyle("TCell",  parent=base["Normal"],   fontSize=9,  leading=12),
        "code":       ParagraphStyle("Code",   parent=base["Code"],     fontSize=8,  leading=11,
                                     backColor=colors.HexColor("#f5f5f5"),
                                     leftIndent=8, rightIndent=8, borderPadding=(4, 4, 4, 4)),
    }

    page_width = A4[0] - 4 * cm
    story = []

    # Question
    story.append(Paragraph(item["question"], styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 0.3 * cm))

    # Answer
    story.append(Paragraph("Answer", styles["h2"]))
    story.extend(_md_to_flowables(item["answer"], styles))
    story.append(Spacer(1, 0.3 * cm))

    # Chart
    if item.get("fig") is not None:
        story.append(Paragraph("Chart", styles["h2"]))
        img_buf = io.BytesIO()
        item["fig"].savefig(img_buf, format="png", bbox_inches="tight", dpi=150)
        img_buf.seek(0)
        story.append(Image(img_buf, width=page_width, height=page_width * 0.55))
        story.append(Spacer(1, 0.3 * cm))

    # SQL
    story.append(Paragraph("SQL", styles["h2"]))
    wrapped_sql = "\n".join(
        "\n".join(textwrap.wrap(line, width=90)) if len(line) > 90 else line
        for line in item["final_sql"].splitlines()
    )
    story.append(Preformatted(wrapped_sql, styles["code"]))

    doc.build(story)
    buf.seek(0)

    safe = re.sub(r"[^\w\s-]", "", item["question"]).strip()
    safe = re.sub(r"[\s]+", "_", safe)[:60]
    return f"{safe}.pdf", buf.read()
