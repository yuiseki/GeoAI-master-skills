"""A value that is measured is often a noisy stand-in for a true value nobody observes. These are the small
pieces for reasoning about that: the reliability ratio, what repeats and a validation sample tell about it,
regression calibration, and misclassification of a 0/1 value.

    reliability               var(true) / (var(true) + var(error)): the share of the observed variance that
                              is the true value. Under classical error (observed = true + independent error)
                              a slope on the observed predictor is the true slope times this ratio.
    reliability_from_repeats  n units x k repeated measurements: the error variance from the spread within
                              units, the true variance from the spread of unit means minus error / k, the
                              reliability of one measurement and of the mean of k.
    calibration_from_validation  in rows where the true value is known too, the regression of the true value
                              on the observed one: E[true | observed] = a + b x observed (b is the reliability
                              under classical error). A choice of rows that depends only on the observed
                              variables the calibration conditions on can be ignorable; one that depends on the
                              true value, the outcome or the measurement process can bias the line.
    regression_calibration    replaces the observed predictor by a + b x observed and refits. The standard
                              errors it prints ignore that a and b were estimated: bootstrap the validation
                              rows for an interval.
    observed_prevalence       the rate a test with sensitivity se and specificity sp reports: se p + (1 - sp)(1 - p)
    correct_prevalence        the inverse (Rogan-Gladen). Stops when se + sp <= 1 or the result is outside 0..1:
                              the assumed rates do not fit the data.
    correction_grid           the correction over a grid of se and sp, for when the rates are not known; None
                              where they do not fit.
    misclassified_exposure    the 2 x 2 table expected when a 0/1 exposure is misclassified, the same way for
                              cases and non-cases (non-differential) or not (se_cases, sp_cases).

Berkson error (true = assigned + independent error, as when every resident gets the grid cell's value) does
not bias a linear slope; it widens the residuals. Error in the outcome alone does not bias the slope either;
it widens the standard error. Neither is the same as a missing value: a missing value is absent, an error
value is present and wrong.

Usage:
    uvx --from 'duckdb>=1.5.5' --with numpy python measurement_error.py repeats TABLE COL1 COL2 [...]
    uvx --from 'duckdb>=1.5.5' --with numpy python measurement_error.py calibrate TABLE OUTCOME OBSERVED TRUE
        (TRUE is null outside the validation rows)
    uvx --with numpy python measurement_error.py prevalence P_OBSERVED --se 0.8 0.9 --sp 0.95 0.99
"""

import argparse

import numpy as np


def ols(y, X):
    y = np.asarray(y, float)
    D = np.c_[np.ones(len(y)), np.asarray(X, float).reshape(len(y), -1)]
    inv = np.linalg.inv(D.T @ D)
    b = inv @ D.T @ y
    u = y - D @ b
    se = np.sqrt(np.diag(inv) * (u @ u) / (len(y) - D.shape[1]))
    return {"coef": b, "se": se}


def reliability(var_true, var_error):
    return var_true / (var_true + var_error)


def reliability_from_repeats(W):
    W = np.asarray(W, float)
    n, k = W.shape
    if k < 2:
        raise ValueError("repeats need at least two measurements per unit")
    error_var = float(np.mean(np.var(W, axis=1, ddof=1)))
    true_var = float(np.var(W.mean(axis=1), ddof=1) - error_var / k)
    if true_var <= 0:
        raise ValueError("the unit means vary no more than the error alone would make them: no reliability")
    return {"n": n, "k": k, "error_var": error_var, "true_var": true_var,
            "lambda_single": true_var / (true_var + error_var),
            "lambda_mean": true_var / (true_var + error_var / k)}


def calibration_from_validation(x_true, w):
    x_true, w = np.asarray(x_true, float), np.asarray(w, float)
    b = float(np.cov(w, x_true)[0, 1] / np.var(w, ddof=1))
    return float(x_true.mean() - b * w.mean()), b


def regression_calibration(y, w, a, b):
    return ols(y, a + b * np.asarray(w, float))


def observed_prevalence(p, se, sp):
    return se * p + (1 - sp) * (1 - p)


