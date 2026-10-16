"""uvx --with numpy --with matplotlib --with colorspacious --with pytest pytest test_cvd_crosscheck.py

The simulation against colorspacious 1.1.2 ("sRGB1+CVD" at severity 100, which uses the same Machado et al.
2009 matrices on linear sRGB), and CIELAB against its "CIELab" (D65). colorspacious's XYZ white differs in the
fourth decimal, which moves L*a*b* by up to 0.02.
"""

import numpy as np
import pytest

from cvd import lab, simulate

cs = pytest.importorskip("colorspacious")


@pytest.mark.parametrize("kind,name", [("protan", "protanomaly"), ("deutan", "deuteranomaly"),
                                       ("tritan", "tritanomaly")])
def test_simulation_matches_colorspacious(kind, name):
    rgb = np.random.default_rng(0).random((200, 3))
    ref = np.clip(cs.cspace_convert(rgb, {"name": "sRGB1+CVD", "cvd_type": name, "severity": 100}, "sRGB1"), 0, 1)
    np.testing.assert_allclose(simulate(rgb, kind), ref, atol=1e-12)


def test_lab_matches_colorspacious():
    rgb = np.random.default_rng(1).random((200, 3))
    np.testing.assert_allclose(lab(rgb), cs.cspace_convert(rgb, "sRGB1", "CIELab"), atol=0.05)
