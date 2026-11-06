"""Probe script for tameike cascade dam-break routing with 5m DEM (GSI DEM5A z15).

Measures:
1. GSI DEM5A z15 coverage and HTTP status across Awaji (Hyogo) and Sanuki (Kagawa).
2. Longitudinal elevation cross-sections (5m resolution) along concrete cascade chains.
3. Physical resolution of dam crests, downstream steep faces, and water surface NaN masking.
4. Topographic implications for D8 flow routing and breach modeling.
"""
import json
import math
import urllib.request
from pathlib import Path
import numpy as np

OUTPUT_JSON = Path(__file__).resolve().parent / "probe_cascade_5m_dem.json"

def lonlat_to_global_pixel(lon, lat, z, size=256):
    n = size * (2 ** z)
    x = (lon + 180) / 360 * n
    lat_rad = math.radians(lat)
    y = (1 - math.asinh(math.tan(lat_rad)) / math.pi) / 2 * n
    return x, y

def metres_per_pixel(lat, z, size=256):
    return 2 * math.pi * 6378137 * math.cos(math.radians(lat)) / (size * (2 ** z))

def fetch_gsi_tile(layer, z, x, y):
    url = f"https://cyberjapandata.gsi.go.jp/xyz/{layer}/{z}/{x}/{y}.txt"
    req = urllib.request.Request(url, headers={"User-Agent": "GeoAI-Probe/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8")
        rows = [line.split(",") for line in text.strip().split("\n")]
        arr = np.array([[np.nan if v == "e" else float(v) for v in r] for r in rows])
        return 200, arr
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return str(e), None

def main():
    print("=== Probing 5m DEM (GSI DEM5A z15) for Tameike Cascade Dam-Break Routing ===")
    
    test_points = [
        {"name": "淡路市 上那木池", "lat": 34.45322, "lon": 134.81372, "role": "upper_head"},
        {"name": "淡路市 下那木新池", "lat": 34.45625, "lon": 134.81331, "role": "downstream"},
        {"name": "淡路市 深山池", "lat": 34.45350, "lon": 134.81725, "role": "upper_head"},
        {"name": "淡路市 深山下池", "lat": 34.45433, "lon": 134.81719, "role": "downstream"},
        {"name": "香川県 まんのう町 満濃池", "lat": 34.162, "lon": 133.874, "role": "large_head"},
        {"name": "香川県 高松市 三郎池", "lat": 34.281, "lon": 134.074, "role": "large_head"},
    ]

    results = {
        "dem_comparison": {},
        "cascade_profiles": [],
        "nan_masking_audit": {}
    }

    # 1. Compare DEM layers: dem5a (z15, 5m), dem5b (z15), dem (z14, 10m)
    print("\n1. Checking tile availability:")
    for pt in test_points:
        pt_res = {}
        for layer, z in [("dem5a", 15), ("dem5b", 15), ("dem", 14)]:
            gx, gy = lonlat_to_global_pixel(pt["lon"], pt["lat"], z)
            tx, ty = int(gx // 256), int(gy // 256)
            code, arr = fetch_gsi_tile(layer, z, tx, ty)
            m_pix = metres_per_pixel(pt["lat"], z)
            valid_pct = float(np.sum(~np.isnan(arr)) / arr.size * 100) if arr is not None else 0.0
            pt_res[f"{layer}_z{z}"] = {
                "status": code,
                "tile_x": tx,
                "tile_y": ty,
                "metres_per_pixel": round(m_pix, 2),
                "valid_pct": round(valid_pct, 2)
            }
            print(f"  {pt['name']} | {layer} z{z}: status {code}, {m_pix:.2f} m/pix, valid {valid_pct:.1f}%")
        results["dem_comparison"][pt["name"]] = pt_res

    # 2. Extract 5m longitudinal profile along concrete cascade chain:
    # Miyama-ike (upper) -> Miyama-shimo-ike (lower)
    print("\n2. Extracting 5m profile: 深山池 -> 深山下池 (距離 ~110m, 落差 ~7m):")
    z = 15
    gx1, gy1 = lonlat_to_global_pixel(134.81725, 34.45350, z)
    gx2, gy2 = lonlat_to_global_pixel(134.81719, 34.45433, z)
    tx, ty = int(gx1 // 256), int(gy1 // 256)
    code, arr5a = fetch_gsi_tile("dem5a", z, tx, ty)
    code_10b, arr10b = fetch_gsi_tile("dem", 14, int(gx1 // 512), int(gy1 // 512)) # 10m tile

    px1, py1 = int(gx1 % 256), int(gy1 % 256)
    px2, py2 = int(gx2 % 256), int(gy2 % 256)
    d_pix = math.hypot(px2 - px1, py2 - py1)
    m_per_pix = metres_per_pixel(34.4535, z)

    profile_samples = []
    for step in range(int(d_pix) + 1):
        alpha = step / d_pix
        cx = int(round(px1 + alpha * (px2 - px1)))
        cy = int(round(py1 + alpha * (py2 - py1)))
        elev5a = float(arr5a[cy, cx]) if not np.isnan(arr5a[cy, cx]) else None
        dist_m = round(step * m_per_pix, 1)
        profile_samples.append({
            "step": step,
            "dist_m": dist_m,
            "px": cx,
            "py": cy,
            "elev_5m_m": elev5a
        })
        elev_str = f"{elev5a:5.2f}m" if elev5a is not None else "  NaN (Water/Mask)"
        print(f"  Step {step:2d} ({dist_m:5.1f}m) [px {cx},{cy}]: Elev = {elev_str}")

    results["cascade_profiles"].append({
        "chain_name": "淡路市 深山池 -> 深山下池",
        "upper": "深山池 (貯水量 16.0k m³, 堤高 4.5m)",
        "lower": "深山下池 (貯水量 3.0k m³, 堤高 3.1m)",
        "pixel_resolution_m": round(m_per_pix, 2),
        "total_distance_m": round(d_pix * m_per_pix, 1),
        "profile": profile_samples
    })

    # 3. Waterbody NaN mask analysis in 5m DEM
    print("\n3. Analyzing NaN masking behavior in 5m DEM5A:")
    import scipy.ndimage as ndi
    nan_mask = np.isnan(arr5a)
    lbl, n_clusters = ndi.label(nan_mask)
    cluster_sizes = [int(np.sum(lbl == i)) for i in range(1, n_clusters + 1)]
    cluster_areas_m2 = [round(sz * (m_per_pix ** 2), 1) for sz in cluster_sizes]
    
    print(f"  Tile ({tx}, {ty}): Total pixels=65,536, NaN pixels={int(np.sum(nan_mask))} ({np.sum(nan_mask)/65536*100:.2f}%)")
    print(f"  Distinct NaN waterbody clusters: {n_clusters}")
    print(f"  Top 5 waterbody cluster sizes: {sorted(cluster_sizes, reverse=True)[:5]} pixels")
    print(f"  Top 5 waterbody cluster areas: {sorted(cluster_areas_m2, reverse=True)[:5]} m²")

    results["nan_masking_audit"] = {
        "tile": f"{tx}_{ty}",
        "total_pixels": 65536,
        "nan_pixels": int(np.sum(nan_mask)),
        "nan_pct": round(float(np.sum(nan_mask)/65536*100), 2),
        "n_waterbody_clusters": n_clusters,
        "top_cluster_sizes_pixels": sorted(cluster_sizes, reverse=True)[:10],
        "top_cluster_areas_m2": sorted(cluster_areas_m2, reverse=True)[:10]
    }

    OUTPUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nProbe successfully recorded to: {OUTPUT_JSON}")

if __name__ == "__main__":
    main()
