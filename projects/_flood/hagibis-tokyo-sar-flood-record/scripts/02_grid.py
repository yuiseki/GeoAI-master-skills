"""Stack the scenes of each orbit on one grid and put the other inputs on it.

env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA uvx --with rasterio --with numpy --with scipy --with shapely --with pyproj --with scikit-image python -u scripts/02_grid.py

Writes to artifacts/_flood/hagibis-tokyo-sar-flood-record/:
- stack_o46.npy, stack_o39.npy: float32 linear gamma0, shape (2 [vv, vh], ndate, rows, cols), the dates of
  common.SCENES in order; nan where missing (nodata or <= 0). Items of one date are merged (first valid value wins);
  every file must be on the same grid, the script stops otherwise.
- aux.npz: transform, wc (WorldCover 2021, nearest), tokyo (pixel centre in a Tokyo municipality of N03), rec (centre
  in a 2019 record polygon), a31a (centre in any A31a 想定最大規模 polygon), a31a_class (the largest depth class
  there, 0 outside), dist_tama (m, from the rasterised OSM 多摩川 lines, all touched), dist_rec (m, from rec), ward
  (N03_007 code of the pixel, 0 outside Tokyo)
and outputs/grid_summary.json: grid, scenes (date, role, platforms, items), missing counts, and for each orbit the shift
of the mean of the pre scenes (VV dB) against the WorldCover water mask (phase correlation), with the rule of the plan
(shift back by whole pixels when either component is over 1 pixel).
"""
import json
from collections import defaultdict

import numpy as np
import rasterio
import shapely
from pyproj import Transformer
from rasterio.features import rasterize
from rasterio.warp import Resampling, reproject
from scipy import ndimage

import flood
from common import ART, OUT, RAW, SCENES, UTM

TO_UTM = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)


def load_geoms(name):
    fc = json.loads((RAW / "vectors" / name).read_text(encoding="utf-8"))
    gs = shapely.from_geojson([json.dumps(f["geometry"]) for f in fc["features"]])
    gs = shapely.transform(gs, lambda xy: np.column_stack(TO_UTM.transform(xy[:, 0], xy[:, 1])))
    return gs, [f["properties"] for f in fc["features"]]


def main():
    items = json.loads((RAW / "rtc_items.json").read_text(encoding="utf-8"))
    groups = defaultdict(list)
    for it in items:
        groups[(it["properties"]["sat:relative_orbit"], it["properties"]["datetime"][:10])].append(it)
    ref = None
    for o, sc in SCENES.items():
        for _, d in sc:
            for it in groups[(o, d)]:
                for pol in ("vv", "vh"):
                    with rasterio.open(RAW / "rtc" / f"{it['id']}_{pol}.tif") as src:
                        g = (tuple(src.transform)[:6], src.shape)
                    if ref is None:
                        ref = g
                    elif g != ref:
                        raise RuntimeError(f"grid differs: {it['id']} {pol} {g} vs {ref}")
    transform = rasterio.Affine(*ref[0])
    rows, cols = ref[1]
    summary = {"grid": {"crs": UTM, "transform": list(ref[0]), "rows": rows, "cols": cols}, "orbits": {}}

    wc = np.zeros((rows, cols), np.uint8)
    with rasterio.open(RAW / "worldcover_2021.tif") as src:
        reproject(src.read(1), wc, src_transform=src.transform, src_crs=src.crs, dst_transform=transform, dst_crs=UTM,
                  resampling=Resampling.nearest)
    shape = (rows, cols)
    gs, props = load_geoms("tokyo.geojson")
    codes = [int(p["N03_007"]) for p in props]
    ward = rasterize(zip(gs, codes), out_shape=shape, transform=transform, fill=0, dtype="int32")
    tokyo = ward > 0
    gs, _ = load_geoms("rec_2019.geojson")
    rec = rasterize(((g, 1) for g in gs), out_shape=shape, transform=transform, fill=0, dtype="uint8").astype(bool)
    gs, props = load_geoms("a31a_max.geojson")
    order = np.argsort([p["class_code"] for p in props], kind="stable")  # larger classes drawn last win
    a31a_class = rasterize(((gs[i], int(props[i]["class_code"])) for i in order), out_shape=shape, transform=transform,
                           fill=0, dtype="uint8")
    gs, _ = load_geoms("tama.geojson")
    tama = rasterize(((g, 1) for g in gs), out_shape=shape, transform=transform, fill=0, dtype="uint8",
                     all_touched=True).astype(bool)
    dist_tama = ndimage.distance_transform_edt(~tama) * 10.0
    dist_rec = ndimage.distance_transform_edt(~rec) * 10.0
    np.savez_compressed(ART / "aux.npz", transform=np.array(ref[0]), wc=wc, tokyo=tokyo, rec=rec, a31a=a31a_class > 0,
                        a31a_class=a31a_class, dist_tama=dist_tama.astype(np.float32),
                        dist_rec=dist_rec.astype(np.float32), ward=ward)
    summary["pixels"] = {"tokyo": int(tokyo.sum()), "rec": int(rec.sum()), "rec_in_tokyo": int((rec & tokyo).sum()),
                         "a31a_in_tokyo": int((a31a_class > 0)[tokyo].sum()), "tama_line": int(tama.sum()),
                         "wc_water_in_tokyo": int((wc == 80)[tokyo].sum())}

    water = wc == 80
    for o, sc in SCENES.items():
        stack = np.lib.format.open_memmap(ART / f"stack_o{o}.npy", mode="w+", dtype=np.float32,
                                          shape=(2, len(sc), rows, cols))
        scenes = []
        for t, (role, d) in enumerate(sc):
            its = groups[(o, d)]
            for k, pol in enumerate(("vv", "vh")):
                out = np.full(shape, np.nan, np.float32)
                for it in its:
                    with rasterio.open(RAW / "rtc" / f"{it['id']}_{pol}.tif") as src:
                        a = src.read(1).astype(np.float32)
                        if src.nodata is not None:
                            a[a == src.nodata] = np.nan
                    a[~(a > 0)] = np.nan
                    out = np.where(np.isnan(out), a, out)
                stack[k, t] = out
            scenes.append({"date": d, "role": role, "datetimes": sorted(it["properties"]["datetime"] for it in its),
                           "platforms": sorted({it["properties"]["platform"] for it in its}),
                           "items": [it["id"] for it in its], "missing_vv_in_tokyo": int(np.isnan(stack[0, t])[tokyo].sum())})
            print(o, d, role, flush=True)
        stack.flush()
        pre = [t for t, (r, _) in enumerate(sc) if r == "pre"]
        pre_db = 10 * np.log10(np.nanmean(np.asarray(stack[0, pre], float), axis=0))
        s = flood.shift_against_mask(pre_db, water)
        summary["orbits"][str(o)] = {"scenes": scenes, "pre_vs_water_shift_rows_cols": [round(s[0], 3), round(s[1], 3)],
                                     "shift_back": [int(round(v)) for v in s] if max(abs(v) for v in s) > 1 else [0, 0]}
    (OUT / "grid_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "orbits"}, ensure_ascii=False))
    print({o: v["pre_vs_water_shift_rows_cols"] for o, v in summary["orbits"].items()})


if __name__ == "__main__":
    main()
