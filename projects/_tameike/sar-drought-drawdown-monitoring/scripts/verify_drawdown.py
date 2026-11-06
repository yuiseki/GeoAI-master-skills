"""Re-check the drawdown claims from what run_drawdown_experiments.py actually measured (outputs/pond_timeseries.json).

1. Is each window a water surface? A ledger pond whose storage / area gives a mean depth under 0.5 m has a placeholder
   area (1.0 km2 with 0.6 thousand m3), as does a storage of exactly 9999.9; and a window whose baseline water share (gamma0 < -14 dB) is under 50 % is
   mostly land: the change in such a window is not the pond's.
2. Is a pond's change larger than a water surface's own date-to-date change? The noise for a water surface is the
   permanent-water controls' change between the same two dates and their spread over all dates, not the forest's.
3. The rules as the plan fixed them (C2: k = 5, I > 0.25, p < 0.01; C4: against the share of all ledger ponds that
   have another pond within 300 m).

uvx --python 3.12 --with numpy --with duckdb --with scipy --with pyproj python scripts/verify_drawdown.py
"""

import json
from pathlib import Path

import duckdb
import numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree

PROJECT = Path(__file__).resolve().parent.parent
OUT = PROJECT / "outputs"
TAMEIKE = ("https://huggingface.co/datasets/yuiseki/maff-tameike-list-jp-2026-03/resolve/"
           "ee87755e53cf5b049b31bc307aca56ad950771cc/parquet/maff_tameike_ichiran_20260331.parquet")
BASE, PEAK = "2024-07-02", "2024-08-19"


def moran(vals, coords, k, n_perm=999, seed=42):
    n = len(vals)
    W = np.zeros((n, n))
    for i in range(n):
        d = np.hypot(*(coords - coords[i]).T)
        d[i] = np.inf
        W[i, np.argsort(d)[:k]] = 1.0 / k
    z = vals - vals.mean()
    stat = lambda z: (n / W.sum()) * (z @ W @ z) / (z @ z)
    i0 = stat(z)
    rng = np.random.default_rng(seed)
    perm = np.array([stat(rng.permutation(z)) for _ in range(n_perm)])
    return float(i0), float((1 + np.sum(perm >= i0)) / (n_perm + 1))


def main():
    T = json.loads((OUT / "pond_timeseries.json").read_text())
    dates = sorted({d for t in T for d in t["ts"]})

    # 2. water-surface noise from the permanent-water controls
    ctrl = {}
    for t in T:
        if t["tier"] == "CTRL_PERM_WATER":
            s = np.array([t["ts"][d]["vv_mean_db"] for d in dates if t["ts"].get(d)])
            ctrl[t["name"]] = dict(change_base_to_peak_db=round(t["ts"][PEAK]["vv_mean_db"] - t["ts"][BASE]["vv_mean_db"], 2),
                                   sd_over_dates_db=round(float(s.std(ddof=1)), 2),
                                   mean_db=round(float(s.mean()), 2))
    sd_water = float(np.mean([c["sd_over_dates_db"] for c in ctrl.values()]))
    noise_change = sd_water * np.sqrt(2)  # sd of a difference of two dates

    ponds = []
    for t in T:
        if "POND" not in t["tier"]:
            continue
        b, p = t["ts"].get(BASE), t["ts"].get(PEAK)
        area, vol = t["surface_area_km2"], t["storage_thousand_m3"]
        depth = vol * 1e3 / (area * 1e6) if area else None
        row = dict(name=t["name"], prefecture=t["prefecture"], municipality=t["municipality"], tier=t["tier"],
                   lat=t["lat"], lon=t["lon"], surface_area_km2=area, storage_thousand_m3=vol,
                   ledger_mean_depth_m=None if depth is None else round(depth, 3), observed=bool(b and p))
        if b and p:
            d = p["vv_mean_db"] - b["vv_mean_db"]
            row.update(base_water_pct=b["water_pct"], peak_water_pct=p["water_pct"], delta_db=round(d, 2),
                       z_vs_water_noise=round(d / noise_change, 2))
        row["placeholder_area"] = depth is not None and (depth < 0.5 or vol == 9999.9)
        row["window_is_water"] = bool(b) and b["water_pct"] >= 50.0
        row["usable"] = row["observed"] and not row["placeholder_area"] and row["window_is_water"]
        ponds.append(row)

    usable = [p for p in ponds if p["usable"]]
    observed = [p for p in ponds if p["observed"] and p["tier"] in ("POND_LARGE", "POND_MED")]

    def moran_rows(rows, k):
        if len(rows) <= k:
            return dict(n=len(rows), k=k, moran_i=None, p_value=None, note="too few ponds for k neighbours")
        i, pv = moran(np.array([r["delta_db"] for r in rows]), np.array([[r["lon"], r["lat"]] for r in rows]), k)
        return dict(n=len(rows), k=k, moran_i=round(i, 3), p_value=round(pv, 3), plan_rule="I > 0.25 and p < 0.01",
                    supported=bool(i > 0.25 and pv < 0.01))

    # 3. C4 baseline: share of all ledger ponds in the three prefectures with another pond within 300 m
    con = duckdb.connect()
    xy = np.array(con.execute(f"""select lon, lat from '{TAMEIKE}' where prefecture in ('香川県','兵庫県','広島県')
                                  and lat is not null and lon is not null""").fetchall())
    x, y = Transformer.from_crs("EPSG:4326", "EPSG:6690", always_xy=True).transform(xy[:, 0], xy[:, 1])
    tree = cKDTree(np.c_[x, y])
    counts = np.array([len(n) - 1 for n in tree.query_ball_point(np.c_[x, y], r=300.0)])
    base_share = float(np.mean(counts > 0))

    out = dict(
        dates=dict(base=BASE, peak=PEAK, all=dates),
        water_noise=dict(controls=ctrl, mean_sd_over_dates_db=round(sd_water, 2),
                         sd_of_two_date_change_db=round(noise_change, 2)),
        counts=dict(ponds_selected=len(ponds), observed=sum(p["observed"] for p in ponds),
                    placeholder_area=sum(p["placeholder_area"] for p in ponds),
                    window_not_water=sum(p["observed"] and not p["window_is_water"] for p in ponds),
                    usable=len(usable)),
        moran_plan_rule_all_observed=moran_rows(observed, 5),
        moran_plan_rule_usable=moran_rows(usable, 5),
        c4_baseline_share_with_pond_within_300m=round(base_share, 3),
        c4_baseline_n=int(len(counts)),
        ponds=ponds,
    )
    (OUT / "verify_drawdown.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "ponds"}, ensure_ascii=False, indent=1))
    for p in sorted(ponds, key=lambda p: -(p.get("delta_db") or -99)):
        print(p["tier"][5:], p["name"], p.get("delta_db"), p.get("z_vs_water_noise"), p.get("base_water_pct"),
              "placeholder" if p["placeholder_area"] else "", "usable" if p["usable"] else "")


if __name__ == "__main__":
    main()
