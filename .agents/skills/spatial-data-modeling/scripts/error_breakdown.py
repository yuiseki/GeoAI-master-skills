"""Where a model's errors are: bias (mean of prediction minus target), MAE and RMSE per group.

Reads the out-of-fold predictions of compare_models.py --predictions-out, averages each row's
predictions over the repeats, joins the table for the column to break down by, and reports one
line per group. A text column is used as is; a numeric column is cut into --bins quantile bins
(measurement counts, population, distance to the edge).

Usage:
    uvx --with numpy --with duckdb python error_breakdown.py PREDICTIONS TABLE ID COLUMN \
        [--model hgb] [--bins 5] [--weight COLUMN]
"""

import argparse

import numpy as np


def breakdown(target, pred, by, bins=5, weights=None):
    target, pred = np.asarray(target, float), np.asarray(pred, float)
    by = np.asarray(by)
    w = np.ones(len(target)) if weights is None else np.asarray(weights, float)
    if np.issubdtype(by.dtype, np.number):
        edges = np.unique(np.quantile(by, np.linspace(0, 1, bins + 1)))
        idx = np.clip(np.searchsorted(edges, by, side="right") - 1, 0, len(edges) - 2)
        labels = np.array([f"[{edges[i]:.4g}, {edges[i + 1]:.4g}{']' if i == len(edges) - 2 else ')'}"
                           for i in idx])
        order = [f"[{edges[i]:.4g}, {edges[i + 1]:.4g}{']' if i == len(edges) - 2 else ')'}"
                 for i in range(len(edges) - 1)]
    else:
        labels = by
        order = sorted(set(by.tolist()))
    rows = []
    for g in order:
        m = labels == g
        if not m.any():
            continue
        e = pred[m] - target[m]
        rows.append({"group": g, "n": int(m.sum()), "weight": float(w[m].sum()),
                     "bias": float(np.average(e, weights=w[m])),
                     "mae": float(np.average(np.abs(e), weights=w[m])),
                     "rmse": float(np.sqrt(np.average(e ** 2, weights=w[m])))})
    return rows


def joined_rows(predictions, table, id_col, column, model, weight=None):
    """One row per predicted id (target and prediction averaged over repeats) with the table's column.
    Stops when a predicted id has no row in the table, or the table repeats an id."""
    import duckdb

    dup = duckdb.sql(f"""select count(*) - count(distinct cast("{id_col}" as varchar)) from '{table}'""").fetchone()[0]
    if dup:
        raise SystemExit(f"{id_col} repeats in {table}: {dup} duplicate rows")
    cols = ["avg(p.target)", "avg(p.prediction)", f'any_value(t."{column}")']
    if weight:
        cols.append(f'any_value(t."{weight}")')
    n_pred = duckdb.sql(f"select count(distinct id) from '{predictions}' where model = '{model}'").fetchone()[0]
    rows = duckdb.sql(f"""
        select {", ".join(cols)}
        from '{predictions}' p join '{table}' t on cast(t."{id_col}" as varchar) = p.id
        where p.model = '{model}' group by p.id""").fetchall()
    if len(rows) != n_pred:
        raise SystemExit(f"{model}: {n_pred - len(rows)} of {n_pred} predicted ids have no row in {table}")
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("predictions")
    p.add_argument("table")
    p.add_argument("id")
    p.add_argument("column")
    p.add_argument("--model")
    p.add_argument("--bins", type=int, default=5)
    p.add_argument("--weight")
    a = p.parse_args()

    import duckdb

    models = [r[0] for r in duckdb.sql(f"select distinct model from '{a.predictions}' order by 1").fetchall()]
    for model in [a.model] if a.model else models:
        rows = joined_rows(a.predictions, a.table, a.id, a.column, model, a.weight)
        target = np.array([r[0] for r in rows], float)
        pred = np.array([r[1] for r in rows], float)
        by = np.array([r[2] for r in rows])
        if all(isinstance(v, (int, float)) for v in by):
            by = by.astype(float)
        w = np.array([r[3] for r in rows], float) if a.weight else None
        print(f"{model}: rows {len(rows)}, broken down by {a.column}"
              + (f", weighted by {a.weight}" if a.weight else ""))
        for r in breakdown(target, pred, by, a.bins, w):
            print(f"  {str(r['group']):<28} n {r['n']:>6}  bias {r['bias']:+.4g}  "
                  f"MAE {r['mae']:.4g}  RMSE {r['rmse']:.4g}")


if __name__ == "__main__":
    main()
