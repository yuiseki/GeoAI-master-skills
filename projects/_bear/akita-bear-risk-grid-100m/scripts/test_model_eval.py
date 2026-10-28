import numpy as np

import model_eval as me


def tiny(seed=0):
    rng = np.random.default_rng(seed)
    ny, nx = 40, 50
    muni = np.zeros((ny, nx), dtype=np.int16)
    muni[:, :5] = -1
    static = {"tree": rng.random((ny, nx)).astype(np.float32), "pop_500": rng.random((ny, nx)).astype(np.float32),
              "pop_2000": rng.random((ny, nx)).astype(np.float32)}
    hot = static["tree"] > 0.8
    counts = {y: (rng.random((ny, nx)) < np.where(hot, 0.2, 0.01)).astype(float) for y in (2022, 2023, 2024, 2025)}
    return static, counts, muni


def test_design_uses_prefecture_cells_and_labels_from_the_target_year():
    static, counts, muni = tiny()
    X, names, y, c = me.design(static, counts, muni, 2024, history=True)
    assert X.shape[0] == int((muni >= 0).sum()) and len(y) == X.shape[0]
    assert y.sum() == int((counts[2024][muni >= 0] > 0).sum())
    assert "h_all_r1000" in names and "tree" in names
    X2, names2, _, _ = me.design(static, counts, muni, 2024, history=False)
    assert not any(n.startswith("h_") for n in names2)


def test_models_see_no_label_of_the_test_year():
    static, counts, muni = tiny()
    a = me.run_models(static, counts, muni, [2023], 2024, ["M_full", "B_hist"], seed=0)
    counts2 = dict(counts)
    counts2[2024] = np.zeros_like(counts[2024])  # the test year's labels changed
    b = me.run_models(static, counts2, muni, [2023], 2024, ["M_full", "B_hist"], seed=0)
    for m in ("M_full", "B_hist"):
        np.testing.assert_array_equal(a[m], b[m])


def test_a_learnable_pattern_is_found():
    static, counts, muni = tiny()
    s = me.run_models(static, counts, muni, [2023, 2024], 2025, ["M_full", "B_env"], seed=0)
    _, _, y, _ = me.design(static, counts, muni, 2025, history=True)
    from sklearn.metrics import roc_auc_score

    assert roc_auc_score(y, s["B_env"]) > 0.7
