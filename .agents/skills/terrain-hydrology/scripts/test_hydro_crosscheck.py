"""uvx --python 3.12 --with pyflwdir --with numpy --with rasterio --with pyproj --with whitebox_workflows --with geopandas --with pytest pytest test_hydro_crosscheck.py

hydro.py against Whitebox Workflows (whitebox_workflows, the Python front end of whitebox_next_gen) on the synthetic
surfaces, and a trap of whitebox_workflows pinned so that a fix upstream shows up here. With GEOAI_REALDATA=1, the
catchments of three dams on the Sagami against the areas MLIT publishes (reads AW3D30 v4.1 from JAXA Earth).
"""

import csv
import os
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from hydro import flow, run
from test_hydro import TR, boxed_valley, points_csv, valley, write

wbw = pytest.importorskip("whitebox_workflows")

# whitebox's default pointer codes (1 NE, 2 E, 4 SE, 8 S, 16 SW, 32 W, 64 NW, 128 N) to pyflwdir's d8 codes
WB_TO_PYFLWDIR = {1: 128, 2: 1, 4: 2, 8: 4, 16: 8, 32: 16, 64: 32, 128: 64}


def hy():
    env = wbw.WbEnvironment()
    env.verbose = False
    return env.hydrology


def read1(path):
    with rasterio.open(path) as s:
        return s.read(1), s.nodata


def test_d8_matches_whitebox_on_slopes(tmp_path):
    z = valley(pit=False)
    write(tmp_path / "d.tif", z)
    h = hy()
    h.d8_pointer(dem=str(tmp_path / "d.tif"), output=str(tmp_path / "p.tif"))
    wp, _ = read1(tmp_path / "p.tif")
    _, d8, _ = flow(z, TR)
    inner = (slice(1, -1), slice(1, -1))
    mapped = np.vectorize(lambda v: WB_TO_PYFLWDIR.get(int(v), -1))(wp[inner])
    assert np.array_equal(mapped, d8[inner])


