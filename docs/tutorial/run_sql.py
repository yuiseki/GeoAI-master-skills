"""Run a file of SQL statements with DuckDB and print the result of the last one.

    uvx --from 'duckdb>=1.5.5' python docs/tutorial/run_sql.py docs/tutorial/wdi_2022.sql
"""

import sys

import duckdb

duckdb.sql("install httpfs; load httpfs")
result = None
for statement in open(sys.argv[1]).read().split(";\n"):
    if statement.strip():
        result = duckdb.sql(statement)
if result is not None:
    print(result)
