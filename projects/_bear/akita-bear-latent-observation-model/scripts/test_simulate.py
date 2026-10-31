"""Known-answer tests for the synthetic generator (on a small fake mesh set, not the real files)."""

import numpy as np
import pytest

import simulate as sm

TARGETS = {"E6": 0.75, "E7": 0.94, "count": 3.4}


def fake(M=400, G=6, seed=1):
    rng = np.random.default_rng(seed)
    XB = rng.normal(size=(M, 5))
    return {"XB": XB, "H": -0.8 * XB[:, 0] + rng.normal(0, 0.5, M), "muni": rng.integers(0, G, M), "G": G,
            "offset": np.log(rng.integers(1200, 2600, M).astype(float)), "env_mask": np.ones((2, M), bool),
            "y_mask": np.ones((4, M), bool), "z_tree": XB[:, 0], "city": 2,
            "block": np.array([f"{i // 4:06d}" for i in range(M)])}


def test_the_scenarios_have_the_planned_true_changes():
    d = fake()
    share_city = np.mean(d["muni"] == d["city"])
    s1, s2, s3, s4, s5 = (sm.truth(d, s, 0, TARGETS) for s in sm.SCENARIOS)
    assert s1["T_B"] == pytest.approx(0.4, abs=0.05) and s1["T_R"] == 0 and s1["S_B"] < -0.2
    assert s2["T_B"] == 0 and s2["T_R"] == pytest.approx(0.4 + 0.6 * share_city)
    assert s3["T_B"] == 0 and s3["T_R"] == 0 and s3["dH"][3].max() == pytest.approx(0.6)
    assert (s3["dH"][3] > 0).mean() == pytest.approx(0.25, abs=0.01)
    assert s4["T_B"] == pytest.approx(s1["T_B"]) and s4["T_R"] == pytest.approx(s2["T_R"])
    assert s5["T_B"] == 0 and s5["T_R"] == 0 and np.all(s5["d"] == 0)
    assert np.all(s1["d"][0] == 0)  # 2023 is the reference


def test_the_intercepts_reproduce_the_record_rates_and_the_mean_count():
    d = fake()
    rates, means = [], []
    for seed in range(20):
        tr = sm.truth(d, "S5", seed, TARGETS)
        sim, _ = sm.simulate(d, tr, seed)
        rates.append(sim["E"].mean(1))
        means.append(sim["Y"][0].mean())
    assert np.mean(rates, 0) == pytest.approx([0.75, 0.94], abs=0.02)
    assert np.mean(means) == pytest.approx(3.4, rel=0.1)


def test_negative_binomial_counts_are_overdispersed_like_phi_2():
    d = fake(M=4000)
    tr = sm.truth(d, "S5", 3, TARGETS)
    tr["B_k"][:] = 0
    tr["rep"][:] = 0
    d["H"][:] = 0
    d["offset"][:] = 0
    tr["a0"] = np.log(4.0)
    sim, _ = sm.simulate(d, tr, 3)
    y = sim["Y"].ravel()
    assert y.mean() == pytest.approx(4.0, rel=0.05)
    assert y.var() == pytest.approx(4.0 + 4.0 ** 2 / 2, rel=0.1)


def test_extras_have_the_planned_shapes():
    d = fake()
    tr = sm.truth(d, "S1", 0, TARGETS)
    _, ex = sm.simulate(d, tr, 0, extras=("V1", "V2", "V3", "V4", "V5", "V6"))
    assert ex["camera"]["days"].shape == (200,)  # V2 overwrites V1 here; each is run alone in practice
    assert ex["capture"]["count"].shape == (4, d["G"])
    assert ex["env2020s"]["E8"].shape == (2, 400)
    assert ex["history"]["Z"].shape == (2, 4, d["G"])
    assert ex["H_obs"].shape == (4, 400)
    _, v1 = sm.simulate(d, tr, 0, extras=("V1",))
    assert len(set(v1["camera"]["mesh"][:50])) == 50 and np.array_equal(v1["camera"]["mesh"][:50], v1["camera"]["mesh"][150:])


def test_history_truth_turns_s2_into_recorded_steps_and_leaves_others_alone():
    d = fake()
    s2 = sm.history_truth(d, sm.truth(d, "S2", 0, TARGETS))
    assert np.allclose(s2["rep"][1] - s2["rep"][0], 0.4)
    assert s2["rep"][2, d["city"]] - s2["rep"][1, d["city"]] == pytest.approx(0.6)
    s1 = sm.truth(d, "S1", 0, TARGETS)
    assert np.allclose(sm.history_truth(d, s1)["rep"], s1["rep"])


def test_ou_path_keeps_the_stationary_variance_over_uneven_spacing():
    Z = sm.ou_path(200_000, np.random.default_rng(0))
    assert Z.std(1) == pytest.approx(np.full(6, sm.OU_SD), rel=0.02)
    # correlation between 2002 and 2014 is exp(-0.1 * 12), between 2023 and 2024 exp(-0.1)
    assert np.corrcoef(Z[0], Z[1])[0, 1] == pytest.approx(np.exp(-1.2), abs=0.01)
    assert np.corrcoef(Z[2], Z[3])[0, 1] == pytest.approx(np.exp(-0.1), abs=0.01)


def test_ou_truth_moves_b_between_epochs_but_keeps_the_scenario_change():
    d = fake()
    t0 = sm.truth(d, "S1", 0, TARGETS)
    t1 = sm.truth(d, "S1", 0, TARGETS, ou=True)
    assert np.allclose(t0["B_env"][0], t0["b"]) and not np.allclose(t1["B_env"][0], t1["b"])
    assert np.allclose(t1["B_k"] - t1["b"][None, :] - t1["Z"][2:], t0["d"])
    assert t1["T_B"] == pytest.approx(t0["T_B"], abs=0.05)
