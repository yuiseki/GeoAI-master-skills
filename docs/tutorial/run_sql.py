"""Run a file of SQL statements with DuckDB and print the result of the last one.

    uvx --from 'duckdb>=1.5.5,<2' python docs/tutorial/run_sql.py docs/tutorial/wdi_2022.sql
"""

import sys

import duckdb

duckdb.sql("install httpfs; load httpfs")
result = None
# DuckDB's own parser splits the file, so comments and a ";" inside a string literal are not statement breaks.
# DuckDB 2.0 changed this API (and dropped fetchone on relations); the command above pins 1.x
for statement in duckdb.extract_statements(open(sys.argv[1], encoding="utf-8").read()):
    result = duckdb.sql(statement)
if result is not None:
    print(result)
