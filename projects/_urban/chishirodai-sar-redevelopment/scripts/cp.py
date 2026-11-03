"""Change points in a Sentinel-1 intensity time series, pixel by pixel (sequential omnibus test).

The test is the sequential likelihood-ratio test of Conradsen et al. (2016, IEEE TGRS 54(5), 3007-3024) for a series of
complex Wishart matrices, in the special case used for GRD and RTC products: intensities only (no phase), one or two
polarisations treated as independent, each a gamma variable with L equivalent looks.

At date t, with the pixel's reference made of the n dates since its last change (sum S of their intensities), the test of
"the mean at t equals the mean of the reference" is, per polarisation,

    ln R = L [ j ln j - n ln n + n ln S + ln X - j ln (S + X) ],   j = n + 1

Under no change, B = X / (S + X) is exactly Beta(L, nL), so ln R is a known function of a beta variable. The p-value
here is the share of null draws of the summed ln R (drawn from the beta variables, NULL_DRAWS per reference length n)
at or below the observed. The paper's approximation (-2 rho ln R close to chi-square with one degree of freedom per
polarisation, rho and omega2 with p = 1) agrees with it to within 0.1 percentage point at alpha = 1 % (test_cp.py) and is
kept as `p_value_chi2`. A change is a date where the p-value is below alpha; the reference then restarts from that date.

Until the first change, each date has false alarm probability alpha. After a false alarm the reference is that one
extreme date, so the next date often "changes back": false alarms come in pairs and the rate per date over a long series
is above alpha (about 1.3 % at alpha = 1 % with 17 dates and L = 4.4, test_cp.py).

Assumptions (checked by the tests in test_cp.py; see EXPERIMENT_PLAN.md):
- the intensity of a pixel is gamma with the same L at every date (fully developed speckle, no texture that varies in time);
- the polarisations are independent;
- the dates are co-registered (the same ground at the same pixel).
"""
import numpy as np
from scipy import stats


def rho_omega(j, L):
    """Bartlett correction rho and the second-order term omega2 for one polarisation (p = 1), j dates in the test."""
    j = np.asarray(j, float)
    rho = 1 - (1 + 1 / (j * (j - 1))) / (6 * L)
    omega2 = -0.25 * (1 - 1 / rho) ** 2
    return rho, omega2


def ln_r(S, n, X, L):
    """ln R of one polarisation; S is the sum of the n reference intensities, X the intensity at the tested date."""
    j = n + 1.0
    with np.errstate(divide="ignore", invalid="ignore"):
        nlogn = np.where(n > 0, n * np.log(np.where(n > 0, n, 1.0)), 0.0)
        return L * (j * np.log(j) - nlogn + n * np.log(S) + np.log(X) - j * np.log(S + X))


NULL_DRAWS = 400_000
_NULL = {}


def null_table(n, L, npol, draws=NULL_DRAWS):
    """Sorted null draws of the summed ln R for a reference of n dates (seeded, so the same every run)."""
    key = (int(n), float(L), int(npol), int(draws))
    if key not in _NULL:
        rng = np.random.default_rng(1000 * int(n) + npol)
        B = rng.beta(L, n * L, size=(npol, draws))
        j = n + 1.0
        lr = (L * (j * np.log(j) - n * np.log(n) + n * np.log1p(-B) + np.log(B))).sum(0)
        _NULL[key] = np.sort(lr)
    return _NULL[key]


def p_value(lnr_sum, n, L, npol, draws=NULL_DRAWS):
    """P-value (share of null draws with ln R at or below the observed) of the summed ln R, reference of n dates."""
    lnr_sum = np.asarray(lnr_sum, float)
    n = np.broadcast_to(np.asarray(n), lnr_sum.shape)
    out = np.full(lnr_sum.shape, np.nan)
    for k in np.unique(n[np.isfinite(lnr_sum)]):
        sel = (n == k) & np.isfinite(lnr_sum)
        tab = null_table(k, L, npol, draws)
        out[sel] = (np.searchsorted(tab, lnr_sum[sel], side="right") + 1) / (len(tab) + 1)
    return out


