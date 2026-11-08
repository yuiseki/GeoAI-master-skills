"""uvx --python 3.12 --with duckdb --with scikit-learn --with pandas --with pyarrow --with numpy --with pytest pytest -q docs/tutorial/test_kfold_vs_group.py"""

# Tests for kfold_vs_group.py: ordinary K-fold vs holding out whole regions, read from a parquet of countries.
# Inputs are small synthetic tables; the expected R2 values follow from how the tables are built.

import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCRIPT = Path(__file__).parent / "kfold_vs_group.py"
LINE = re.compile(r"^(KFold \(行を無作為に\)|GroupKFold \(地域ごと伏せる\))\s+(linear|hgb)\s+R2 (-?\d+\.\d{3})$")


def table(n_regions=6, per_region=10, seed=0):
    rng = np.random.default_rng(seed)
    n = n_regions * per_region
    t = pd.DataFrame({
        "iso3": [f"C{i:02d}" for i in range(n)],
        "region": np.repeat([f"R{r}" for r in range(n_regions)], per_region),
        "log_gdp_pc": rng.uniform(6, 11, n),
        "log_pop": rng.uniform(12, 20, n),
        "urban_pct": rng.uniform(10, 95, n),
    })
    return t


def run(path):
    return subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True)


def results(stdout):
    out = {}
    for line in stdout.splitlines():
        m = LINE.match(line)
        assert m, f"unexpected line {line!r}"
        out[(m.group(1).split()[0], m.group(2))] = float(m.group(3))
    return out


def test_four_lines_two_splits_by_two_models(tmp_path):
    t = table()
    t["life_exp"] = 50 + 3 * t["log_gdp_pc"]
    t.to_parquet(tmp_path / "w.parquet")
    r = run(tmp_path / "w.parquet")
    assert r.returncode == 0, r.stderr
    res = results(r.stdout)
    assert sorted(res) == [("GroupKFold", "hgb"), ("GroupKFold", "linear"), ("KFold", "hgb"), ("KFold", "linear")]


def test_an_exactly_linear_target_gets_r2_one_from_linear_regression_under_both_splits(tmp_path):
    t = table()
    t["life_exp"] = 40 + 2.5 * t["log_gdp_pc"] - 0.5 * t["log_pop"] + 0.1 * t["urban_pct"]
    t.to_parquet(tmp_path / "w.parquet")
    res = results(run(tmp_path / "w.parquet").stdout)
    assert res[("KFold", "linear")] == 1.0
    assert res[("GroupKFold", "linear")] == 1.0


def test_a_target_set_by_region_alone_is_predictable_only_when_regions_are_shared(tmp_path):
    # life_exp is a per-region constant, and the features carry the region (urban_pct = 10 * region index + small noise).
    # KFold keeps every region in training, so trees recover it; GroupKFold hides the whole region, so they cannot.
    t = table(n_regions=6, per_region=30)
    idx = t["region"].str[1:].astype(int)
    rng = np.random.default_rng(1)
    t["urban_pct"] = 10 * idx + rng.uniform(0, 1, len(t))
    t["life_exp"] = np.array([70, 55, 80, 60, 75, 50])[idx]
    t.to_parquet(tmp_path / "w.parquet")
    res = results(run(tmp_path / "w.parquet").stdout)
    assert res[("KFold", "hgb")] > 0.9
    assert res[("GroupKFold", "hgb")] < 0.5


def test_a_missing_feature_column_fails_loudly(tmp_path):
    t = table().drop(columns="urban_pct")
    t["life_exp"] = 60.0
    t.to_parquet(tmp_path / "w.parquet")
    r = run(tmp_path / "w.parquet")
    assert r.returncode != 0
    assert "urban_pct" in r.stderr


def test_missing_values_are_not_silently_filled(tmp_path):
    # the tutorial drops incomplete countries before this step; a NaN reaching the script must be an error
    t = table()
    t["life_exp"] = 60.0
    t.loc[3, "log_gdp_pc"] = np.nan
    t.to_parquet(tmp_path / "w.parquet")
    r = run(tmp_path / "w.parquet")
    assert r.returncode != 0
    assert "NaN" in r.stderr


def test_fewer_than_five_regions_cannot_be_split_into_five_groups(tmp_path):
    t = table(n_regions=4)
    t["life_exp"] = 50 + t["log_gdp_pc"]
    t.to_parquet(tmp_path / "w.parquet")
    r = run(tmp_path / "w.parquet")
    assert r.returncode != 0
    assert "group" in r.stderr.lower()


def test_no_input_path_fails():
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert r.returncode != 0
