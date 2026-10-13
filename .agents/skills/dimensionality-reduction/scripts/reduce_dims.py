"""Principal components of standardised features, how many to keep, and how stable they are.

    parallel analysis  keep the leading components whose eigenvalue exceeds the 95th percentile
                       of the same component's eigenvalue in data whose columns are shuffled
                       independently (same marginals, no correlation)
    bootstrap          resample the rows and redo the PCA. Axis congruence: each original
                       component matched one-to-one to a resampled one (best |Tucker congruence|);
                       near 1, the axis itself comes back and may be named. Subspace congruence:
                       the resampled components rotated onto the original ones first; near 1, the
                       space they span comes back even if the axes within it turn (components of
                       similar eigenvalue do).

Usage:
    uvx --with numpy --with scipy --with duckdb --with pyarrow python reduce_dims.py TABLE ID F1 F2 ... \
        [--components 6] [--permutations 200] [--resamples 200] [--top 5] [--scores-out scores.parquet]
        [--compare-by COLUMN]
"""

import argparse

import numpy as np
from scipy.optimize import linear_sum_assignment


def _standardise(X):
    X = np.asarray(X, float)
    sd = X.std(axis=0)
    if (sd == 0).any():
        raise SystemExit("a feature is constant")
    return (X - X.mean(axis=0)) / sd


def pca(X):
    """Eigenvalues (of the correlation matrix), loadings (components x features), scores."""
    Z = _standardise(X)
    U, s, Vt = np.linalg.svd(Z, full_matrices=False)
    eig = s ** 2 / (len(Z) - 1)
    # Fix the sign: the largest loading of each component is positive.
    signs = np.sign(Vt[np.arange(len(Vt)), np.abs(Vt).argmax(axis=1)])
    Vt = Vt * signs[:, None]
    return eig, Vt, Z @ Vt.T


def parallel_analysis(X, permutations=200, seed=0):
    eig, _, _ = pca(X)
    rng = np.random.default_rng(seed)
    X = np.asarray(X, float)
    sims = []
    for _ in range(permutations):
        Xp = np.column_stack([rng.permutation(col) for col in X.T])
        sims.append(pca(Xp)[0])
    threshold = np.percentile(np.array(sims), 95, axis=0)
    keep = 0
    while keep < len(eig) and eig[keep] > threshold[keep]:
        keep += 1
    return keep, eig, threshold


def match_congruence(ref, cand):
    """|Tucker congruence| of each reference component with the candidate matched to it,
    one-to-one, whatever the candidates' order and signs."""
    # Tucker congruence between unit vectors is their dot product; match by its magnitude.
    cong = np.abs(np.asarray(ref) @ np.asarray(cand).T)
    rows, cols = linear_sum_assignment(-cong)
    out = np.zeros(len(ref))
    out[rows] = cong[rows, cols]
    return out


def bootstrap_congruence(X, components, resamples=200, seed=0):
    """Mean |Tucker congruence| per component between the full-data loadings and resampled ones.

    axis      each original component matched one-to-one to a resampled one: is this axis, by
              itself, the same in every resample (can it be named?)
    subspace  the resampled components first rotated onto the original ones (orthogonal
              Procrustes): is the space the components span the same (can the data be summed up
              in this many dimensions?)
    """
    X = np.asarray(X, float)
    _, load, _ = pca(X)
    ref = load[:components]
    rng = np.random.default_rng(seed)
    axis = np.zeros(components)
    sub = np.zeros(components)
    for _ in range(resamples):
        idx = rng.integers(0, len(X), len(X))
        _, lb, _ = pca(X[idx])
        cand = lb[:components]
        axis += match_congruence(ref, cand)
        # Orthogonal Procrustes: the rotation R minimising |cand.T R - ref.T|.
        u, _, vt = np.linalg.svd(cand @ ref.T)
        rotated = (u @ vt).T @ cand
        sub += np.abs(np.sum(rotated * ref, axis=1))
    return {"axis": axis / resamples, "subspace": sub / resamples}


