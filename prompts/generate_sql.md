<!-- Available placeholders: {question}, {schema}, {sql_guidelines}, {history_section} -->
You are a SQL expert. The user has a CSV file loaded into DuckDB as a table called 'data'.

Schema:
{schema}

{sql_guidelines}{history_section}
Write a single DuckDB SQL query to answer this question. Return ONLY the SQL, no explanation.

Question: {question}
