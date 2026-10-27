"""Rank 1 km meshes by potential demand and compare daytime vs residential readings.

Reads artifacts/tokyo23-daytime-evac-stress/{mesh_dataset,blocks}.parquet and writes
outputs/analysis_results.json plus the top lists as CSV.

Run: ~/.venvs/geoai/bin/python scripts/analyze.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
ART = ROOT / "artifacts" / "tokyo23-daytime-evac-stress"
OUT = PROJECT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

TOP_N = 20


def top(df, col, n=TOP_N):
    return df.sort_values([col, "mesh1kmid"], ascending=[False, True]).head(n)


def ids(df):
    return set(df.mesh1kmid)


def overlap(a, b):
    return len(ids(a) & ids(b))


def rho(a, b):
    ok = a.notna() & b.notna()
    if ok.sum() < 3:
        return None
    return float(spearmanr(a[ok], b[ok]).statistic)


def main():
    mesh = pd.read_parquet(ART / "mesh_dataset.parquet")
    blocks = pd.read_parquet(ART / "blocks.parquet")
    mesh["night"] = mesh["night"].astype(int)
    mesh["day19"] = mesh["day19"].astype(int)
    mesh["day21"] = mesh["day21"].astype(int)

    finite = mesh[mesh.sh_1000 > 0].copy()
    finite["night_ratio"] = finite.night / finite.sh_1000
    finite["day_ratio"] = finite.day19 / finite.sh_1000
    finite["delta"] = finite.day_ratio - finite.night_ratio
    finite["rel"] = np.where(finite.night_ratio > 0, finite.day_ratio / finite.night_ratio, np.nan)
    finite["day21_ratio"] = finite.day21 / finite.sh_1000
    zero = mesh[mesh.sh_1000 == 0].copy()

    day_top = top(finite, "day_ratio")
    night_top = top(finite, "night_ratio")
    delta_top = top(finite, "delta")
    daypop_top = top(finite, "day19")
    rel_top = top(finite.assign(rel_floor=finite.rel.where(finite.night >= 100)), "rel_floor")

    res = {}
    res["universe"] = {
        "meshes": int(len(mesh)),
        "finite_meshes": int(len(finite)),
        "zero_shelter_meshes": int(len(zero)),
        "night_total": int(mesh.night.sum()),
        "day19_total": int(mesh.day19.sum()),
        "day21_total": int(mesh.day21.sum()),
        "census_rows": int(mesh.census_row.sum()),
        "day19_rows": int(mesh.day19_row.sum()),
        "day21_rows": int(mesh.day21_row.sum()),
        "eq_published_meshes": int(mesh.eq_published.sum()),
        "eq_published_wards": int(mesh.loc[mesh.eq_published, "ward"].nunique()),
        "no_shelter_within_5km": int(mesh.nearest_sh_m.isna().sum()),
    }

    res["C1_day_vs_night_top20"] = {
        "overlap": overlap(day_top, night_top),
        "union": len(ids(day_top) | ids(night_top)),
        "spearman_all_finite": rho(finite.day_ratio, finite.night_ratio),
    }
    res["C2_day_ratio_vs_day_population_top20"] = {
        "overlap": overlap(day_top, daypop_top),
        "spearman_all_finite": rho(finite.day_ratio, finite.day19),
    }
    res["other_rank_relations"] = {
        "delta_vs_day_ratio_top20_overlap": overlap(delta_top, day_top),
        "delta_vs_day_population_top20_overlap": overlap(delta_top, daypop_top),
        "day_ratio_vs_night_population_spearman": rho(finite.day_ratio, finite.night),
        "night_ratio_vs_night_population_spearman": rho(finite.night_ratio, finite.night),
    }

    worst = finite.sort_values(["delta", "mesh1kmid"], ascending=[False, True]).iloc[0]
    res["most_worsened"] = {
        "mesh1kmid": worst.mesh1kmid,
        "ward": worst.ward,
        "lon": float(worst.lon),
        "lat": float(worst.lat),
        "night": int(worst.night),
        "day19": int(worst.day19),
        "shelters_1km": int(worst.sh_1000),
        "night_ratio": float(worst.night_ratio),
        "day_ratio": float(worst.day_ratio),
        "delta": float(worst.delta),
    }
    finite["delta21"] = finite.day21_ratio - finite.night_ratio
    w21 = finite.sort_values(["delta21", "mesh1kmid"], ascending=[False, True]).iloc[0]
    res["most_worsened_2021"] = {
        "mesh1kmid": w21.mesh1kmid,
        "ward": w21.ward,
        "day21_ratio": float(w21.day21_ratio),
        "delta21": float(w21.delta21),
    }

    # Top-20 ward composition
    res["day_ratio_top20_wards"] = day_top.ward.value_counts().to_dict()
    res["delta_top20_wards"] = delta_top.ward.value_counts().to_dict()
    res["night_ratio_top20_wards"] = night_top.ward.value_counts().to_dict()

    # Relative reading
    rel_top_all = top(finite.assign(rel_ok=finite.rel), "rel_ok")
    res["relative_reading"] = {
        "top_mesh": rel_top_all.iloc[0].mesh1kmid,
        "top_ward": rel_top_all.iloc[0].ward,
        "top_night": int(rel_top_all.iloc[0].night),
        "top_day19": int(rel_top_all.iloc[0].day19),
        "top_ratio": float(rel_top_all.iloc[0].rel),
        "top20_with_night_ge_100": [str(m) for m in rel_top.mesh1kmid],
    }

    # Zero-shelter group
    zero["day_change"] = zero.day19 - zero.night
    zero_top = zero.sort_values(["day19", "mesh1kmid"], ascending=[False, True]).head(10)
    res["zero_shelter_group"] = {
        "count": int(len(zero)),
        "top_by_day19": zero_top[["mesh1kmid", "ward", "night", "day19", "nearest_sh_m"]]
        .assign(nearest_sh_m=lambda d: d.nearest_sh_m.round(0))
        .to_dict(orient="records"),
        "wards": zero.ward.value_counts().to_dict(),
    }

    # Radius variants, including where the main top mesh lands at each radius
    finite["rank_day_ratio"] = finite.day_ratio.rank(ascending=False, method="min")
    finite["rank_night_ratio"] = finite.night_ratio.rank(ascending=False, method="min")
    radius = {}
    radius_detail = {}
    for r in (500, 1000, 1500):
        col = f"sh_{r}"
        sub = mesh[mesh[col] > 0].copy()
        sub["day_ratio"] = sub.day19 / sub[col]
        sub["night_ratio"] = sub.night / sub[col]
        sub["delta"] = sub.day_ratio - sub.night_ratio
        t = top(sub, "day_ratio")
        both = finite.merge(sub[["mesh1kmid", "day_ratio"]], on="mesh1kmid",
                            suffixes=("", f"_{r}"))
        radius[r] = {
            "finite_meshes": int(len(sub)),
            "zero_meshes": int((mesh[col] == 0).sum()),
            "top20_overlap_with_1000": overlap(day_top, t),
            "spearman_day_ratio_vs_1000": rho(both.day_ratio, both[f"day_ratio_{r}"]),
        }
        ranked = sub.sort_values(["delta", "mesh1kmid"], ascending=[False, True]) \
                    .reset_index(drop=True)
        main_row = ranked[ranked.mesh1kmid == res["most_worsened"]["mesh1kmid"]]
        radius_detail[str(r)] = {
            "top_delta_mesh": ranked.iloc[0].mesh1kmid,
            "top_delta_ward": ranked.iloc[0].ward,
            "top_delta": float(ranked.iloc[0].delta),
            "top5_day_ratio": [
                {"mesh1kmid": x.mesh1kmid, "ward": x.ward,
                 "day_ratio": float(x.day_ratio), "shelters": int(getattr(x, col))}
                for x in t.head(5).itertuples()
            ],
            "main_top_shelters": None if main_row.empty else int(getattr(main_row.iloc[0], col)),
            "main_top_delta": None if main_row.empty else float(main_row.iloc[0].delta),
            "main_top_delta_rank": None if main_row.empty else int(main_row.index[0]) + 1,
        }
    res["C3_radius"] = radius
    res["radius_detail"] = radius_detail

    wm = res["most_worsened"]["mesh1kmid"]
    wrow = finite[finite.mesh1kmid == wm].iloc[0]
    nrow = finite[finite.mesh1kmid == night_top.iloc[0].mesh1kmid].iloc[0]
    res["rank_swap"] = {
        "worst_mesh": wm,
        "worst_night_rank": int(wrow.rank_night_ratio),
        "worst_day_rank": int(wrow.rank_day_ratio),
        "night_top_mesh": nrow.mesh1kmid,
        "night_top_ward": nrow.ward,
        "night_top_night_rank": int(nrow.rank_night_ratio),
        "night_top_day_rank": int(nrow.rank_day_ratio),
    }

    # Year variant
    t21 = top(finite, "day21_ratio")
    res["C4_year"] = {
        "top20_overlap_2019_2021": overlap(day_top, t21),
        "spearman_day_ratio_2019_2021": rho(finite.day_ratio, finite.day21_ratio),
        "day19_total": int(mesh.day19.sum()),
        "day21_total": int(mesh.day21.sum()),
    }

    # Facility scope variant
    sub23 = mesh[mesh.sh_1000_23 > 0].copy()
    sub23["day_ratio"] = sub23.day19 / sub23.sh_1000_23
    t23 = top(sub23, "day_ratio")
    both23 = finite.merge(sub23[["mesh1kmid", "day_ratio"]], on="mesh1kmid", suffixes=("", "_23"))
    res["facility_scope"] = {
        "finite_meshes_23only": int(len(sub23)),
        "zero_meshes_23only": int((mesh.sh_1000_23 == 0).sum()),
        "top20_overlap_with_all": overlap(day_top, t23),
        "spearman_day_ratio_vs_all": rho(both23.day_ratio, both23.day_ratio_23),
        "meshes_with_outside_shelter_only": int(((mesh.sh_1000 > 0) & (mesh.sh_1000_23 == 0)).sum()),
    }

    # Pseudo-count +1
    pc = mesh.copy()
    pc["day_ratio"] = pc.day19 / (pc.sh_1000 + 1)
    pc["night_ratio"] = pc.night / (pc.sh_1000 + 1)
    pc["delta"] = pc.day_ratio - pc.night_ratio
    res["pseudo_count"] = {
        "day_top20_overlap_with_main": overlap(day_top, top(pc, "day_ratio")),
        "delta_top20_overlap_with_main": overlap(delta_top, top(pc, "delta")),
        "top_delta_mesh": top(pc, "delta").iloc[0].mesh1kmid,
    }

    # Earthquake-site cross-check, published wards only
    eqs = mesh[(mesh.eq_published) & (mesh.eq_1000 > 0)].copy()
    eqs["eq_day_ratio"] = eqs.day19 / eqs.eq_1000
    eqs["eq_night_ratio"] = eqs.night / eqs.eq_1000
    eqs["eq_delta"] = eqs.eq_day_ratio - eqs.eq_night_ratio
    eq_top = top(eqs, "eq_day_ratio")
    eq_delta_top = top(eqs, "eq_delta")
    sh_sub = eqs[eqs.sh_1000 > 0].copy()
    sh_sub["sh_day_ratio"] = sh_sub.day19 / sh_sub.sh_1000
    res["C6_earthquake_sites"] = {
        "published_meshes": int(mesh.eq_published.sum()),
        "finite_eq_meshes": int(len(eqs)),
        "top20_overlap_shelter_vs_eq": len(ids(eq_top) & ids(top(sh_sub, "sh_day_ratio"))),
        "spearman_day_ratio_shelter_vs_eq": rho(sh_sub.eq_day_ratio, sh_sub.sh_day_ratio),
        "top_mesh_eq": eq_top.iloc[0].mesh1kmid,
        "top_ward_eq": eq_top.iloc[0].ward,
        "top_eq_count": int(eq_top.iloc[0].eq_1000),
        "top_eq_day_ratio": float(eq_top.iloc[0].eq_day_ratio),
        "top_delta_mesh_eq": eq_delta_top.iloc[0].mesh1kmid,
        "top_delta_ward_eq": eq_delta_top.iloc[0].ward,
        "top_delta_eq": float(eq_delta_top.iloc[0].eq_delta),
    }

    # MAUP: blocks at four scales
    maup = {}
    for scale, g in blocks.groupby("scale"):
        g = g[g.sh_1000 > 0].copy()
        g["day_ratio"] = g.day19 / g.sh_1000
        g["night_ratio"] = g.night / g.sh_1000
        k = max(3, int(round(0.1 * len(g))))
        d = g.sort_values(["day_ratio", "block_id"], ascending=[False, True]).head(k)
        n = g.sort_values(["night_ratio", "block_id"], ascending=[False, True]).head(k)
        p = g.sort_values(["day19", "block_id"], ascending=[False, True]).head(k)
        maup[scale] = {
            "blocks": int(len(g)),
            "k_top10pct": int(k),
            "day_night_overlap": len(set(d.block_id) & set(n.block_id)),
            "day_pop_overlap": len(set(d.block_id) & set(p.block_id)),
            "spearman_day_night": rho(g.day_ratio, g.night_ratio),
        }
    res["C5_maup"] = maup

    res["alternative_tops"] = {
        "day_population": {
            "mesh1kmid": daypop_top.iloc[0].mesh1kmid,
            "ward": daypop_top.iloc[0].ward,
            "day19": int(daypop_top.iloc[0].day19),
            "shelters_1km": int(daypop_top.iloc[0].sh_1000),
        },
        "day_ratio_level": {
            "mesh1kmid": day_top.iloc[0].mesh1kmid,
            "ward": day_top.iloc[0].ward,
            "day_ratio": float(day_top.iloc[0].day_ratio),
            "shelters_1km": int(day_top.iloc[0].sh_1000),
        },
        "relative": {
            "mesh1kmid": rel_top_all.iloc[0].mesh1kmid,
            "ward": rel_top_all.iloc[0].ward,
            "relative_ratio": float(rel_top_all.iloc[0].rel),
        },
        "year_2021_delta": res["most_worsened_2021"],
        "pseudo_count_delta": {
            "mesh1kmid": res["pseudo_count"]["top_delta_mesh"],
        },
        "earthquake_site_delta": {
            "mesh1kmid": res["C6_earthquake_sites"]["top_delta_mesh_eq"],
            "ward": res["C6_earthquake_sites"]["top_delta_ward_eq"],
            "delta": res["C6_earthquake_sites"]["top_delta_eq"],
        },
        "radius_500_delta": radius_detail["500"]["top_delta_mesh"],
        "radius_1500_delta": radius_detail["1500"]["top_delta_mesh"],
    }

    # Ward summary
    ward = mesh.groupby(["ward_code", "ward"]).agg(
        meshes=("mesh1kmid", "size"),
        night=("night", "sum"),
        day19=("day19", "sum"),
        shelters_1km_sum=("sh_1000", "sum"),
    ).reset_index()
    ward["day_night"] = ward.day19 / ward.night.replace(0, np.nan)

    # Write lists
    cols = ["mesh1kmid", "ward", "lon", "lat", "night", "day19", "day21", "sh_1000",
            "night_ratio", "day_ratio", "delta"]
    day_top[cols].to_csv(OUT / "top20_day_ratio_2019.csv", index=False)
    night_top[cols].to_csv(OUT / "top20_night_ratio.csv", index=False)
    delta_top[cols].to_csv(OUT / "top20_delta_abs.csv", index=False)
    daypop_top[cols].to_csv(OUT / "top20_day_population.csv", index=False)
    rel_top_all[cols + ["rel"]].to_csv(OUT / "top20_relative_ratio.csv", index=False)
    zero_top[["mesh1kmid", "ward", "lon", "lat", "night", "day19", "nearest_sh_m"]] \
        .to_csv(OUT / "zero_shelter_top10.csv", index=False)
    ward.to_csv(OUT / "ward_summary.csv", index=False)

    # Moran input
    finite[["mesh1kmid", "lon", "lat", "night_ratio", "day_ratio", "delta", "day19", "rel"]] \
        .to_parquet(OUT / "moran_input.parquet", index=False)

    (OUT / "analysis_results.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