def compare_subspaces(ref, other, components):
    """Compare the principal components of two sets of rows with the same features (a region and
    the whole, an early and a late period).

    axis         |Tucker congruence| of each reference component with its matched component of
                 the other set (order and sign ignored)
    in_subspace  for each of the other set's components, the length of its projection onto the
                 space the reference components span: 1 if it lies in that space, even if turned
    score_shift  mean of the other set's scores on the reference axes (the other set standardised
                 with the reference's means and sds), in units of the reference scores' sd
    """
    ref, other = np.asarray(ref, float), np.asarray(other, float)
    k = components
    eig_r, load_r, _ = pca(ref)
    _, load_o, _ = pca(other)
    R, O = load_r[:k], load_o[:k]
    z = (other - ref.mean(axis=0)) / ref.std(axis=0)
    shift = (z @ R.T).mean(axis=0) / np.sqrt(eig_r[:k])
    return {"axis": match_congruence(R, O), "in_subspace": np.linalg.norm(O @ R.T, axis=1),
            "score_shift": shift}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("table")
    p.add_argument("id")
    p.add_argument("features", nargs="+")
    p.add_argument("--components", type=int, default=6)
    p.add_argument("--permutations", type=int, default=200)
    p.add_argument("--resamples", type=int, default=200)
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--scores-out")
    p.add_argument("--compare-by", help="compare each value's rows with all rows")
    a = p.parse_args()

    import duckdb

    cols = [a.id, *a.features] + ([a.compare_by] if a.compare_by else [])
    rows = duckdb.sql("select " + ", ".join(f'"{c}"' for c in cols) + f" from '{a.table}'").fetchall()
    if any(v is None for r in rows for v in r):
        raise SystemExit("some rows have a missing value; drop them first and say how many")
    ids = [r[0] for r in rows]
    X = np.array([r[1:1 + len(a.features)] for r in rows], float)
    k = min(a.components, X.shape[1])
    keep, eig, thr = parallel_analysis(X, a.permutations, a.seed)
    cong = bootstrap_congruence(X, k, a.resamples, a.seed)
    _, load, scores = pca(X)
    total = eig.sum()
    print(f"rows: {len(ids)}, features: {X.shape[1]} (standardised)")
    print(f"parallel analysis keeps {keep} component(s)")
    print("component: eigenvalue (95% of shuffled), share of variance, bootstrap congruence"
          f" of the axis / of the {k}-component subspace")
    for i in range(k):
        print(f"  PC{i + 1}: {eig[i]:.3f} ({thr[i]:.3f}), {eig[i] / total:.1%}, "
              f"{cong['axis'][i]:.3f} / {cong['subspace'][i]:.3f}")
        order = np.argsort(-np.abs(load[i]))[:a.top]
        print("        " + ", ".join(f"{a.features[j]} {load[i, j]:+.2f}" for j in order))
    if a.compare_by:
        kk = max(keep, 1)
        by = np.array([r[-1] for r in rows])
        print(f"each {a.compare_by} against all rows, {kk} component(s): axis congruence, "
              "length inside the subspace, score shift (sd of all rows' scores)")
        for v in sorted(set(by.tolist())):
            m = by == v
            if m.sum() < 2 * X.shape[1]:
                print(f"  {v}: {int(m.sum())} rows, too few for {X.shape[1]} features; not compared")
                continue
            c = compare_subspaces(X, X[m], kk)
            cells = "; ".join(f"PC{i + 1} {c['axis'][i]:.2f} / {c['in_subspace'][i]:.2f} / "
                              f"{c['score_shift'][i]:+.2f}" for i in range(kk))
            print(f"  {v}: {int(m.sum())} rows: {cells}")
    if a.scores_out:
        import pyarrow as pa

        out = pa.table({"id": [str(i) for i in ids],
                        **{f"pc{i + 1}": scores[:, i] for i in range(max(keep, 1))}})
        duckdb.sql(f"copy (select * from out order by id) to '{a.scores_out}' (format parquet)")
        print(f"scores of the kept components: {a.scores_out}")


if __name__ == "__main__":
    main()
