import numpy as np

import g02_features as gf


def test_third_mesh_code_of_known_points():
    # the south-west corner cell of first mesh 5940 (39.3333N, 140.0E): code 59400000
    assert gf.mesh3(np.array([39.3334]), np.array([140.0001]))[0] == "59400000"
    # Tokyo station (35.6812N, 139.7671E) lies in third mesh 53394611
    assert gf.mesh3(np.array([35.6812]), np.array([139.7671]))[0] == "53394611"


def test_scale_follows_the_units():
    row = {"G02_053": 122, "G02_058": 28, "G02_071": 15659, "G02_014": 17782, "G02_084": 120, "G02_017": 14, "G02_038": 244}
    v = gf.scaled(row)
    assert v["t_year"] == 12.2 and v["snow_max"] == 28 and v["sun_year"] == 1565.9 and v["precip_year"] == 1778.2
    assert v["rad_year"] == 12.0 and v["t_jan"] == 1.4 and v["t_aug"] == 24.4
