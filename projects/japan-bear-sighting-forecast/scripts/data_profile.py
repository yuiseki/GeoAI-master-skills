"""Counts quoted in report.md, taken from the two tables built by build_table.py and build_table_gifu.py.

Usage:
    uvx --from 'duckdb>=1.5.5' python data_profile.py AKITA_WEEK.parquet GIFU_MONTH.parquet OUT.txt
"""

import sys

import duckdb

akita, gifu, out = sys.argv[1:4]
lines = []


def put(title, rows):
    lines.append(title)
    lines.extend("  " + ", ".join(str(x) for x in r) for r in rows)


put("Akita bear reports by calendar year in the weekly table (year, reports)",
    duckdb.sql(f"select year(week_start), sum(bear) from '{akita}' group by 1 order by 1").fetchall())
put("Akita: summer Jun-Aug, autumn Sep-Dec, Oct-Nov by year (year, summer, autumn, oct_nov)",
    duckdb.sql(f"""select year(week_start), sum(bear) filter (month(week_start) between 6 and 8),
                   sum(bear) filter (month(week_start) between 9 and 12), sum(bear) filter (month(week_start) between 10 and 11)
                   from '{akita}' group by 1 order by 1""").fetchall())
put("Akita: municipalities, weeks, rows, zero share of cells, mean and variance of the weekly count",
    duckdb.sql(f"select count(distinct code5), count(distinct week_start), count(*), round(avg((bear=0)::int),3), round(avg(bear),2), round(var_samp(bear),1) from '{akita}'").fetchall())
put("Gifu: reports by fiscal year in the monthly table (fiscal year starting April, reports)",
    duckdb.sql(f"""select case when month(month_start) >= 4 then year(month_start) else year(month_start) - 1 end fy, sum(bear)
                   from '{gifu}' group by 1 order by 1""").fetchall())
put("Gifu: municipalities, months, rows",
    duckdb.sql(f"select count(distinct code5), count(distinct month_start), count(*) from '{gifu}'").fetchall())
open(out, "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
