"""Known-answer tests for the identifiability gate."""

import gate as gt


def row(seed, tb, tr, sb=0, conv=True, cov=True):
    return {"seed": seed, "converged": conv, "T_B": {"detect": tb, "covered": cov}, "T_R": {"detect": tr},
            "S_B": {"detect": sb}}


def perfect():
    return {"S1": [row(i, 1, 0, -1) for i in range(5)], "S2": [row(i, 0, 1) for i in range(5)],
            "S3": [row(i, 0, 0) for i in range(5)], "S4": [row(i, 1, 1, -1) for i in range(5)],
            "S5": [row(i, 0, 0) for i in range(5)]}


def test_a_perfect_experiment_passes_every_gate():
    g = gt.gate(perfect(), perfect())
    assert g["gate_passed"] and g["secondary_S_B_passed"] and g["agreement_T_B"] == 1.0


def test_non_converged_fits_count_as_failures():
    r = perfect()
    r["S1"][0]["converged"] = r["S1"][1]["converged"] = False
    v = gt.verdicts(r)
    assert v["S1_correct"] == 0.6 and not v["G1"]
    r = perfect()
    r["S5"][0]["converged"] = r["S5"][1]["converged"] = False
    assert gt.verdicts(r)["S5_false_bear"] == 0.4


def test_a_confounded_model_that_never_detects_fails_g1_and_g2_but_not_g3():
    r = {s: [row(i, 0, 0) for i in range(5)] for s in gt.SCEN}
    v = gt.verdicts(r)
    assert not v["G1"] and not v["G2"] and v["G3"] and not v["G4"]
    assert not gt.gate(r, r)["gate_passed"]


def test_g6_fails_when_the_wide_prior_changes_the_calls():
    w = perfect()
    for x in w["S1"]:
        x["T_B"]["detect"] = 0
    g = gt.gate(perfect(), w)
    assert not g["G6"] and not g["gate_passed"]
