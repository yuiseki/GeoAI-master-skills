# uvx --with numpy --with scipy --with pytest pytest -q scripts/test_cp.py
"""Synthetic series with known answers for the sequential omnibus test (cp.py).

Speckle is simulated as gamma with L looks: intensity = mean * Gamma(L, 1/L).
"""
import numpy as np
import pytest

from cp import local_enl, log_ratio, p_value, p_value_chi2, sequential

RNG = np.random.default_rng(20261103)
N = 100_000  # pixels per simulation; the standard error of a rate of 0.01 is about 0.0003


def speckle(mean, L, rng=RNG):
    mean = np.asarray(mean, float)
    return mean * rng.gamma(L, 1 / L, size=mean.shape)


def series(means_db, L, npix=N, npol=2, rng=RNG):
    """Stack (npol, ndate, npix) with the same mean sequence (dB) in every pixel and polarisation."""
    m = 10 ** (np.asarray(means_db, float) / 10)
    return speckle(np.broadcast_to(m[None, :, None], (npol, len(m), npix)), L, rng)


@pytest.mark.parametrize("L", [4.4, 10.0])
@pytest.mark.parametrize("npol", [1, 2])
def test_false_alarm_is_alpha_until_the_first_change(L, npol):
    x = series(np.zeros(17), L, npol=npol)
    c = sequential(x, L, alpha=0.01)["change"]
    before = np.cumsum(c, axis=0) - c  # changes before each date
    rate = [(c[t] & (before[t] == 0)).sum() / (before[t] == 0).sum() for t in range(1, 17)]
    assert np.all(np.abs(np.array(rate) - 0.01) < 0.003), rate


def test_false_alarms_come_in_pairs():
    """After a false alarm the reference restarts from that one extreme date, so the next date often 'changes back'.

    Per date the rate rises above alpha (about 1.3 % at alpha = 1 %), and a change right after a change is common.
    """
    x = series(np.zeros(17), 4.4)
    c = sequential(x, 4.4, alpha=0.01)["change"]
    overall = c[1:].mean()
    after_change = c[2:][c[1:-1]].mean()
    assert 0.011 < overall < 0.016, overall
    assert after_change > 0.1, after_change


def test_any_change_rate_is_above_independent_tests():
    x = series(np.zeros(17), 4.4)
    out = sequential(x, 4.4, alpha=0.01)
    any_rate = out["change"].any(axis=0).mean()
    assert abs(any_rate - (1 - 0.99 ** 16)) < 0.02 and any_rate > (1 - 0.99 ** 16) - 0.005


def test_step_change_is_found_at_its_date_and_the_reference_restarts():
    means = [0.0] * 8 + [-10.0] * 9  # a 10 dB drop at date 8, like open water replacing a field
    out = sequential(series(means, 4.4), 4.4, alpha=0.01)
    c = out["change"]
    assert c[8].mean() > 0.99
    assert (out["ratio_db"][8][c[8]] < 0).mean() > 0.999
    after = c[9:].mean(axis=1)  # new reference from date 8: back to the false alarm rate
    assert np.all(after < 0.02), after


def test_two_dates_against_many_reference_dates_detect_smaller_changes():
    """A 3 dB drop is found more often after 12 stable reference dates than after 1 (the point of using a stack)."""
    short = sequential(series([0.0, -3.0], 4.4), 4.4, 0.01)["change"][1].mean()
    long_ = sequential(series([0.0] * 12 + [-3.0], 4.4), 4.4, 0.01)["change"][12].mean()
    assert long_ > 1.5 * short, (short, long_)


def test_wrong_enl_inflates_false_alarms():
    """Assumption broken: the data have 3 looks but the test assumes 4.4. False alarms rise well above alpha."""
    x = series(np.zeros(17), 3.0)
    rate = sequential(x, 4.4, 0.01)["change"][1:].mean()
    assert rate > 0.02, rate


def test_natural_fluctuation_inflates_false_alarms():
    """Assumption broken: the mean itself moves 1 dB (sd) from date to date (wet and dry fields). Not speckle."""
    means = RNG.normal(0, 1.0, size=(17, N))
    m = 10 ** (means / 10)
    x = speckle(np.broadcast_to(m[None], (2, 17, N)), 4.4)
    rate = sequential(x, 4.4, 0.01)["change"][1:].mean()
    assert rate > 0.02, rate


def test_missing_date_is_skipped():
    x = series([0.0] * 6 + [-10.0] * 4, 4.4, npix=1000)
    x[:, 3, :500] = np.nan
    out = sequential(x, 4.4, 0.01)
    assert not out["change"][3, :500].any()
    assert np.isnan(out["p"][3, :500]).all()
    assert out["change"][6].mean() > 0.99
    clean = ~out["change"][:6].any(0)
    assert (out["nref"][6, :500][clean[:500]] == 5).all() and (out["nref"][6, 500:][clean[500:]] == 6).all()


def test_log_ratio_baseline():
    db = np.array([[[0.0, 0.0], [0.5, 4.0], [np.nan, 4.0], [3.6, 4.1]]])  # one polarisation, 4 dates, 2 pixels
    c = log_ratio(db, 3.0)
    assert c.tolist() == [[False, False], [False, True], [False, False], [True, False]]


def test_local_enl_recovers_looks():
    img = speckle(np.ones((700, 700)), 4.4)
    enl, m = local_enl(img, 7)
    assert abs(np.median(enl) - 4.4) < 0.6  # small blocks: the moment estimate is biased and noisy
    big, _ = local_enl(img, 70)
    assert abs(np.median(big) - 4.4) < 0.15


@pytest.mark.parametrize("n", [1, 15])
@pytest.mark.parametrize("npol", [1, 2])
def test_beta_null_and_chi2_approximation_agree(n, npol):
    """Both p-values give alpha for one test; the beta null is exact, the approximation is from Conradsen et al."""
    from cp import ln_r
    L = 4.4
    x = series(np.zeros(n + 1), L, npol=npol)
    lr = sum(ln_r(x[k, :n].sum(0), np.full(N, float(n)), x[k, n], L) for k in range(npol))
    exact = (p_value(lr, np.full(N, n), L, npol) < 0.01).mean()
    approx = (p_value_chi2(lr, np.full(N, n), L, npol) < 0.01).mean()
    assert abs(exact - 0.01) < 0.0012 and abs(approx - exact) < 0.001, (exact, approx)