def test_catchments_match_whitebox(tmp_path):
    import geopandas as gpd
    from shapely.geometry import Point

    z = boxed_valley()
    hgt, w = z.shape
    write(tmp_path / "d.tif", z)
    pts = {"in": (hgt - 5, w // 2), "mid": (20, w // 2)}
    out = {o["id"]: o for o in run(tmp_path / "d.tif", tmp_path / "o.tif", points_csv(tmp_path / "p.csv", pts),
                                   snap_m=0, snap_min_km2=0)}
    h = hy()
    h.fill_depressions(dem=str(tmp_path / "d.tif"), output=str(tmp_path / "f.tif"))
    h.d8_pointer(dem=str(tmp_path / "f.tif"), output=str(tmp_path / "p.tif"))
    for pid, (r, c) in pts.items():
        x, y = TR * (c + 0.5, r + 0.5)
        gpd.GeoDataFrame({"id": [1]}, geometry=[Point(x, y)], crs="EPSG:32654").to_file(tmp_path / f"{pid}.gpkg")
        h.watershed(d8_pntr=str(tmp_path / "p.tif"), pour_pts=str(tmp_path / f"{pid}.gpkg"), output=str(tmp_path / f"{pid}.tif"))
        ws, nd = read1(tmp_path / f"{pid}.tif")
        assert int(((ws != nd) & (ws > 0)).sum()) == out[pid]["catchment_cells"]


def test_whitebox_accumulation_from_a_pointer_saturates_at_int16(tmp_path):
    """Trap (whitebox_workflows 2.0.6): d8_flow_accum with input_is_pointer=True stops at 32767 cells with no warning,
    in a float32 file. From the DEM it does not. If this test fails, the trap may be fixed: update references/pitfalls.md."""
    n = 200
    r, c = np.indices((n, n))
    z = (n - 1 - r) * 1.0 + np.abs(c - n // 2) * 2.0 + 10  # a valley draining to the bottom centre, 40,000 cells
    write(tmp_path / "d.tif", z)
    h = hy()
    h.d8_pointer(dem=str(tmp_path / "d.tif"), output=str(tmp_path / "p.tif"))
    h.d8_flow_accum(input=str(tmp_path / "p.tif"), input_is_pointer=True, out_type="cells", output=str(tmp_path / "ap.tif"))
    h.d8_flow_accum(input=str(tmp_path / "d.tif"), out_type="cells", output=str(tmp_path / "ad.tif"))
    ap, _ = read1(tmp_path / "ap.tif")
    ad, _ = read1(tmp_path / "ad.tif")
    assert ad.max() == n * n
    assert ap.max() == 32767


SAGAMI_DAMS = {  # OSM waterway=dam (nominatim.yuiseki.net, 2026-11-06); areas: MLIT Sagami overview p.70-71
    "sagami": (139.1961592, 35.6153147, 1016.0),
    "shiroyama": (139.2834642, 35.5857198, 1221.3),
    "doshi": (139.1334730, 35.5504626, 112.5),
}
AW3D30 = ("https://s3.ap-northeast-1.wasabisys.com/je-pds/cog/v1/JAXA.EORC_ALOS.PRISM_AW3D30.v4.1_global/2024-04/3/"
          "{band}/{tile}-DSM.tiff")


# Lakes on the north foot of Fuji with no surface outlet. Kawaguchi is left out: since 1994 the Usobuki floodway joins
# it to the Miya, a tributary of the Katsura (the Sagami upstream), and MLIT's overview treats its floods as the
# basin's (p.54-64). Whether MLIT's areas count Saiko, Shoji and Motosu was not found in the overview: unconfirmed.
CLOSED_LAKES = {"saiko": (138.685, 35.499), "shoji": (138.605, 35.488), "motosu": (138.585, 35.465)}
BOUNDS = (138.55, 35.25, 139.45, 35.85)  # a narrower box (138.70-139.35, 35.35-35.75) cuts the two large catchments


def aw3d30_utm(bounds, path):
    from rasterio.crs import CRS
    from rasterio.merge import merge
    from rasterio.warp import Resampling, calculate_default_transform, reproject

    urls = [AW3D30.format(band=f"E{lo:03d}.00-E{lo + 1:03d}.00", tile=f"E{lo:03d}.00-N{la:02d}.00-E{lo + 1:03d}.00-N{la + 1:02d}.00")
            for lo in range(int(np.floor(bounds[0])), int(np.ceil(bounds[2])))
            for la in range(int(np.floor(bounds[1])), int(np.ceil(bounds[3])))]
    a, tr = merge([rasterio.open(u) for u in urls], bounds=bounds)
    ll, utm = CRS.from_epsg(4326), CRS.from_epsg(32654)
    t2, w2, h2 = calculate_default_transform(ll, utm, a.shape[2], a.shape[1], *bounds, resolution=30)
    b = np.full((h2, w2), -9999, "float32")
    reproject(a[0].astype("float32"), b, src_transform=tr, src_crs=ll, dst_transform=t2, dst_crs=utm,
              resampling=Resampling.bilinear, src_nodata=-9999, dst_nodata=-9999)
    return write(path, b, transform=t2)


def lonlat_csv(path, pts):
    with open(path, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["id", "x", "y"])
        for k, v in pts.items():
            wr.writerow([k, v[0], v[1]])
    return path


@pytest.mark.skipif(os.environ.get("GEOAI_REALDATA") != "1", reason="set GEOAI_REALDATA=1 to read AW3D30 from JAXA Earth")
def test_sagami_dam_catchments_against_mlit(tmp_path):
    dem = aw3d30_utm(BOUNDS, tmp_path / "dem.tif")
    dams = lonlat_csv(tmp_path / "dams.csv", SAGAMI_DAMS)
    plain = {o["id"]: o for o in run(dem, tmp_path / "a.tif", dams, points_crs="EPSG:4326", snap_m=300, snap_min_km2=50)}
    out = run(dem, tmp_path / "b.tif", dams, points_crs="EPSG:4326", snap_m=300, snap_min_km2=50,
              sinks=lonlat_csv(tmp_path / "sinks.csv", CLOSED_LAKES))
    for o in out:
        ref = SAGAMI_DAMS[o["id"]][2]
        err = (o["catchment_km2"] - ref) / ref
        err0 = (plain[o["id"]]["catchment_km2"] - ref) / ref
        print(o["id"], "MLIT", ref, "lakes filled", plain[o["id"]]["catchment_km2"], f"{100 * err0:+.2f}%",
              "lakes as sinks", o["catchment_km2"], f"{100 * err:+.2f}%", "snap", o["snap_m"], "m")
        assert o["snapped"] and o["edge_cells"] == 0
        assert abs(err) < 0.04
