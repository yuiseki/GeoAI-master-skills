"""uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with pyarrow --with pytest pytest test_audit_observation_bias.py

Three small worlds where the true process and the observation process are known, so the expected numbers
are worked out by hand.
"""

import numpy as np
import pytest

from audit_observation_bias import audit

R, C = np.meshgrid(np.arange(10), np.arange(10), indexing="ij")
R, C = R.ravel(), C.ravel()
IDS = [f"u{r}{c}" for r, c in zip(R, C)]
WEST = C <= 4


def case_a():
    """Uniform truth (50 events in every unit of 1,000 people); recorded 90 % in the west, 20 % in the east."""
    exposure = np.full(100, 1000.0)
    effort = np.where(WEST, 9.0, 2.0)
    count = np.where(WEST, 45.0, 10.0)
    return count, exposure, effort


def test_a_detection_gap_looks_like_a_hotspot_and_the_audit_shows_it():
    count, exposure, effort = case_a()
    r = audit(IDS, count, exposure=exposure, effort=effort, area=np.ones(100), x=C, y=-R)
    rate = r["units"]["per_exposure"]
    assert rate[WEST].mean() / rate[~WEST].mean() == pytest.approx(4.5)   # the apparent west/east difference
    strata = r["by_effort"]
    assert [s["effort"] for s in strata] == [2.0, 9.0]
    assert strata[1]["rate"] / strata[0]["rate"] == pytest.approx(4.5)
    assert r["effort_dependent"]
    assert r["units"]["flag"].count("") == 100                            # within its own effort stratum no unit stands out
    assert r["spatial"]["effort_moran"] > 0.5                             # effort itself is clustered


def test_b_truth_and_effort_together_cannot_be_separated_without_ground_truth():
    urban = (R < 3) & (C < 3)
    exposure = np.full(100, 1000.0)
    true = np.where(urban, 150.0, 50.0)                     # three times more events in the town
    effort = np.where(urban, 9.0, 3.0)                      # and three times more surveys
    detect = 1 - np.exp(-0.2 * effort)                      # 0.835 in town, 0.451 outside
    count = np.round(true * detect)
    r = audit(IDS, count, exposure=exposure, effort=effort)
    assert r["effort_dependent"]
    assert r["separable"] is False
    assert not any("corrected" in k or "true" in k for k in r["units"])   # it audits, it does not invent a truth


def test_c_exposure_is_not_effort():
    pop = 1000.0 + 400 * R                                   # people: more in the south
    count = pop * 5 / 1000 * 0.5                             # 5 per 1,000 people, half of them recorded, everywhere
    effort = np.full(100, 4.0)                               # the same survey everywhere
    r = audit(IDS, count, exposure=pop, effort=effort)
    assert np.allclose(r["units"]["per_exposure"], 0.0025)   # flat once divided by people
    assert not r["effort_dependent"]
    mistaken = audit(IDS, count, exposure=pop, effort=pop)   # population passed again as if it were survey effort
    assert mistaken["warnings"] and "exposure" in mistaken["warnings"][0]


def test_missing_and_zero_counts_are_counted_not_dropped():
    count = np.array([0.0, 3.0, np.nan, 5.0])
    r = audit(["a", "b", "c", "d"], count, exposure=np.array([10.0, 10.0, 10.0, np.nan]))
    assert r["rows"] == 4 and r["missing"]["count"] == 1 and r["missing"]["exposure"] == 1
    assert r["zero_counts"] == 1
    assert len(r["units"]["per_exposure"]) == 4 and np.isnan(r["units"]["per_exposure"][2])


def test_a_unit_far_above_its_own_effort_stratum_is_flagged():
    count, exposure, effort = case_a()
    count = count.copy()
    count[IDS.index("u07")] = 30.0                           # east, 3 times its stratum
    r = audit(IDS, count, exposure=exposure, effort=effort)
    flags = dict(zip(IDS, r["units"]["flag"]))
    assert flags["u07"] == "high within its effort stratum"
    assert flags["u00"] == ""                                # the west is high only because it is surveyed more
