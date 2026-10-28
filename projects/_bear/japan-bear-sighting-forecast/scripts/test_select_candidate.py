import select_candidate as s


def scores(**by_model):
    return {f"{m}|h{h}": {"mae": v} for m, vals in by_model.items() for h, v in zip((1, 2, 4), vals)}


def test_picks_the_lowest_mean_mae_over_the_horizons_and_leaves_out_baselines():
    sc = scores(naive=(1, 1, 1), a=(3, 3, 3), b=(2, 2, 5), c=(4, 4, 1))
    t, chosen = s.select(sc, ["a", "b", "c"], [1, 2, 4])
    assert chosen == "a"  # a three-way tie: the first listed
    assert t["a"] == 3 and abs(t["b"] - 3) < 1e-12 and t["c"] == 3
    sc = scores(a=(3, 3, 3), b=(2, 2, 2), c=(4, 4, 4))
    assert s.select(sc, ["a", "b", "c"], [1, 2, 4])[1] == "b"


def test_a_tie_goes_to_the_candidate_with_fewer_features_listed_first():
    sc = scores(glm=(2, 2, 2), hgb_nb=(2, 2, 2))
    # tie-break by the order given: the plain model is listed before the one with more features
    assert s.select(sc, ["glm", "hgb_nb"], [1, 2, 4])[1] == "glm"
