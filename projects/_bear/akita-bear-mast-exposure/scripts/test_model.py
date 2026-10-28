"""Tests for the offset logistic recalibration (year intercepts + one coefficient on mast x exposure)."""

import numpy as np

import model


def synth(beta, seed=0, n=200_000):
    rng = np.random.default_rng(seed)
    off = rng.normal(-5, 1.5, n)
    e = rng.random(n)
    s = {2023: 4.9, 2024: 2.4}
    rows = []
    for t, a in ((2023, 0.3), (2024, -0.2)):
        eta = off + a + beta * s[t] * e
        y = rng.random(n) < 1 / (1 + np.exp(-eta))
        rows.append((t, off, e, y))
    return rows, s


def test_fit_recovers_the_coefficient():
    rows, s = synth(0.4)
    fit = model.fit([(off, s[t] * e, y) for t, off, e, y in rows])
    assert abs(fit["beta"] - 0.4) < 0.05
    assert abs(fit["alpha"][0] - 0.3) < 0.1 and abs(fit["alpha"][1] + 0.2) < 0.1


def test_fit_finds_no_effect_when_there_is_none():
    rows, s = synth(0.0, seed=1)
    fit = model.fit([(off, s[t] * e, y) for t, off, e, y in rows])
    assert abs(fit["beta"]) < 0.05


def test_score_is_offset_plus_beta_times_mast_times_exposure():
    b = np.array([0.5, 0.25])
    e = np.array([0.0, 1.0])
    sc = model.score(b, e, beta=2.0, s=1.5)
    assert np.allclose(sc, model.logit(b) + np.array([0.0, 3.0]))


def test_logit_clips():
    assert np.isfinite(model.logit(np.array([0.0, 1.0]))).all()
