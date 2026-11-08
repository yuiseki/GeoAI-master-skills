"""uvx --python 3.12 --with pyflwdir --with numpy --with scipy --with rasterio --with pyproj --with 'duckdb>=1.5.5' --with pytest pytest -q -p no:cacheprovider test_analyze.py"""

# Scene readers and pairing of analyze.py, and size_class / grid10 of build_masks.py.
import os

for _k in ("GDAL_DATA", "PROJ_LIB", "PROJ_DATA"):    # an anaconda proj.db breaks rasterio's CRS (see the scripts' env -u)
    os.environ.pop(_k, None)

import numpy as np  # noqa: E402
import pytest  # noqa: E402

import analyze as an  # noqa: E402
import build_masks as bm  # noqa: E402


def test_size_class_edges():
    assert bm.size_class(0.05) == "<0.1ha" and bm.size_class(0.1) == "0.1-0.5ha"
    assert bm.size_class(0.5) == "0.5-1ha" and bm.size_class(4.99) == "1-5ha" and bm.size_class(5.0) == ">=5ha"
    assert {bm.size_class(a) for a in (0.2, 0.7, 2, 50)} == set(an.CLASSES)


def test_grid10_halves_the_5m_grid():
    (h, w), tr10, (h5, w5), tr5 = bm.grid10(bm.BOXES["kagawa"])
    assert (h, w) == (h5 // 2, w5 // 2) and tr10.a == 10.0 and tr10.e == -10.0
    assert (tr10.c, tr10.f) == (tr5.c, tr5.f)


def test_load_scenes_keys_by_date(tmp_path, monkeypatch):
    d = tmp_path / "scenes" / "kagawa"
    d.mkdir(parents=True)
    for n in ("S1_2024-05-01", "S1_2024-05-13", "S2_2024-05-02", "x_2024"):
        (d / f"{n}.npz").write_bytes(b"")
    monkeypatch.setattr(an, "ART", tmp_path)
    s1, s2 = an.load_scenes("kagawa")
    assert list(s1) == ["2024-05-01", "2024-05-13"] and list(s2) == ["2024-05-02"]


def test_s1_db(tmp_path):
    np.savez(tmp_path / "s1.npz", vv=np.array([[1.0, 0.1], [0.0, -1.0]], dtype="float32"))
    db = an.s1_db(tmp_path / "s1.npz")
    assert db[0].tolist() == pytest.approx([0.0, -10.0]) and np.isnan(db[1]).all()


@pytest.mark.parametrize("baseline,off", [("04.00", 1000.0), ("05.10", 1000.0), ("03.01", 0.0)])
def test_s2_arrays_ndwi_and_the_baseline_offset(tmp_path, baseline, off):
    b03 = np.array([[3000, 0]], dtype="uint16")
    b08 = np.array([[2000, 500]], dtype="uint16")
    np.savez(tmp_path / "s2.npz", b03=b03, b08=b08, scl=np.array([[6, 0]], dtype="uint8"), baseline=np.array(baseline))
    ndwi, scl, has = an.s2_arrays(tmp_path / "s2.npz")
    g, n = (3000 - off) / 1e4, (2000 - off) / 1e4
    assert ndwi[0, 0] == pytest.approx((g - n) / (g + n)) and np.isnan(ndwi[0, 1])
    assert has.tolist() == [[True, False]] and scl.tolist() == [[6, 0]]


def row(sensor, pond, date, frac, n=10, clear=1.0, variant="main", outline="inner", size="1-5ha"):
    return dict(box="kagawa", pond=pond, date=date, sensor=sensor, variant=variant, outline=outline, frac=frac,
                n_valid=n, clear_share=clear, size_class=size)


def test_make_pairs_applies_the_quality_rules():
    rows = [row("S1", 1, "d1", 0.5), row("S2", 1, "e1", 0.6),                 # kept
            row("S1", 2, "d1", 0.5, n=3), row("S2", 2, "e1", 0.6),            # S1 below MIN_PIX
            row("S1", 3, "d1", 0.5), row("S2", 3, "e1", 0.6, clear=0.89),     # S2 too cloudy
            row("S1", 4, "d1", None), row("S2", 4, "e1", 0.6),                # no S1 fraction
            row("S1", 5, "d2", 0.5), row("S2", 5, "e2", 0.6),                 # d2 has no S2 date paired
            row("S1", 6, "d1", 0.5, outline="full"), row("S2", 6, "e1", 0.6, outline="full"),
            row("S1", 7, "d1", 0.2, variant="s1_-13"), row("S2", 7, "e1", 0.6)]
    pairs = an.make_pairs(rows, {"kagawa": {"d1": "e1"}})
    assert pairs == [dict(box="kagawa", pond=1, size_class="1-5ha", s1_date="d1", s2_date="e1", s1_frac=0.5,
                          s2_frac=0.6, n_s1=10, n_s2=10)]
    assert [p["pond"] for p in an.make_pairs(rows, {"kagawa": {"d1": "e1"}}, outline="full")] == [6]
    assert [p["pond"] for p in an.make_pairs(rows, {"kagawa": {"d1": "e1"}}, s1_var="s1_-13")] == [7]


def test_boot_ci_resamples_ponds(monkeypatch):
    monkeypatch.setattr(an, "N_BOOT", 400)
    lo, hi = an.boot_ci({"a": 1.0, "b": 1.0}, lambda v: float(np.mean(v)), np.random.default_rng(0))
    assert (lo, hi) == (1.0, 1.0)
    lo, hi = an.boot_ci({"a": 0.0, "b": 1.0}, lambda v: float(np.mean(v)), np.random.default_rng(0))
    assert (lo, hi) == (0.0, 1.0)                    # the two all-same draws each have probability 1/4
