"""How a map's classes look to readers with colour-vision deficiency: simulate protan, deutan and tritan vision
and measure whether neighbouring classes stay apart and whether lightness keeps the values' order.

    simulate   Machado, Oliveira and Fernandes (2009)'s matrices at full severity, applied to linear sRGB, then
               back to sRGB (clipped to the gamut)
    lab        CIELAB (D65) from sRGB
    report     for each vision (normal, protan, deutan, tritan): the smallest colour difference between
               neighbouring classes (CIE76 Delta E in CIELAB) and whether L* rises (or falls) steadily with the
               class, which a sequential palette needs

A Delta E near 2 is at the edge of what people tell apart side by side; classes on a map are seen apart and
small, so they need much more. The script prints the numbers and the pairs; it does not fix a pass mark.

Usage:
    uvx --with numpy --with matplotlib python cvd.py --palette viridis --k 7
    uvx --with numpy --with matplotlib python cvd.py --colors '#d73027,#fc8d59,#fee08b,#91cf60,#1a9850'
"""

import argparse

import numpy as np

MACHADO = {
    "protan": np.array([[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216],
                        [-0.003882, -0.048116, 1.051998]]),
    "deutan": np.array([[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413],
                        [-0.011820, 0.042940, 0.968881]]),
    "tritan": np.array([[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602],
                        [0.004733, 0.691367, 0.303900]]),
}


def to_linear(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def to_srgb(c):
    c = np.clip(np.asarray(c, float), 0, 1)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055)


def simulate(rgb, kind):
    """rgb: (n, 3) sRGB in 0..1."""
    if kind == "normal":
        return np.asarray(rgb, float)
    return to_srgb(to_linear(rgb) @ MACHADO[kind].T)


def lab(rgb):
    M = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = to_linear(rgb) @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.c_[116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])]


def report(rgb, diverging=False):
    """Per vision: the smallest neighbour Delta E and its pair, and whether L* is monotone (sequential) or falls
    to a single extreme in the middle (diverging)."""
    out = {}
    for kind in ("normal", "protan", "deutan", "tritan"):
        L = lab(simulate(rgb, kind))
        d = np.sqrt(((L[1:] - L[:-1]) ** 2).sum(1))
        j = int(np.argmin(d))
        steps = np.diff(L[:, 0])
        if diverging:
            mid = int(np.argmax(L[:, 0]))
            ordered = bool(np.all(np.diff(L[:mid + 1, 0]) > 0) and np.all(np.diff(L[mid:, 0]) < 0))
        else:
            ordered = bool(np.all(steps > 0) or np.all(steps < 0))
        out[kind] = {"min_delta_e": float(d[j]), "pair": (j, j + 1), "lightness_ordered": ordered,
                     "ends_delta_e": float(np.sqrt(((L[0] - L[-1]) ** 2).sum()))}
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--palette", help="a matplotlib colormap name, sampled at the class centres")
    p.add_argument("--k", type=int, default=7)
    p.add_argument("--colors", help="comma-separated hex colours, in class order")
    p.add_argument("--diverging", action="store_true", help="lightness peaks in the middle class")
    a = p.parse_args()
    if bool(a.palette) == bool(a.colors):
        p.error("give --palette or --colors")
    if a.palette:
        import matplotlib

        cmap = matplotlib.colormaps[a.palette]
        rgb = np.array([cmap((i + 0.5) / a.k)[:3] for i in range(a.k)])
        label = f"{a.palette}, {a.k} classes"
    else:
        hexes = [h.strip().lstrip("#") for h in a.colors.split(",")]
        rgb = np.array([[int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)] for h in hexes])
        label = f"{len(hexes)} colours"
    print(label)
    for kind, r in report(rgb, a.diverging).items():
        print(f"  {kind:7s} smallest neighbour Delta E {r['min_delta_e']:6.1f} (classes {r['pair'][0] + 1} and "
              f"{r['pair'][1] + 1}); ends {r['ends_delta_e']:6.1f}; lightness in order: {r['lightness_ordered']}")


if __name__ == "__main__":
    main()