def correct_prevalence(p_obs, se, sp):
    if se + sp <= 1:
        raise ValueError(f"sensitivity {se} + specificity {sp} <= 1: the test tells nothing")
    p = (p_obs + sp - 1) / (se + sp - 1)
    if not -1e-12 <= p <= 1 + 1e-12:
        raise ValueError(f"corrected rate {p:.4g} is outside 0..1: se {se}, sp {sp} do not fit {p_obs}")
    return min(max(p, 0.0), 1.0)


def correction_grid(p_obs, ses, sps):
    out = {}
    for se in ses:
        for sp in sps:
            try:
                out[(se, sp)] = correct_prevalence(p_obs, se, sp)
            except ValueError:
                out[(se, sp)] = None
    return out


def misclassified_exposure(n_exposed, n_unexposed, risk_exposed, risk_unexposed, se, sp,
                           se_cases=None, sp_cases=None):
    se_c = se if se_cases is None else se_cases
    sp_c = sp if sp_cases is None else sp_cases
    cases = {1: n_exposed * risk_exposed, 0: n_unexposed * risk_unexposed}
    non = {1: n_exposed - cases[1], 0: n_unexposed - cases[0]}
    called_cases = se_c * cases[1] + (1 - sp_c) * cases[0]
    called_non = se * non[1] + (1 - sp) * non[0]
    other_cases = cases[1] + cases[0] - called_cases
    other_non = non[1] + non[0] - called_non
    r1 = called_cases / (called_cases + called_non)
    r0 = other_cases / (other_cases + other_non)
    return {"risk_exposed": r1, "risk_unexposed": r0, "rd": r1 - r0,
            "true_rd": risk_exposed - risk_unexposed}


def _load(table, cols):
    import duckdb

    return duckdb.sql("select " + ", ".join(f'"{c}"' for c in cols) + f" from '{table}'").fetchall()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("repeats")
    r.add_argument("table")
    r.add_argument("columns", nargs="+")
    c = sub.add_parser("calibrate")
    for name in ("table", "outcome", "observed", "true"):
        c.add_argument(name)
    v = sub.add_parser("prevalence")
    v.add_argument("p_observed", type=float)
    v.add_argument("--se", type=float, nargs="+", required=True)
    v.add_argument("--sp", type=float, nargs="+", required=True)
    a = p.parse_args()
    if a.cmd == "repeats":
        rows = [x for x in _load(a.table, a.columns) if None not in x]
        res = reliability_from_repeats(np.array(rows, float))
        print(f"units {res['n']} with {res['k']} measurements each: error variance {res['error_var']:.4g}, "
              f"true variance {res['true_var']:.4g}, reliability of one {res['lambda_single']:.3f}, "
              f"of the mean {res['lambda_mean']:.3f}. Assumes the repeats share no error (same instrument, "
              "same day, same rater would)")
    elif a.cmd == "calibrate":
        rows = [x for x in _load(a.table, [a.outcome, a.observed, a.true]) if x[0] is not None and x[1] is not None]
        y = np.array([x[0] for x in rows], float)
        w = np.array([x[1] for x in rows], float)
        val = [x for x in rows if x[2] is not None]
        if len(val) < 10:
            raise SystemExit(f"{len(val)} validation rows: too few to estimate the calibration")
        a0, b = calibration_from_validation([x[2] for x in val], [x[1] for x in val])
        naive = ols(y, w)["coef"][1]
        fixed = regression_calibration(y, w, a0, b)["coef"][1]
        print(f"rows {len(y)}, validation rows {len(val)}: true = {a0:.4g} + {b:.4g} x observed")
        print(f"slope on the observed value {naive:.4g}; after regression calibration {fixed:.4g}")
        print("assumes the validation rows were chosen at random or by the observed value alone (not by the true "
              "value or the outcome), and that the error behaves the same outside them; the interval needs a "
              "bootstrap of the validation rows")
    else:
        for (se, sp), val in correction_grid(a.p_observed, a.se, a.sp).items():
            print(f"se {se} sp {sp}: " + ("does not fit" if val is None else f"{val:.4g}"))


if __name__ == "__main__":
    main()
