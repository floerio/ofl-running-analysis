# Prompt Handling Improvements

This document describes a set of improvements applied to the prompt files of an AI data assistant project. It is intended as a reference for a code agent applying the same improvements to a similar project.

All changes are prompt-file-only unless explicitly noted. No application logic was changed.

---

## 1. Add a `# Role` heading to every standalone prompt

### Problem
Persona declarations (`You are a ...`) were either missing or buried inline in the prompt body without any structural marker. This makes prompts harder to scan, edit, and reason about.

### Rule
Every standalone prompt file must begin with a `# Role` heading (after any HTML comment header), immediately followed by the persona sentence. Shared injected blocks (files that are embedded into other prompts via a placeholder, not sent directly to the LLM) are exempt.

### Pattern
```markdown
<!-- Available placeholders: ... -->
# Role
You are a [persona description].

[rest of prompt]
```

### Applied to
All standalone prompt files: `generate_sql.md`, `fix_sql.md`, `formulate_answer.md`, `generate_chart_code.md`, `suggest_followups.md`, `chat_followup.md`, `chat_intent.md`, `chat_general.md`.

### Not applied to
Shared injected blocks (e.g. `sql_guidelines.md`) — these have no persona because they are fragments, not complete prompts.

---

## 2. Move persona to the top when it was buried in the body

### Problem
In `generate_chart_code.md` the persona line appeared *after* the injected `{data_dictionary}` and `{business_glossary}` blocks, meaning the LLM received a large context dump before knowing its role.

### Rule
The `# Role` section must always be the first content in the prompt, before any injected shared blocks or context sections.

### Before
```markdown
<!-- ... -->
{data_dictionary}

{business_glossary}

You are a data visualisation expert using Python and matplotlib.
```

### After
```markdown
<!-- ... -->
# Role
You are a data visualisation expert using Python and matplotlib.

{data_dictionary}

{business_glossary}
```

---

## 3. Add persona to prompts that were missing one entirely

### Problem
`formulate_answer.md` and `generate_chart_code.md` had no persona at all before this work — they jumped straight into injected context blocks.

### Rule
Every prompt sent directly to the LLM must have an explicit persona. Without one the LLM has no role framing for its most user-visible outputs.

### Applied to
`formulate_answer.md` — added: *"You are a running data analyst assistant. Answer the user's question using only the data provided below."*

`generate_chart_code.md` — added: *"You are a data visualisation expert using Python and matplotlib."*

---

## 4. Remove duplicate rules that were already covered by a shared block

### Problem
`generate_sql.md` contained an inline `IMPORTANT:` block repeating a rule about exact column value matching that was already fully covered (with more detail) in the shared `sql_guidelines` block injected via `{sql_guidelines}`. This created a maintenance hazard: two copies of the same rule could diverge over time.

### Rule
Never repeat in a prompt body a rule that is already covered by an injected shared block. Trust the shared block.

### Before (`generate_sql.md`)
```markdown
IMPORTANT: When the schema shows "Possible values" for a column, use ONLY those exact values (case-sensitive) in WHERE clauses.

{sql_guidelines}
```

### After
```markdown
{sql_guidelines}
```

---

## 5. Inject `{schema}` into the SQL fixing prompt

### Problem
`fix_sql.md` declared `{schema}` as an available placeholder in its comment header, and `core.py` passed it in, but the prompt body never used it. When fixing errors like "column not found", the LLM had no visibility into available column names.

### Rule
When the runtime passes a value in, the prompt should use it. The schema is particularly valuable for SQL repair — the LLM needs to know what columns actually exist to suggest a correct fix.

### Change
Added a `## Schema` section to `fix_sql.md`:

```markdown
{sql_guidelines}

## Schema
{schema}

Failed SQL:
{sql}
```

---

## 6. Move `{history_section}` before the current question in answer prompts

### Problem
In `formulate_answer.md`, the conversation history was placed *after* the current question:

```markdown
The user asked: "{question}"
{history_section}
The SQL query returned this data:
```

Conversation history is context for interpreting the current question — the LLM should have that context *before* reading the question, not after.

### Rule
`{history_section}` should always appear before the current question in any prompt that uses both.

### After (`formulate_answer.md`)
```markdown
{business_glossary}
{history_section}
The user asked: "{question}"

The SQL query returned this data:
```

---

## 7. Inject domain context into follow-up and suggestion prompts

### Problem
Several prompts were generating output (suggestions, follow-up answers, chart labels) without access to the domain vocabulary or column descriptions defined in the project's shared blocks.

### Rule
Any prompt that generates user-facing text or question suggestions should have access to both `{business_glossary}` and `{data_dictionary}` so its output uses consistent terminology.

### Changes

| Prompt | Was missing | Added |
|---|---|---|
| `suggest_followups.md` | `{business_glossary}` | ✅ |
| `chat_followup.md` | `{data_dictionary}` | ✅ (already had `{business_glossary}`) |
| `generate_chart_code.md` | `{business_glossary}` | ✅ (already had `{data_dictionary}`) |

