"""Known-answer tests for the summaries that the report reads."""

import summarise as su
from test_gate import row


def p(mean, lo, hi):
    return {"mean": mean, "lo90": lo, "hi90": hi}


def test_falsification_counts_shuffles_below_the_real_loading_and_ranks_the_real_gain():
    real = {"models": {"L2": {"params": {"lam_E": p(0.5, 0.36, 0.65)}}}}
    cv = {"gains": {"E: L2 - L0H": {"sum": -38.0}, "Y: L2 - L0H": {"sum": 1.0}}}
    f1 = {"shuffles": [{"seed": s, "lam_E": p(m, 0, m + 0.1), "gains": {"E: L2 - L0H": {"sum": g}, "Y: L2 - L0H": {"sum": 0.0}}}
                       for s, m, g in [(0, 0.03, -100.0), (1, 0.4, -30.0), (2, 0.05, -90.0)]]}
    f = su.falsification(real, cv, f1)
    assert f["F2"]["shuffled_lam_E_mean_below_real_lo90"] == 2 and f["F2"]["n_shuffles"] == 3
    assert f["F1"]["shuffles_with_E_gain_above_real"] == 1
    assert f["F1"]["real_E_gain"] == -38.0 and f["F1"]["shuffled_E_gain_max"] == -30.0


def test_prior_sensitivity_flags_a_sign_flip():
    d = {"models": {"L2": {"params": {"c_E": p(0.04, -0.2, 0.3), "lam_E": p(0.5, 0.3, 0.6)}}}}
    w = {"models": {"L2": {"params": {"c_E": p(-0.01, -0.3, 0.2), "lam_E": p(0.5, 0.3, 0.6)}}}}
    g = {"gains": {"E: L2 - L0H": {"sum": -3.0, "lo90": -5, "hi90": -1}}}
    f = su.prior_sensitivity(d, w, g, g)
    assert f["params"]["L2"]["lam_E"]["same_sign"] and not f["params"]["L2"]["c_E"]["same_sign"]
    assert f["gains"]["E: L2 - L0H"]["same_sign"] and not f["all_same_sign"]


def test_a_gain_whose_interval_holds_zero_under_both_priors_keeps_its_call_even_if_the_sign_flips():
    d = {"models": {}}
    gd = {"gains": {"Y": {"sum": 1.3, "lo90": -13, "hi90": 17}, "E": {"sum": -38, "lo90": -60, "hi90": -19}}}
    gw = {"gains": {"Y": {"sum": -3.0, "lo90": -17, "hi90": 11}, "E": {"sum": -41, "lo90": -64, "hi90": -20}}}
    f = su.prior_sensitivity(d, d, gd, gw)
    assert not f["gains"]["Y"]["same_sign"] and f["gains"]["Y"]["same_call"] and f["gains"]["E"]["same_call"]
    assert f["all_same_call"]


def test_voi_compares_each_extra_with_the_baseline_seeds():
    base = {"S1": [row(i, 0, 1) for i in range(12)], "S2": [row(i, 0, 1) for i in range(12)],
            "S3": [row(i, 0, 0) for i in range(12)], "S5": [row(i, 1, 0) for i in range(12)]}
    v1 = {"S1": [row(i, 1, 0) for i in range(10)], "S2": [row(i, 0, 1) for i in range(10)],
          "S3": [row(i, 0, 0) for i in range(10)], "S5": [row(i, 0, 0) for i in range(10)]}
    out = su.voi(base, {"V1": v1}, seeds=10)
    assert out["baseline"]["n_per_scenario"] == {"S1": 10, "S2": 10, "S3": 10, "S5": 10}
    assert out["baseline"]["S1S2_correct_mean"] == 0.5 and out["baseline"]["S5_false_bear"] == 1.0
    assert out["V1"]["S1S2_correct_mean"] == 1.0 and out["V1"]["gain_S1S2_correct"] == 0.5
    assert out["V1"]["S5_false_bear"] == 0.0


def test_stage_comparison_reports_the_change_from_stage_2_to_3():
    def g(s1, s2):
        return {"default": {"S1_correct": s1, "S2_correct": s2, "S3_false_bear": 0, "S5_false_bear": 0, "S4_correct": 0,
                            "converged_share": 1, "detect_counts": {}}, "gate_passed": False}
    c = su.stages({"2a": g(0, 0.45), "2": g(0, 0), "3": g(0, 0.15)})
    assert c["change_3_minus_2"]["S2_correct"] == 0.15 and c["any_passed"] is False
