"""The lean of a pole in a level perspective view, measured against the other vertical lines of the same view.

    uvx --with numpy --with scikit-image python pole_lean.py VIEW.jpg X0 Y0 X1 Y1

In a view cut at pitch 0 from a level 360 image (equirect_view.py), every world-vertical line is a vertical image
line. A pole that leans shows as a line tilted from vertical. Only the lean across the line of sight is seen: a
pole leaning towards or away from the camera looks upright. Measuring the same pole from two capture points at
different headings gives both components; this script measures one view.

The camera of a vehicle is not exactly level, so every vertical line of the view tilts by a small common angle.
That angle is estimated as the length-weighted median angle of long near-vertical line segments outside the
pole's box (building edges, other poles), and taken away. The estimate assumes those lines are truly vertical;
a view with few of them is not corrected (corrected = False) and says how many it had.

Angles are in degrees, positive when the top of the line is to the right of its bottom.
"""

import argparse
import json
import math
import sys

import numpy as np


def line_angles(gray, min_length=40, max_tilt=20.0, mask=None, seed=0):
    """Angles (degrees from vertical, + = top to the right) and lengths of near-vertical line segments."""
    from skimage.feature import canny
    from skimage.transform import probabilistic_hough_line
    edges = canny(gray, sigma=1.5)
    if mask is not None:
        edges &= mask
    thetas = np.deg2rad(np.linspace(-max_tilt, max_tilt, int(max_tilt * 20) + 1))
    segs = probabilistic_hough_line(edges, threshold=10, line_length=min_length, line_gap=3, theta=thetas,
                                    rng=np.random.default_rng(seed))
    ang, lens = [], []
    for (x0, y0), (x1, y1) in segs:
        if y0 < y1:                               # make (x0, y0) the bottom end
            x0, y0, x1, y1 = x1, y1, x0, y0
        dx, dy = x1 - x0, y0 - y1
        a = math.degrees(math.atan2(dx, dy))
        if abs(a) <= max_tilt:
            ang.append(a)
            lens.append(math.hypot(dx, dy))
    return np.array(ang), np.array(lens)


def _wmedian(a, w):
    o = np.argsort(a)
    c = np.cumsum(w[o])
    return float(a[o][np.searchsorted(c, c[-1] / 2)])


def pole_lean(gray, box, min_pole_length=None, min_reference=3, reference_length=60):
    """box: (x0, y0, x1, y1) in pixels. Returns raw, reference and corrected angles and the counts behind them."""
    gray = np.asarray(gray, float)
    if gray.ndim == 3:
        gray = gray.mean(axis=2)
    if gray.max() > 1.5:
        gray = gray / 255.0
    h, w = gray.shape
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w), min(y1, h)
    inside = np.zeros_like(gray, bool)
    inside[y0:y1, x0:x1] = True
    mpl = min_pole_length or max(20, int(0.3 * (y1 - y0)))
    pa, pl = line_angles(gray, mpl, mask=inside)
    ra, rl = line_angles(gray, reference_length, max_tilt=10.0, mask=~inside)
    out = {"pole_lines": int(len(pa)), "reference_lines": int(len(ra)), "raw_deg": None, "reference_deg": None,
           "lean_deg": None, "corrected": False}
    if len(ra) >= min_reference:
        out["reference_deg"] = _wmedian(ra, rl)
        out["corrected"] = True
    if len(pa):
        out["raw_deg"] = _wmedian(pa, pl)
        out["lean_deg"] = out["raw_deg"] - (out["reference_deg"] if out["corrected"] else 0.0)
    return out


def main(argv=None):
    from PIL import Image
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("view")
    a.add_argument("box", type=float, nargs=4)
    a = a.parse_args(argv)
    g = np.asarray(Image.open(a.view).convert("L"), float) / 255.0
    print(json.dumps(pole_lean(g, a.box)))


if __name__ == "__main__":
    sys.exit(main())
