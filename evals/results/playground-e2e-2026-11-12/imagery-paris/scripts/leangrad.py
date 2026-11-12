"""Lean of a thin vertical object by shear search (alternative to Hough segments, which found no line on 65 % of
the pole boxes). The horizontal gradient of the box (+30 % of its width each side, middle 80 % of its height) is
sheared by each candidate angle; a straight edge at that angle collapses into one column, so the sum over columns of
(column sum of the signed gradient)^2 peaks. Angle from vertical in degrees, + = top to the right."""
import numpy as np
from scipy import ndimage as ndi

def lean_grad(gray, box, pad=0.3, trim=0.1, max_tilt=10.0, step=0.25, max_rows=400):
    h, w = gray.shape
    x0, y0, x1, y1 = box; bw, bh = x1 - x0, y1 - y0
    X0, X1 = int(max(0, x0 - pad * bw)), int(min(w, x1 + pad * bw))
    Y0, Y1 = int(max(0, y0 + trim * bh)), int(min(h, y1 - trim * bh))
    if X1 - X0 < 5 or Y1 - Y0 < 40: return None
    if Y1 - Y0 > max_rows:
        mid = (Y0 + Y1) // 2; Y0, Y1 = mid - max_rows // 2, mid + max_rows // 2
    g = ndi.gaussian_filter(gray.astype(float), 1.0)
    gx = ndi.sobel(g, axis=1)[Y0:Y1, X0:X1]
    H, W = gx.shape
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    yc = (H - 1) / 2
    angles = np.arange(-max_tilt, max_tilt + step / 2, step)
    sc = []
    for a in angles:
        # a line leaning by a (top to the right) passes x = x_c + (yc - y) tan a; sample at x + (yc - y) tan a
        src = xx - (yy - yc) * np.tan(np.radians(a))
        sh = ndi.map_coordinates(gx, [yy, src], order=1, mode="constant", cval=0.0)
        sc.append(float((sh.sum(axis=0) ** 2).sum()))
    sc = np.array(sc); i = int(np.argmax(sc))
    if 0 < i < len(sc) - 1:                        # parabola through the peak
        d = sc[i - 1] - 2 * sc[i] + sc[i + 1]
        off = 0.5 * (sc[i - 1] - sc[i + 1]) / d if d != 0 else 0.0
    else:
        off = 0.0
    return float(angles[i] + off * step)
