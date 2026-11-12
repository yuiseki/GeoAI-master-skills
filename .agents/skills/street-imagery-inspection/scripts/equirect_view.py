"""Cut a perspective (pinhole) view out of a 360-degree equirectangular image.

    uvx --with numpy --with pillow python equirect_view.py PANO.jpg OUT.jpg --yaw 90 --pitch 0 --fov 60 --size 800 800

Angles in degrees. yaw is measured clockwise from the image centre column (in street-level 360 captures the
centre faces the capture direction, so the view faces azimuth + yaw); pitch is up from the image's horizon row.
The equirectangular image is assumed level (its middle row is the horizon). If the camera was rolled or pitched,
world-vertical lines lean in every view by the same small angle: measure leans against other vertical lines of the
same view, not against the image edge.

In a level view (pitch 0) every world-vertical line projects to a vertical image line, wherever it is in the
view. That is what makes lean measurable in such a view; at another pitch, verticals converge to a vanishing point.
Sampling is bilinear.
"""

import argparse
import math
import sys

import numpy as np


def perspective(img, yaw, pitch, fov, size):
    """img: H x W x C (uint8) equirectangular. size: (width, height) of the view. fov: horizontal, degrees."""
    h, w = img.shape[:2]
    vw, vh = size
    f = (vw / 2) / math.tan(math.radians(fov) / 2)
    xs = np.arange(vw) - (vw - 1) / 2
    ys = np.arange(vh) - (vh - 1) / 2
    X, Y = np.meshgrid(xs, ys)
    # Camera frame: x right, y down, z forward. Rotate by pitch (about x), then yaw (about the vertical).
    d = np.stack([X, Y, np.full_like(X, f)], axis=-1)
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    p, t = -math.radians(pitch), math.radians(yaw)      # pitch up turns the ray towards -y (up)
    rx = np.array([[1, 0, 0], [0, math.cos(p), math.sin(p)], [0, -math.sin(p), math.cos(p)]])
    ry = np.array([[math.cos(t), 0, math.sin(t)], [0, 1, 0], [-math.sin(t), 0, math.cos(t)]])
    d = d @ rx.T @ ry.T
    lon = np.arctan2(d[..., 0], d[..., 2])                # 0 at the image centre, positive to the right
    lat = -np.arcsin(np.clip(d[..., 1], -1, 1))           # positive up
    u = (lon / (2 * math.pi) + 0.5) * w - 0.5
    v = (0.5 - lat / math.pi) * h - 0.5
    return _bilinear(img, u, v)


def _bilinear(img, u, v):
    h, w = img.shape[:2]
    u0 = np.floor(u).astype(int)
    v0 = np.clip(np.floor(v).astype(int), 0, h - 1)
    du, dv = (u - u0)[..., None], (v - np.floor(v))[..., None]
    u1, v1 = (u0 + 1) % w, np.clip(v0 + 1, 0, h - 1)
    u0 %= w
    im = img.astype(np.float32)
    out = (im[v0, u0] * (1 - du) * (1 - dv) + im[v0, u1] * du * (1 - dv) + im[v1, u0] * (1 - du) * dv
           + im[v1, u1] * du * dv)
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)


def heading_of_column(azimuth, yaw, x, width, fov):
    """Compass heading (degrees) faced by view column x, for a capture whose image centre faces azimuth."""
    f = (width / 2) / math.tan(math.radians(fov) / 2)
    return (azimuth + yaw + math.degrees(math.atan((x - (width - 1) / 2) / f))) % 360


def main(argv=None):
    from PIL import Image
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("pano")
    a.add_argument("out")
    a.add_argument("--yaw", type=float, default=0.0)
    a.add_argument("--pitch", type=float, default=0.0)
    a.add_argument("--fov", type=float, default=60.0)
    a.add_argument("--size", type=int, nargs=2, default=[800, 800])
    a = a.parse_args(argv)
    img = np.asarray(Image.open(a.pano).convert("RGB"))
    Image.fromarray(perspective(img, a.yaw, a.pitch, a.fov, tuple(a.size))).save(a.out, quality=92)


if __name__ == "__main__":
    sys.exit(main())
