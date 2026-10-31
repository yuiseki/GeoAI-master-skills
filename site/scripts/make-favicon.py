"""Draw the site icon: a pixelated blue marble with "GeoAI" in a pixel font.

The icon is designed on a 32x32 grid, so it stays crisp when a browser shows it
at 16 or 32 pixels, and every larger size is the same grid scaled by an integer.
The globe is an orthographic view of Natural Earth 110m land centred on Japan.
Clouds come from fixed sine waves, not random noise, so the output only
changes when this script or the pinned land file changes.

Run from site/:
  uv run --no-project --with shapely --with pillow python3 scripts/make-favicon.py
"""

import hashlib
import json
import math
import urllib.request
from pathlib import Path

import numpy as np
import shapely
from PIL import Image

SITE = Path(__file__).resolve().parent.parent
LAND_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "ca96624a56bd078437bca8184e78163e5039ad19/geojson/ne_110m_land.geojson"
)
LAND_SHA256 = "9e0729ee253ca7d7a5c4ae9395fb1902264c5377c52e224d13dd85010e2835d9"
CACHE = Path("/tmp/geoai-site-cache/ne_110m_land.geojson")

GRID = 32
SAMPLES = 8  # per pixel side, to decide how much of a pixel is land or cloud
CENTER_LON, CENTER_LAT = 138.0, 22.0
RADIUS = 15.2  # in grid pixels; 15.5 leaves single pixels sticking out at the poles

OCEAN_DEEP, OCEAN_LIGHT = np.array([8, 34, 92]), np.array([38, 112, 190])
LAND_GREEN, LAND_DRY, ICE = np.array([58, 112, 58]), np.array([176, 150, 96]), np.array([236, 242, 246])
CLOUD = np.array([246, 248, 252])
TEXT, OUTLINE = (150, 240, 232, 255), (6, 26, 56, 255)

# 3x5 glyphs; "#" is ink.
GLYPHS = {
    "G": [".##", "#..", "#.#", "#.#", ".##"],
    "e": ["...", ".##", "###", "#..", ".##"],
    "o": ["...", ".#.", "#.#", "#.#", ".#."],
    "A": [".#.", "#.#", "###", "#.#", "#.#"],
    "I": ["###", ".#.", ".#.", ".#.", "###"],
}
WORD, TEXT_TOP = "GeoAI", 13


def land_geometry():
    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(LAND_URL, timeout=60) as response:
            CACHE.write_bytes(response.read())
    data = CACHE.read_bytes()
    if hashlib.sha256(data).hexdigest() != LAND_SHA256:
        raise SystemExit(f"{CACHE} does not match the pinned sha256; delete it and rerun")
    geoms = [shapely.geometry.shape(f["geometry"]) for f in json.loads(data)["features"]]
    land = shapely.union_all(geoms)
    shapely.prepare(land)
    return land


