"""Where a model's errors are: bias (mean of prediction minus target), MAE and RMSE per group.

Reads the out-of-fold predictions of compare_models.py --predictions-out, averages each row's
predictions over the repeats, joins the table for the column to break down by, and reports one
line per group. A text column is used as is; a numeric column is cut into --bins quantile bins
(measurement counts, population, distance to the edge).

With --lon and --lat (columns of the table), it also measures whether the errors are spatially
autocorrelated: Moran's I of each row's residual (prediction minus target) over its --k nearest rows by
great-circle distance, row-standardised weights, with a permutation pseudo p-value. Residuals that cluster
in space mean the model misses a spatial structure, and that the rows are not independent: the usual
standard errors and p-values of a regression are then too small.

Usage:
    uvx --with numpy --with duckdb python error_breakdown.py PREDICTIONS TABLE ID COLUMN \
        [--model hgb] [--bins 5] [--weight COLUMN] [--lon COL --lat COL --k 6]
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


def residual_moran(lon, lat, resid, k=6, permutations=999, seed=0):
    """Moran's I of residuals with row-standardised k-nearest-neighbour weights by great-circle distance."""
    lon, lat = np.radians(np.asarray(lon, float)), np.radians(np.asarray(lat, float))
    z = np.asarray(resid, float)
    n = len(z)
    nb = np.empty((n, k), int)
    for i in range(n):
        a = np.sin((lat - lat[i]) / 2) ** 2 + np.cos(lat[i]) * np.cos(lat) * np.sin((lon - lon[i]) / 2) ** 2
        d = 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
        d[i] = np.inf
        nb[i] = np.argsort(d, kind="stable")[:k]

    def stat(v):
        c = v - v.mean()
        return float((c * c[nb].mean(1)).sum() / (c ** 2).sum())

    observed = stat(z)
    rng = np.random.default_rng(seed)
    sim = np.array([stat(rng.permutation(z)) for _ in range(permutations)])
    ei = -1.0 / (n - 1)
    more = (sim >= observed).sum() if observed >= ei else (sim <= observed).sum()
    return {"I": observed, "EI": ei, "p_sim": float((more + 1) / (permutations + 1)), "n": n, "k": k}


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
    p.add_argument("--lon")
    p.add_argument("--lat")
    p.add_argument("--k", type=int, default=6)
    a = p.parse_args()

    import duckdb

    models = [r[0] for r in duckdb.sql(f"select distinct model from '{a.predictions}' order by 1").fetchall()]
    for model in [a.model] if a.model else models:
        rows = joined_rows(a.predictions, a.table, a.id, a.column, model, a.weight)
        if a.lon and a.lat:
            xy = joined_rows(a.predictions, a.table, a.id, a.lon, model, a.lat)
            r = residual_moran([v[2] for v in xy], [v[3] for v in xy], [v[1] - v[0] for v in xy], a.k)
            print(f"{model}: residual Moran's I {r['I']:+.3f} (expected {r['EI']:+.4f} without autocorrelation), "
                  f"pseudo p {r['p_sim']:.4f}, {r['k']} nearest by great-circle distance, {r['n']} rows")
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
