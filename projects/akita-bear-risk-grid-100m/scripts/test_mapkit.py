import numpy as np

import mapkit as mk


def test_rank_classes_put_the_top_one_percent_first_and_cover_every_class():
    c = mk.rank_classes(np.arange(1000, dtype=float))
    assert (c == 0).sum() == 10 and (c == 1).sum() == 40 and (c == 2).sum() == 50
    assert (c == 3).sum() == 150 and (c == 4).sum() == 250 and (c == 5).sum() == 500
    assert c[999] == 0 and c[0] == 5


def test_lonlat_view_of_a_box_around_the_origin_of_zone_x():
    b = mk.lonlat_view((-1000.0, 1000.0, -1000.0, 1000.0), "EPSG:6678")
    assert b.bounds[0] < 140.8333 < b.bounds[2] and b.bounds[1] < 40.0 < b.bounds[3]


def test_thin_labels_keeps_the_higher_priority_name_where_two_would_overlap():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(4, 4))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    a = ax.text(50, 50, "big town", fontsize=10)
    b = ax.text(51, 50, "small quarter", fontsize=10)  # on top of the first
    c = ax.text(10, 10, "far village", fontsize=10)
    kept, dropped = mk.thin_labels(fig, [(0, a), (3, b), (2, c)])
    assert a in kept and c in kept and b not in kept and dropped == 1
    assert not b.get_visible()
    plt.close(fig)


def test_without_holes_keeps_the_outlines_and_drops_the_holes():
    import shapely

    ring = shapely.box(0, 0, 10, 10)
    holed = ring.difference(shapely.box(4, 4, 5, 5))
    multi = shapely.MultiPolygon([holed, shapely.box(20, 0, 21, 1)])
    assert mk.without_holes(holed).equals(ring)
    out = mk.without_holes(multi)
    assert len(out.geoms) == 2 and all(len(p.interiors) == 0 for p in out.geoms)
    assert out.area == 101