def globe() -> np.ndarray:
    """Return a GRID x GRID x 4 uint8 RGBA array."""
    n = GRID * SAMPLES
    coords = (np.arange(n) + 0.5) / SAMPLES  # sample centres in grid units
    x, y = np.meshgrid(coords - GRID / 2, coords - GRID / 2)
    u, v = x / RADIUS, -y / RADIUS
    rho2 = u * u + v * v
    inside = rho2 <= 1
    w = np.sqrt(np.clip(1 - rho2, 0, 1))

    # Inverse orthographic projection.
    lat0, lon0 = math.radians(CENTER_LAT), math.radians(CENTER_LON)
    lat = np.arcsin(np.clip(w * math.sin(lat0) + v * math.cos(lat0), -1, 1))
    lon = lon0 + np.arctan2(u, w * math.cos(lat0) - v * math.sin(lat0))
    lat_deg, lon_deg = np.degrees(lat), (np.degrees(lon) + 180) % 360 - 180

    is_land = np.zeros_like(inside)
    is_land[inside] = shapely.contains_xy(LAND, lon_deg[inside], lat_deg[inside])

    # Swirls of cloud from fixed waves; the storm belts sit near 45 degrees.
    waves = (np.sin(3 * lon + 2.4 * np.sin(2 * lat)) + np.sin(5 * lat + 1.7 * np.cos(2 * lon))
             + 0.8 * np.sin(7 * lon - 4 * lat))
    is_cloud = inside & (waves + 0.9 * np.cos(2 * lat) ** 2 < -1.15)

    def pool(a):
        return a.reshape(GRID, SAMPLES, GRID, SAMPLES).mean(axis=(1, 3))

    cover, land_f, cloud_f = pool(inside.astype(float)), pool(is_land.astype(float)), pool(is_cloud.astype(float))
    lat_px = pool(np.where(inside, np.abs(lat_deg), 0)) / np.maximum(cover, 1e-9)
    shade = pool(np.where(inside, w, 0)) / np.maximum(cover, 1e-9)
    # Light from the upper left.
    light = pool(np.where(inside, np.clip(0.55 * w - 0.45 * u + 0.45 * v, 0, None), 0)) / np.maximum(cover, 1e-9)

    ocean = OCEAN_DEEP + (OCEAN_LIGHT - OCEAN_DEEP) * shade[..., None] ** 0.8
    dry = np.clip(1 - np.abs(lat_px - 24) / 14, 0, 1)[..., None]
    land_c = LAND_GREEN + (LAND_DRY - LAND_GREEN) * dry
    land_c = np.where((lat_px > 62)[..., None], ICE, land_c)
    color = ocean * (1 - land_f[..., None]) + land_c * land_f[..., None]
    color = color * (1 - 0.85 * cloud_f[..., None]) + CLOUD * 0.85 * cloud_f[..., None]
    color = color * (0.45 + 0.75 * np.clip(light, 0, 1)[..., None])

    rgba = np.zeros((GRID, GRID, 4), dtype=np.uint8)
    rgba[..., :3] = np.clip(color, 0, 255).round().astype(np.uint8)
    rgba[..., 3] = np.where(cover >= 0.5, 255, 0)
    # A small specular highlight.
    rgba[8, 9, :3] = np.maximum(rgba[8, 9, :3], 200)
    return rgba


def draw_text(rgba: np.ndarray) -> None:
    width = len(WORD) * 4 - 1
    left = (GRID - width) // 2
    ink = set()
    for i, ch in enumerate(WORD):
        for r, row in enumerate(GLYPHS[ch]):
            for c, cell in enumerate(row):
                if cell == "#":
                    ink.add((TEXT_TOP + r, left + i * 4 + c))
    outline = {(r + dr, c + dc) for r, c in ink for dr in (-1, 0, 1) for dc in (-1, 0, 1)} - ink
    for r, c in outline:
        rgba[r, c] = OUTLINE
    for r, c in ink:
        rgba[r, c] = TEXT


def to_svg(rgba: np.ndarray) -> str:
    rects = []
    for r in range(GRID):
        c = 0
        while c < GRID:
            if rgba[r, c, 3] == 0:
                c += 1
                continue
            start, color = c, tuple(rgba[r, c, :3])
            while c < GRID and rgba[r, c, 3] and tuple(rgba[r, c, :3]) == color:
                c += 1
            rects.append(f'<rect x="{start}" y="{r}" width="{c - start}" height="1" fill="#{bytes(color).hex()}"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {GRID} {GRID}" '
            f'shape-rendering="crispEdges">' + "".join(rects) + "</svg>\n")


def scaled(rgba: np.ndarray, factor: int) -> Image.Image:
    return Image.fromarray(rgba).resize((GRID * factor, GRID * factor), Image.NEAREST)


def main() -> None:
    icon = globe()
    draw_text(icon)
    public = SITE / "public"
    (public / "favicon.svg").write_text(to_svg(icon), encoding="utf-8")
    scaled(icon, 1).save(public / "favicon-32.png", optimize=True)
    # iOS fills transparency with black, so the touch icon gets the page colour behind it.
    touch = Image.new("RGBA", (180, 180), (246, 247, 244, 255))
    touch.alpha_composite(scaled(icon, 5), (10, 10))
    touch.convert("RGB").save(public / "apple-touch-icon.png", optimize=True)
    for name in ("favicon.svg", "favicon-32.png", "apple-touch-icon.png"):
        print(name, (public / name).stat().st_size, "bytes")


LAND = land_geometry()

if __name__ == "__main__":
    main()