---

## 8. Fix the column alias rule in the SQL guidelines

### Problem
The original rule said:
> *"DO NOT use column aliases (AS) in your SELECT statements."*

This was both too broad and incorrect. Without aliases, DuckDB names aggregated columns with expressions like `count_star()` or `avg(try_cast(...))`, which downstream chart code cannot reliably reference. The rule's intent was only to prevent renaming *existing* source columns.

### Rule
Split into two explicit, opposing rules:

```
- DO alias computed and aggregated columns with short, clean names
  (e.g. COUNT(*) AS run_count, AVG(...) AS avg_distance).
  This is required — without an alias, DuckDB names them things like
  count_star() which breaks chart code.

- Do NOT alias existing source columns that already have a name
  (e.g. do not write "Elapsed Time" AS duration).
  Use the original column name directly so chart code can reference it.
```

---

## 9. Tune the intent classifier to avoid mis-routing greetings and borderline queries

### Problem
The `chat_intent.md` classifier had two conflicting failure modes:

1. **Too eager to classify as UNCLEAR**: Originally the `UNCLEAR` definition was too broad ("ambiguous or unrelated to running data entirely"), causing queries like *"what is a tempo run?"* to be routed away from the SQL pipeline unnecessarily.

2. **Misses obvious non-queries**: After tightening the threshold, greetings like *"Hi!"* were being routed to `NEW_QUERY` and triggering a SQL generation attempt, because nothing in the prompt explicitly identified greetings as `UNCLEAR`.

### Rule
The `UNCLEAR` category should be:
- **Narrow enough** that anything plausibly related to running, fitness, or training defaults to `NEW_QUERY`
- **Explicit enough** that greetings, small talk, and meta-questions are reliably caught

### Final definition used
```
- UNCLEAR: The input is not a data question at all. This includes greetings
  ("Hi", "Hello", "Thanks"), small talk, meta-questions about the assistant
  ("what can you do?"), or topics completely unrelated to running, fitness,
  or the user's data (e.g. "what's the weather?", "write me a poem").
  Do NOT use this for anything that could plausibly be answered by querying
  the running data.
```

### Final instructions used
```
- Default to NEW_QUERY whenever there is any doubt — including ambiguous
  or borderline questions
- Only classify as FOLLOWUP if the question clearly cannot be answered
  without the previous result
- Only classify as UNCLEAR if you are certain the question has no connection
  to running, fitness, training, or the user's data
```

---

## 10. Keep prompt metadata in sync with prompt file changes

### Problem
This project maintains a `PROMPT_META` dictionary in code (`src/prompt_manager.py`) that documents each prompt's available placeholders. When a placeholder is added to a prompt file, the metadata must be updated to match — otherwise the configuration UI shows stale or incomplete information to the user.

### Rule
Whenever a placeholder is added to or removed from a prompt file, update the corresponding `PROMPT_META` entry in code to reflect the change. Treat the metadata as a contract between the prompt and the UI.

### Changes made
After adding `{business_glossary}` to `generate_chart_code.md` and `suggest_followups.md`, and `{data_dictionary}` to `chat_followup.md`, the `PROMPT_META` entries for those three prompts were updated accordingly.

### Example
```python
# Before — generate_chart_code was missing {business_glossary}
"generate_chart_code": {
    "placeholders": [
        ("{question}", "..."),
        ("{result_str}", "..."),
        ("{data_dictionary}", "..."),
    ],
}

# After
"generate_chart_code": {
    "placeholders": [
        ("{question}", "..."),
        ("{result_str}", "..."),
        ("{data_dictionary}", "..."),
        ("{business_glossary}", "..."),  # added
    ],
}
```

---

## Summary of all changes by file

| File | Changes applied |
|---|---|
| `generate_sql.md` | Added `# Role`; removed duplicate IMPORTANT rule (covered by `{sql_guidelines}`) |
| `fix_sql.md` | Added `# Role`; added `## Schema` section using the `{schema}` placeholder |
| `formulate_answer.md` | Added `# Role` + persona; moved `{history_section}` before the question |
| `generate_chart_code.md` | Added `# Role`; moved persona to top (was buried after context blocks); added `{business_glossary}` |
| `suggest_followups.md` | Added `# Role`; added `{business_glossary}` |
| `chat_followup.md` | Added `# Role`; added `{data_dictionary}` |
| `chat_intent.md` | Added `# Role`; rewrote `UNCLEAR` definition to explicitly include greetings and small talk; tightened classification instructions |
| `chat_general.md` | Added `# Role` |
| `sql_guidelines.md` (shared block) | Replaced single vague "no aliases" rule with two explicit opposing rules for computed vs. source columns |
| `src/prompt_manager.py` (code) | Updated `PROMPT_META` entries for `generate_chart_code`, `suggest_followups`, and `chat_followup` to document newly added placeholders |
