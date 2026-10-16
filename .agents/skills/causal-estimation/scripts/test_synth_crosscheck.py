"""uvx --with numpy --with scipy --with pandas --with pysyncon --with pytest pytest test_synth_crosscheck.py

synth_weights against pysyncon 1.7.0 (Synth.fit with a fixed V). pysyncon divides each predictor by its
standard deviation across all units before applying V, so V is set to those variances to give the same
problem as ours (raw pre-treatment outcomes, equal weight). Compared: the loss reached and the weights. With
GEOAI_REALDATA=1, the Basque Country's GDP per capita (Abadie and Gardeazabal 2003, pysyncon's example data).
"""

import os

import numpy as np
import pandas as pd
import pytest
from pysyncon import Synth

from synth import synth_weights, synthetic_control
from test_synth import _factor_world


def _pysyncon(y1, Y0):
    X0 = pd.DataFrame(Y0, columns=[f"d{j}" for j in range(Y0.shape[1])])
    X1 = pd.Series(y1, name="treated")
    var = pd.concat([X0, X1], axis=1).std(axis=1).to_numpy() ** 2
    s = Synth()
    s.fit(X0=X0, X1=X1, Z0=X0, Z1=X1, custom_V=var)
    return np.asarray(s.W, float)


@pytest.mark.parametrize("seed", range(4))
def test_weights_match_pysyncon(seed):
    y1, Y0, T0 = _factor_world(seed, J=10)
    ref = _pysyncon(y1[:T0], Y0[:T0])
    ours = synth_weights(y1[:T0], Y0[:T0])
    loss = lambda w: ((y1[:T0] - Y0[:T0] @ w) ** 2).sum()
    assert loss(ours) <= loss(ref) * (1 + 1e-6) + 1e-9  # ours is at least as good
    assert ours == pytest.approx(ref, abs=1e-3)


@pytest.mark.skipif(os.environ.get("GEOAI_REALDATA") != "1", reason="real data: set GEOAI_REALDATA=1")
def test_basque_country():
    d = pd.read_csv("https://raw.githubusercontent.com/sdfordham/pysyncon/main/data/basque.csv")
    wide = d.pivot(index="year", columns="regionname", values="gdpcap")
    treated = "Basque Country (Pais Vasco)"
    donors = [c for c in wide.columns if c not in (treated, "Spain (Espana)")]
    pre = wide.index < 1970
    y1, Y0 = wide[treated].to_numpy(), wide[donors].to_numpy()
    T0 = int(pre.sum())
    ref = _pysyncon(y1[:T0], Y0[:T0])
    r = synthetic_control(y1, Y0, T0)
    assert r["w"] == pytest.approx(ref, abs=1e-3)
    print({donors[j]: round(float(r["w"][j]), 3) for j in np.flatnonzero(r["w"] > 0.001)}, r["rmspe_pre"],
          r["effect"])
