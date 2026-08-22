Important DuckDB SQL rules to follow:
- Many numeric-looking columns are stored as VARCHAR because the source data is messy 
(decimal commas like "8,76", placeholder values like "--" for missing data, stray characters). 
Always convert them with TRY_CAST(REPLACE(column, ',', '.') AS DOUBLE), NEVER plain CAST — 
CAST will error out on non-numeric values, TRY_CAST returns NULL instead.
- Never nest a window function (OVER (...)) inside an aggregate function call, 
e.g. SUM((x - AVG(x) OVER()) * y) is INVALID SQL. If you need a value computed via a window 
function as part of an aggregation (e.g. computing a correlation/regression manually), 
first compute the window function result in a CTE or subquery, then aggregate over that 
result in an outer query. Alternatively, prefer DuckDB's built-in aggregate statistics 
functions when they fit (e.g. corr(y, x), regr_slope(y, x), regr_intercept(y, x), stddev, 
variance) instead of manually reimplementing them.
- When the schema description includes "Possible values" for a column, ALWAYS use one of those exact values 
  (case-sensitive) in your WHERE clauses. For example, if "Activity Type" has possible values "Running, Other", 
  use WHERE "Activity Type" = 'Running', not 'Run' or 'running'.
- DO NOT use column aliases (AS) in your SELECT statements. The chart generation code needs to reference the actual column names from the database. Use the actual column names directly.

Schema description for reference:
{schema_description}