def p_value_chi2(lnr_sum, n, L, npol):
    """P-value from the chi-square approximation of Conradsen et al. (2016), for comparison only."""
    rho, om = rho_omega(n + 1.0, L)
    z = -2 * rho * lnr_sum
    f = npol
    cdf = stats.chi2.cdf(z, f) + npol * om * (stats.chi2.cdf(z, f + 4) - stats.chi2.cdf(z, f))
    return np.clip(1 - cdf, 0, 1)


def sequential(stack, L, alpha):
    """Change points of a stack of linear intensities, shape (npol, ndate, ...).

    Returns a dict of arrays of shape (ndate, ...):
    - change: True where a change is found at that date (date 0 is never a change)
    - p: the p-value of the test at that date (nan at date 0 and where the date is missing)
    - ratio_db: 10 log10 of the date over the reference mean, first polarisation (the sign of the change)
    - nref: the number of reference dates used in the test
    A missing value (nan or <= 0) at a date in any polarisation skips that date for that pixel.
    """
    stack = np.asarray(stack, float)
    npol, nd = stack.shape[:2]
    shape = stack.shape[2:]
    change = np.zeros((nd,) + shape, bool)
    p = np.full((nd,) + shape, np.nan)
    ratio_db = np.full((nd,) + shape, np.nan)
    nref = np.zeros((nd,) + shape, np.int16)
    S = np.zeros((npol,) + shape)
    n = np.zeros(shape)
    for t in range(nd):
        X = stack[:, t]
        ok = np.all(np.isfinite(X) & (X > 0), axis=0)
        test = ok & (n > 0)
        if test.any():
            lr = np.zeros(shape)
            for k in range(npol):
                lr = lr + np.where(test, ln_r(np.where(test, S[k], 1.0), n, np.where(test, X[k], 1.0), L), 0.0)
            pt = p_value(lr, np.where(test, n, 1.0), L, npol)
            p[t] = np.where(test, pt, np.nan)
            with np.errstate(divide="ignore", invalid="ignore"):
                ratio_db[t] = np.where(test, 10 * np.log10(X[0] * n / S[0]), np.nan)
            nref[t] = np.where(test, n, 0)
            change[t] = test & (pt < alpha)
        reset = change[t] | (ok & (n == 0))
        grow = ok & ~reset
        for k in range(npol):
            S[k] = np.where(reset, np.where(ok, X[k], 0.0), np.where(grow, S[k] + np.where(ok, X[k], 0.0), S[k]))
        n = np.where(reset, 1.0, np.where(grow, n + 1, n))
    return {"change": change, "p": p, "ratio_db": ratio_db, "nref": nref}


def log_ratio(stack_db, threshold_db):
    """Baseline: a change at date t where |dB(t) - dB(t-1)| >= threshold in any polarisation (stack in dB, npol x ndate x ...).

    Missing dates are skipped: the previous valid date is used.
    """
    stack_db = np.asarray(stack_db, float)
    npol, nd = stack_db.shape[:2]
    change = np.zeros((nd,) + stack_db.shape[2:], bool)
    prev = np.full(stack_db.shape[:1] + stack_db.shape[2:], np.nan)
    for t in range(nd):
        x = stack_db[:, t]
        ok = np.all(np.isfinite(x), axis=0)
        has = ok & np.all(np.isfinite(prev), axis=0)
        d = np.abs(x - prev).max(axis=0)
        change[t] = has & (np.nan_to_num(d) >= threshold_db)
        prev = np.where(ok, x, prev)
    return change


def local_enl(img, win=7):
    """ENL by moments (mean^2 / variance) in non-overlapping win x win blocks of a linear intensity image.

    Blocks with any missing value are nan. Returns (enl, block_mean) of shape (rows // win, cols // win).
    """
    img = np.asarray(img, float)
    r, c = (img.shape[0] // win) * win, (img.shape[1] // win) * win
    b = img[:r, :c].reshape(r // win, win, c // win, win).transpose(0, 2, 1, 3).reshape(r // win, c // win, -1)
    m = b.mean(-1)
    v = b.var(-1, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return m ** 2 / v, m
