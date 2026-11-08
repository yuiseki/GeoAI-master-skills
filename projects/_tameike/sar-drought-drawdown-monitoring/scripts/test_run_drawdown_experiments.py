"""uvx --python 3.12 --with 'duckdb>=1.5.5' --with numpy --with rasterio --with pyproj --with matplotlib --with pytest pytest -q -p no:cacheprovider test_run_drawdown_experiments.py"""

# B0 and B1 of evaluate_blocks in run_drawdown_experiments.py, with OUTPUTS_DIR pointed at tmp_path.
# The module creates its own outputs/ folder at import (os.makedirs, exist_ok): that folder is tracked, nothing is written.
import json
import os

for _k in ("GDAL_DATA", "PROJ_LIB", "PROJ_DATA"):
    os.environ.pop(_k, None)

import pytest  # noqa: E402

import run_drawdown_experiments as rd  # noqa: E402

DATES = ["2024-07-02", "2024-07-14", "2024-08-19"]


def obs(db, water=50.0):
    return {"vv_mean_db": db, "water_pct": water}


def pond(tier, base, peak, wb=90.0, wp=60.0):
    return {"tier": tier, "name": tier, "lat": 34.3, "lon": 134.0, "ts": {DATES[0]: obs(base, wb), DATES[2]: obs(peak, wp)}}


def run(tmp_path, monkeypatch, targets):
    monkeypatch.setattr(rd, "OUTPUTS_DIR", str(tmp_path))
    try:
        rd.evaluate_blocks(targets, DATES)
    except Exception:                       # the later blocks need more targets; B0 and B1 are written first
        pass
    return (json.loads((tmp_path / "b0_sanity.json").read_text(encoding="utf-8")),
            json.loads((tmp_path / "b1_size_snr.json").read_text(encoding="utf-8")))


def controls():
    return [{"tier": "CTRL_PERM_WATER", "name": "w", "ts": {DATES[0]: obs(-20.0), DATES[2]: obs(-18.0)}},
            {"tier": "CTRL_FOREST", "name": "f", "ts": {DATES[0]: obs(-7.0), DATES[1]: obs(-8.0), DATES[2]: obs(-9.0)}}]


def test_b0_and_b1_from_controls_and_ponds(tmp_path, monkeypatch):
    ponds = [pond("POND_LARGE", -18.0, -14.0), pond("POND_LARGE", -18.0, -16.0), pond("POND_MED", -17.0, -15.5)]
    b0, b1 = run(tmp_path, monkeypatch, controls() + ponds)
    # permanent water mean over its 2 dates = -19 dB; forest population sd of (-7, -8, -9) = sqrt(2/3) = 0.816
    assert b0["mean_perm_water_db"] == -19.0 and b0["n_perm_water_obs"] == 2
    assert b0["mean_forest_std_db"] == 0.82 and b0["status"] == "FAIL"          # 0.82 > 0.8
    # B1: large ponds change +4 and +2 dB -> mean 3, SNR 3 / 0.816 = 3.67; medium +1.5 -> 1.84
    assert b1["tier_stats"]["POND_LARGE"] == {"n_ponds": 2, "mean_delta_db": 3.0, "std_delta_db": 1.0,
                                              "mean_water_loss_pct": 30.0, "snr": 3.67}
    assert b1["tier_stats"]["POND_MED"]["snr"] == 1.84 and b1["status"] == "PASS"
    assert b1["tier_stats"]["POND_SMALL"]["n_ponds"] == 0


def test_b0_without_controls_does_not_pass(tmp_path, monkeypatch):
    b0, _ = run(tmp_path, monkeypatch, [pond("POND_LARGE", -18.0, -14.0)])
    assert b0["status"] != "PASS"


def test_b1_conclusion_follows_the_result(tmp_path, monkeypatch):
    ponds = [pond("POND_LARGE", -18.0, -18.1), pond("POND_MED", -17.0, -17.0)]
    _, b1 = run(tmp_path, monkeypatch, controls() + ponds)
    assert b1["status"] == "FAIL"
    assert "robust drawdown detection" not in b1["conclusion"]
