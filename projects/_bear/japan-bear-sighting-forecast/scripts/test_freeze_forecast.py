"""uvx --python 3.12 --with numpy --with pandas --with scikit-learn --with scipy --with pytest pytest -q -p no:cacheprovider test_freeze_forecast.py"""

# sha256 and forecast_rows of freeze_forecast.py; the models of evaluate.py are replaced by fixed forecasts.
import hashlib

import numpy as np
import pytest

import freeze_forecast as ff


@pytest.fixture
def fixed(monkeypatch):
    monkeypatch.setattr(ff.ev, "model_forecast", lambda cand, Y, dates, pop, o, h, weekly, W: np.array([1.0, 2.0]) * h)
    monkeypatch.setattr(ff.ev, "baseline", lambda Y, o, h, kind, weekly: np.array({"naive": [0.0, 1.0],
                                                                                    "mean_short": [0.5, 0.5],
                                                                                    "muni_mean": [2.0, 3.0]}[kind]))


def test_sha256_of_a_file(tmp_path):
    p = tmp_path / "f.parquet"
    p.write_bytes(b"x" * (3 << 20))
    assert ff.sha256(p) == hashlib.sha256(b"x" * (3 << 20)).hexdigest()


def test_forecast_rows_one_row_per_model_h_and_municipality(fixed):
    dates = np.array(["2026-09-07", "2026-09-14", "2026-09-21"], dtype="datetime64[D]")
    rows = ff.forecast_rows(None, dates, None, ["05201", "05202"], None, 2, [1, 3], "hgb_nb", "_shift4")
    assert len(rows) == 2 * 4 * 2
    assert rows[0] == ("hgb_nb_shift4", 1, "2026-09-21", "2026-09-28", "05201", 1.0)
    assert ("hgb_nb_shift4", 3, "2026-09-21", "2026-10-12", "05202", 6.0) in rows
    assert {r[0] for r in rows} == {"hgb_nb_shift4", "naive_shift4", "mean_short_shift4", "muni_mean_shift4"}


def test_forecast_rows_refuses_negative_or_missing_forecasts(monkeypatch, fixed):
    dates = np.array(["2026-09-21"], dtype="datetime64[D]")
    monkeypatch.setattr(ff.ev, "model_forecast", lambda *a: np.array([1.0, -0.1]))
    with pytest.raises(ValueError, match="hgb_nb h=1"):
        ff.forecast_rows(None, dates, None, ["a", "b"], None, 0, [1], "hgb_nb")
    monkeypatch.setattr(ff.ev, "model_forecast", lambda *a: np.array([1.0, np.nan]))
    with pytest.raises(ValueError):
        ff.forecast_rows(None, dates, None, ["a", "b"], None, 0, [1], "hgb_nb")
