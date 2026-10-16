"""uvx --with numpy --with pandas --with pyfixest --with differences --with pyreadr --with pytest pytest test_did_crosscheck.py

did against pyfixest 0.60 (feols with unit and period fixed effects, CRV1 by unit) and differences 0.3.0
(ATTgt, never-treated comparison, varying base period, outcome regression without covariates). With
GEOAI_REALDATA=1, Callaway and Sant'Anna's county teen employment panel (mpdta, from the did R package on
GitHub).
"""

import os

import numpy as np
import pandas as pd
import pyfixest as pf
import pytest
from differences import ATTgt

from did import aggregate, att_gt, twfe
from test_did import _panel


def _differences(y, unit, time, cohort):
    df = pd.DataFrame({"y": y, "uid": pd.factorize(unit)[0], "time": time, "coh": np.where(cohort > 0, cohort, np.nan)})
    m = ATTgt(data=df.set_index(["uid", "time"]), cohort_column="coh")
    r = m.fit(formula="y", control_group="never_treated", progress_bar=False)
    cells = m.results()
    return m, {(int(g), int(t)): float(v) for (g, _, t), v in cells[cells.columns[0]].items()}


@pytest.mark.parametrize("seed", range(3))
def test_twfe_matches_pyfixest(seed):
    y, unit, time, cohort = _panel(seed=seed, effect=lambda e: 1 + 0.5 * e)
    d = ((cohort > 0) & (time >= cohort)).astype(float)
    f = pf.feols("y ~ d | unit + time", data=pd.DataFrame({"y": y, "d": d, "unit": unit, "time": time}),
                 vcov={"CRV1": "unit"})
    ours = twfe(y, unit, time, d)
    assert ours["coef"] == pytest.approx(f.coef().iloc[0], rel=1e-10)
    assert ours["se"] == pytest.approx(f.se().iloc[0], rel=1e-8)


@pytest.mark.parametrize("seed", range(3))
def test_group_time_cells_and_aggregates_match_differences(seed):
    y, unit, time, cohort = _panel(seed=seed, effect=lambda e: 1 + 0.5 * e)
    m, ref = _differences(y, unit, time, cohort)
    cells = att_gt(y, unit, time, cohort)
    assert {(int(c["g"]), int(c["t"])): c["att"] for c in cells} == pytest.approx(ref, rel=1e-10)
    simple = m.aggregate("simple")
    assert aggregate(cells, "simple")["att"] == pytest.approx(float(simple.iloc[0, 0]), rel=1e-10)
    ev = m.aggregate("event")
    ours = aggregate(cells, "event")
    for e, row in ev.iterrows():
        assert ours[int(e)]["att"] == pytest.approx(float(row.iloc[0]), rel=1e-10)


@pytest.mark.skipif(os.environ.get("GEOAI_REALDATA") != "1", reason="real data: set GEOAI_REALDATA=1")
def test_mpdta_county_teen_employment(tmp_path):
    import urllib.request

    import pyreadr

    path = tmp_path / "mpdta.rda"
    urllib.request.urlretrieve("https://raw.githubusercontent.com/bcallaway11/did/master/data/mpdta.rda", path)
    d = pyreadr.read_r(str(path))["mpdta"]
    assert len(d) == 2500 and d.countyreal.nunique() == 500
    y, unit, time, cohort = (d.lemp.to_numpy(), d.countyreal.astype(str).to_numpy(), d.year.to_numpy(),
                             d["first.treat"].to_numpy())
    m, ref = _differences(y, unit, time, cohort)
    cells = att_gt(y, unit, time, cohort)
    assert {(int(c["g"]), int(c["t"])): c["att"] for c in cells} == pytest.approx(ref, rel=1e-10)
    print("simple", aggregate(cells, "simple"), "twfe", twfe(y, unit, time, ((cohort > 0) & (time >= cohort)).astype(float)))
