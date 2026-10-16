"""uvx --with numpy --with scipy --with pandas --with causalinference --with pytest pytest test_match_crosscheck.py

att_matching against causalinference 0.1.3 (CausalModel.est_via_matching, diagonal inverse-variance distance,
ties kept): the ATT with and without its bias adjustment. causalinference's standard error uses a constant
("conservative") conditional variance, not the Abadie-Imbens matching estimate, so standard errors are not
compared. With GEOAI_REALDATA=1, the National Supported Work treated men against PSID and CPS controls.
"""

import os

import numpy as np
import pytest
from causalinference import CausalModel

from match import att_matching


def _world(seed, n=400):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 3))
    t = (rng.random(n) < 1 / (1 + np.exp(-(x[:, 0] - 0.3)))).astype(int)
    y = 2 * t + x @ [1.0, 0.5, -0.5] + 0.3 * x[:, 0] ** 2 + rng.normal(size=n)
    return y, t, x


@pytest.mark.parametrize("seed", range(4))
@pytest.mark.parametrize("k", [1, 3])
@pytest.mark.parametrize("bias_adjust", [False, True])
def test_att_matches_causalinference(seed, k, bias_adjust):
    y, t, x = _world(seed)
    cm = CausalModel(y, t, x)
    cm.est_via_matching(matches=k, bias_adj=bias_adjust)
    assert att_matching(y, t, x, k=k, bias_adjust=bias_adjust)["att"] == pytest.approx(cm.estimates["matching"]["att"],
                                                                                      rel=1e-10)


NSW = "https://users.nber.org/~rdehejia/data/{}.dta"


@pytest.mark.skipif(os.environ.get("GEOAI_REALDATA") != "1", reason="real data: set GEOAI_REALDATA=1")
@pytest.mark.parametrize("controls", ["psid_controls", "cps_controls"])
def test_nsw_matching_against_causalinference(controls):
    import pandas as pd

    d = pd.read_stata(NSW.format("nsw_dw"))
    d = pd.concat([d[d.treat == 1], pd.read_stata(NSW.format(controls))], ignore_index=True)
    d = d.drop(columns="data_id").astype(float)
    d["u74"], d["u75"] = (d.re74 == 0).astype(float), (d.re75 == 0).astype(float)
    cov = ["age", "education", "black", "hispanic", "married", "nodegree", "re74", "re75", "u74", "u75"]
    y, t, x = d.re78.to_numpy(), d.treat.to_numpy().astype(int), d[cov].to_numpy()
    cm = CausalModel(y, t, x)
    cm.est_via_matching(matches=1, bias_adj=True)
    ours = att_matching(y, t, x, k=1, bias_adjust=True)
    assert ours["att"] == pytest.approx(cm.estimates["matching"]["att"], rel=1e-8)
    print(controls, ours["att"], ours["se"])
