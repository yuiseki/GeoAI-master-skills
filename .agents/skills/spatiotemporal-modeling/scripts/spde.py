"""A Matern field on a regular grid as a sparse Gaussian Markov random field: the SPDE approach (Lindgren, Rue
and Lindstrom 2011) with alpha = 2, which in two dimensions is the Matern covariance with smoothness nu = 1:

    C(d) = sigma^2 kappa d K_1(kappa d),   sigma^2 = 1 / (4 pi kappa^2 tau^2),   practical range sqrt(8) / kappa

    precision      Q = tau^2 h^2 (kappa^2 I - L)^T (kappa^2 I - L), L the five-point Laplacian on cells of side h
                   with zero-flux (Neumann) edges. Each cell has at most 13 non-zero entries: a field of a
                   hundred thousand cells is solved with a sparse factorisation instead of a dense n^3 one.
    krige          the posterior mean and (optionally, for chosen cells) variance of the field given noisy
                   observations at cells: Q_post = Q + A^T A / s^2, mean = Q_post^-1 A^T y / s^2 (mean 0; centre y
                   first)
    pad            the edges distort the field: within about one range of a zero-flux edge the variance grows
                   (about twice at an edge, four times at a corner). Extend the grid by a range or more on every
                   side and use only the inner part.

    loglik / fit   the log marginal likelihood of noisy observations from the two log-determinants (sparse LU),
                   and its maximum over kappa, sigma^2 and the noise variance

Only nu = 1; the grid must be fine next to the range (h well below 1 / kappa). Observations are put in their
cell (a positional error of up to half a cell).

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with pyarrow python spde.py OBS X Y VALUE \
        --cell 200 --pad 10000 [--detrend mean|plane] [--pred PRED --pred-id ID --out pred.parquet]
"""

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import splu
from scipy.special import kv


def matern_nu1(d, sigma2, kappa):
    d = np.asarray(d, float)
    with np.errstate(invalid="ignore"):
        c = sigma2 * kappa * d * kv(1, kappa * d)
    return np.where(d > 0, c, sigma2)


def laplacian(nx, ny, h):
    """The five-point Laplacian with zero-flux edges, cells in row-major order (row = y, column = x)."""
    def one(n):
        if n == 1:  # no neighbours along this axis
            return sparse.csr_matrix((1, 1))
        main = -2.0 * np.ones(n)
        main[0] = main[-1] = -1.0  # Neumann: a missing neighbour contributes nothing
        return sparse.diags([np.ones(n - 1), main, np.ones(n - 1)], [-1, 0, 1])

    return (sparse.kron(sparse.identity(ny), one(nx)) + sparse.kron(one(ny), sparse.identity(nx))) / (h * h)


def precision(nx, ny, h, kappa, tau):
    K = kappa ** 2 * sparse.identity(nx * ny) - laplacian(nx, ny, h)
    return (tau ** 2 * h * h * (K.T @ K)).tocsc()


def tau_for(sigma2, kappa):
    return 1.0 / np.sqrt(4 * np.pi * kappa ** 2 * sigma2)


def covariance_column(Q, cell):
    """Column `cell` of Q^-1: the covariance of every cell with that one."""
    e = np.zeros(Q.shape[0])
    e[cell] = 1.0
    return splu(Q).solve(e)


def krige(Q, cells, y, noise_var, variance_cells=None):
    """cells: the observed cells' indices (repeats allowed); y: the values (mean 0). Returns the posterior mean
    over all cells and, for variance_cells, the posterior variances."""
    n = Q.shape[0]
    A = sparse.csr_matrix((np.ones(len(cells)), (np.arange(len(cells)), cells)), shape=(len(cells), n))
    Qp = (Q + (A.T @ A) / noise_var).tocsc()
    lu = splu(Qp)
    mean = lu.solve(np.asarray(A.T @ (np.asarray(y, float) / noise_var)).ravel())
    out = {"mean": mean}
    if variance_cells is not None:
        var = []
        for c in variance_cells:
            e = np.zeros(n)
            e[c] = 1.0
            var.append(lu.solve(e)[c])
        out["variance"] = np.array(var)
    return out


def _logdet(lu):
    """log |M| of a symmetric positive-definite matrix from its sparse LU factors (L has a unit diagonal)."""
    return float(np.log(np.abs(lu.U.diagonal())).sum())


def loglik(nx, ny, h, cells, y, kappa, sigma2, noise_var):
    """The log marginal likelihood of y (mean 0) = A x + e, x the SPDE field, e independent noise:
    0.5 log|Q| - 0.5 log|Q_post| - m/2 log(2 pi s^2) - 0.5 (y'y / s^2 - b' Q_post^-1 b), b = A'y / s^2."""
    y = np.asarray(y, float)
    Q = precision(nx, ny, h, kappa, tau_for(sigma2, kappa))
    n = Q.shape[0]
    A = sparse.csr_matrix((np.ones(len(cells)), (np.arange(len(cells)), cells)), shape=(len(cells), n))
    Qp = (Q + (A.T @ A) / noise_var).tocsc()
    lq, lp = splu(Q, permc_spec="MMD_AT_PLUS_A"), splu(Qp, permc_spec="MMD_AT_PLUS_A")
    b = np.asarray(A.T @ (y / noise_var)).ravel()
    quad = y @ y / noise_var - b @ lp.solve(b)
    return 0.5 * _logdet(lq) - 0.5 * _logdet(lp) - 0.5 * len(y) * np.log(2 * np.pi * noise_var) - 0.5 * quad


