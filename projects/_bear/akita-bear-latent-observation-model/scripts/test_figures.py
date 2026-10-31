"""Known-answer tests for the 5 km mesh geometry used by the maps."""

import figures as fg


def test_a_5km_mesh_code_maps_to_its_quarter_of_the_2nd_order_mesh():
    # 5940 (lat 39 deg 20', lon 140 deg), 2nd-order 00, quarter 22 = the south-west 5 km cell
    w, s, e, n = fg.mesh_bounds("59400022")
    assert abs(s - 59 / 1.5) < 1e-9 and abs(w - 140) < 1e-9
    assert abs(n - s - 2.5 / 60) < 1e-9 and abs(e - w - 3.75 / 60) < 1e-9
    w2, s2, _, _ = fg.mesh_bounds("59401377")  # 2nd-order row 1, col 3, north-east quarter
    assert abs(s2 - (59 / 1.5 + 5 / 60 + 2.5 / 60)) < 1e-9 and abs(w2 - (140 + 3 * 7.5 / 60 + 3.75 / 60)) < 1e-9