def fit(nx, ny, h, cells, y, start=None):
    """Maximum likelihood over log(kappa, sigma^2, noise variance), Nelder-Mead from a few starts."""
    from scipy.optimize import minimize

    y = np.asarray(y, float)
    v = y.var()
    span = h * max(nx, ny)
    starts = [np.log(start)] if start is not None else [np.log([np.sqrt(8) / (span * f), 0.7 * v, 0.3 * v])
                                                         for f in (0.05, 0.15, 0.4)]
    best = None
    for z0 in starts:
        def neg(z):
            k, s2, nv = np.exp(z)
            if k * h > 1.0:  # the grid no longer resolves the range
                return 1e300
            val = loglik(nx, ny, h, cells, y, k, s2, nv)
            return -val if np.isfinite(val) else 1e300

        r = minimize(neg, z0, method="Nelder-Mead", options={"xatol": 1e-5, "fatol": 1e-6, "maxiter": 2000})
        if best is None or r.fun < best.fun:
            best = r
    k, s2, nv = np.exp(best.x)
    return {"kappa": float(k), "sigma2": float(s2), "noise_var": float(nv), "range": float(np.sqrt(8) / k),
            "loglik": float(-best.fun), "h_kappa": float(h * k)}


def grid_for(x, y, cell, pad):
    """A grid covering the points plus pad on every side: (x0, y0, nx, ny) and each point's cell index."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    x0, y0 = x.min() - pad, y.min() - pad
    nx = int(np.ceil((x.max() + pad - x0) / cell)) + 1
    ny = int(np.ceil((y.max() + pad - y0) / cell)) + 1
    return x0, y0, nx, ny


def cell_of(x, y, x0, y0, nx, ny, cell):
    c = np.clip(np.floor((np.asarray(x, float) - x0) / cell).astype(int), 0, nx - 1)
    r = np.clip(np.floor((np.asarray(y, float) - y0) / cell).astype(int), 0, ny - 1)
    return r * nx + c


def main():
    import argparse

    import duckdb

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("obs")
    p.add_argument("x")
    p.add_argument("y")
    p.add_argument("value")
    p.add_argument("--cell", type=float, required=True, help="grid cell side, in the coordinates' unit (metres)")
    p.add_argument("--pad", type=float, required=True, help="grid margin beyond the points; a range or more")
    p.add_argument("--detrend", choices=["mean", "plane"], default="mean")
    p.add_argument("--pred", help="a table of points to predict (same x/y column names)")
    p.add_argument("--pred-id")
    p.add_argument("--out")
    a = p.parse_args()
    rows = duckdb.sql(f'select "{a.x}", "{a.y}", "{a.value}" from \'{a.obs}\'').fetchall()
    ok = [r for r in rows if None not in r]
    print(f"observations {len(rows)}, with a missing value {len(rows) - len(ok)} (left out)")
    x, yy, v = (np.array(c, float) for c in zip(*ok))
    F = np.c_[np.ones(len(v))] if a.detrend == "mean" else np.c_[np.ones(len(v)), x - x.mean(), yy - yy.mean()]
    beta = np.linalg.lstsq(F, v, rcond=None)[0]
    r = v - F @ beta
    x0, y0, nx, ny = grid_for(x, yy, a.cell, a.pad)
    cells = cell_of(x, yy, x0, y0, nx, ny, a.cell)
    print(f"grid {nx} x {ny} = {nx * ny} cells of {a.cell:g}; observations sharing a cell: "
          f"{len(cells) - len(np.unique(cells))}")
    f = fit(nx, ny, a.cell, cells, r)
    print(f"kappa {f['kappa']:.4g} (practical range {f['range']:.4g}), field variance {f['sigma2']:.4g}, noise "
          f"variance {f['noise_var']:.4g}; cell x kappa {f['h_kappa']:.2f}; log-likelihood {f['loglik']:.2f}")
    if f["h_kappa"] > 0.5:
        print("the cell is coarse next to the range (cell x kappa > 0.5): refine --cell")
    if f["range"] > a.pad:
        print("the range is longer than --pad: the edges reach the data; widen --pad")
    if a.pred:
        q = duckdb.sql(f'select "{a.pred_id}", "{a.x}", "{a.y}" from \'{a.pred}\'').fetchall()
        qx, qy = np.array([t[1] for t in q], float), np.array([t[2] for t in q], float)
        qc = cell_of(qx, qy, x0, y0, nx, ny, a.cell)
        Q = precision(nx, ny, a.cell, f["kappa"], tau_for(f["sigma2"], f["kappa"]))
        k = krige(Q, cells, r, f["noise_var"], variance_cells=qc)
        Fq = (np.c_[np.ones(len(q))] if a.detrend == "mean"
              else np.c_[np.ones(len(q)), qx - x.mean(), qy - yy.mean()])
        pred = Fq @ beta + k["mean"][qc]
        sd = np.sqrt(k["variance"] + f["noise_var"])
        if a.out:
            import pyarrow as pa
            import pyarrow.parquet as pq

            pq.write_table(pa.table({"id": [t[0] for t in q], "prediction": pred, "sd": sd}), a.out)
            print(f"wrote {len(q)} predictions to {a.out} (sd of a new observation; the trend's own error is not in it)")


if __name__ == "__main__":
    main()
