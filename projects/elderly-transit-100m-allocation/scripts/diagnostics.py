"""Decompose the allocation difference and compute rank/top-K diagnostics.

Run from repository root:
  /tmp/venv-geoai/bin/python projects/elderly-transit-100m-allocation/scripts/diagnostics.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[3]
PROJECT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / PROJECT.name
OUTPUT = PROJECT / "outputs"

ALLOCATIONS = {
    "center": "center_age65_main_500",
    "five": "five_age65_main_500",
    "wpop": "wpop_age65_main_500",
    "uniform": "uniform_age65_main_500",
}
FRACTIONS = {
    "wpop": "wpop_fraction_main_500",
    "uniform": "uniform_fraction_main_500",
    "five": "five_fraction_main_500",
}
KEY = ["53393610", "53394648", "53392558", "53394256", "53394207", "53393253"]


def rank_table(frame, column):
    d = frame[frame[column].notna() & (frame[column] > 0)].copy()
    d = d.sort_values([column, "mesh"], ascending=[False, True]).reset_index(drop=True)
    d["rank"] = np.arange(1, len(d) + 1)
    return d


def overlap_at_k(tables, k):
    result = {}
    names = list(tables)
    for a in names:
        for b in names:
            result[f"{a}__{b}"] = len(
                set(tables[a]["mesh"].head(k)) & set(tables[b]["mesh"].head(k))
            )
    return result


def positive_union_spearman(frame, allocations, columns):
    union = np.zeros(len(frame), dtype=bool)
    for col in columns.values():
        union |= (frame[col].fillna(0) > 0).to_numpy()
    sub = frame.loc[union, list(columns.values())]
    out = {"n": int(union.sum()), "pairs": {}}
    for a in allocations:
        for b in allocations:
            out["pairs"][f"{a}__{b}"] = float(
                spearmanr(
                    sub[columns[a]].fillna(0), sub[columns[b]].fillna(0)
                ).statistic
            )
    return out


def top_union_spearman(frame, allocations, columns, k=50):
    selected = set()
    for col in columns.values():
        selected |= set(rank_table(frame, col)["mesh"].head(k))
    sub = frame[frame["mesh"].isin(selected)]
    out = {"n": len(sub), "k": k, "pairs": {}}
    for a in allocations:
        for b in allocations:
            out["pairs"][f"{a}__{b}"] = float(
                spearmanr(sub[columns[a]].fillna(0), sub[columns[b]].fillna(0)).statistic
            )
    return out


def main():
    frame = pd.read_parquet(ARTIFACTS / "mesh-allocations.parquet")
    points = pd.read_parquet(ARTIFACTS / "point-access.parquet")
    center_points = (
        points[points["point_type"] == "center"]
        .set_index("mesh")[["bus_500", "rail_500", "nearest_node_m"]]
        .rename(columns={"bus_500": "center_bus_m", "rail_500": "center_rail_m",
                         "nearest_node_m": "center_nearest_node_m"})
    )
    frame = frame.merge(center_points, left_on="mesh", right_index=True, how="left")
    frame["wpop_fraction"] = frame["wpop_fraction_main_500"]
    frame["uniform_fraction"] = frame["uniform_fraction_main_500"]
    frame["five_fraction"] = frame["five_fraction_main_500"]
    frame["center_gap"] = frame["center_gap_main_500"]

    tables = {name: rank_table(frame, col) for name, col in ALLOCATIONS.items()}
    top = {name: tables[name]["mesh"].head(10).tolist() for name in tables}

    # Top-K overlap at several K.
    overlaps = {str(k): overlap_at_k(tables, k) for k in (5, 10, 20, 50)}

    # Spearman under three supports.
    columns = ALLOCATIONS
    complete = frame[list(columns.values())].dropna()
    spearman = {
        "all_age_known": {
            "n": int(len(complete)),
            "pairs": {
                f"{a}__{b}": float(
                    spearmanr(complete[columns[a]], complete[columns[b]]).statistic
                )
                for a in columns for b in columns
            },
        },
        "positive_union": positive_union_spearman(frame, columns, columns),
        "top50_union": top_union_spearman(frame, columns, columns, k=50),
    }
    center_positive = frame[frame["center_age65_main_500"].fillna(0) > 0]
    spearman["center_positive"] = {
        "n": int(len(center_positive)),
        "pairs": {
            f"{a}__{b}": float(
                spearmanr(
                    center_positive[columns[a]].fillna(0),
                    center_positive[columns[b]].fillna(0),
                ).statistic
            )
            for a in columns for b in columns
        },
    }

    # Decomposition of the center-gap population.
    age_known = frame[frame["age65"].notna()].copy()
    center_gap = age_known[age_known["center_gap"] == 1]
    not_center_gap = age_known[age_known["center_gap"] == 0]
    wpop_col = "wpop_age65_main_500"
    uniform_col = "uniform_age65_main_500"
    bins = [0.0, 0.0001, 0.1, 0.25, 0.5, 0.75, 1.0001]
    labels = ["0", "(0,0.1)", "[0.1,0.25)", "[0.25,0.5)", "[0.5,0.75)", "[0.75,1]"]
    center_gap = center_gap.copy()
    center_gap["fraction_bin"] = pd.cut(
        center_gap["wpop_fraction"].fillna(0), bins=bins, labels=labels, right=False
    )
    decomposition = {
        "all_age_known_meshes": int(len(age_known)),
        "all_age65": float(age_known["age65"].sum()),
        "all_wpop_target": float(age_known[wpop_col].sum()),
        "all_uniform_target": float(age_known[uniform_col].sum()),
        "all_wpop_share": float(age_known[wpop_col].sum() / age_known["age65"].sum()),
        "all_uniform_share": float(age_known[uniform_col].sum() / age_known["age65"].sum()),
        "center_gap_unknown_meshes": int(age_known["center_gap"].isna().sum()),
        "center_gap_unknown_age65": float(
            age_known.loc[age_known["center_gap"].isna(), "age65"].sum()
        ),
        "center_gap_meshes": int(len(center_gap)),
        "center_gap_age65": float(center_gap["age65"].sum()),
        "center_gap_wpop_target": float(center_gap[wpop_col].sum()),
        "center_gap_uniform_target": float(center_gap[uniform_col].sum()),
        "center_gap_wpop_share": float(center_gap[wpop_col].sum() / center_gap["age65"].sum()),
        "center_gap_uniform_share": float(center_gap[uniform_col].sum() / center_gap["age65"].sum()),
        "center_gap_wpop_zero_meshes": int((center_gap[wpop_col].fillna(0) == 0).sum()),
        "center_gap_wpop_positive_meshes": int((center_gap[wpop_col].fillna(0) > 0).sum()),
        "center_gap_wpop_fraction_median": float(center_gap["wpop_fraction"].median()),
        "center_gap_wpop_fraction_mean": float(center_gap["wpop_fraction"].mean()),
        "center_gap_wpop_fraction_q25": float(center_gap["wpop_fraction"].quantile(0.25)),
        "center_gap_wpop_fraction_q75": float(center_gap["wpop_fraction"].quantile(0.75)),
        "center_gap_fraction_bins": {
            str(k): int(v) for k, v in center_gap["fraction_bin"].value_counts().sort_index().items()
        },
        "not_center_gap_meshes": int(len(not_center_gap)),
        "not_center_gap_age65": float(not_center_gap["age65"].sum()),
        "not_center_gap_wpop_target": float(not_center_gap[wpop_col].sum()),
        "not_center_gap_wpop_positive_meshes": int((not_center_gap[wpop_col].fillna(0) > 0).sum()),
        "not_center_gap_uniform_target": float(not_center_gap[uniform_col].sum()),
        "wpop_target_outside_center_gap_share": float(
            not_center_gap[wpop_col].sum() / age_known[wpop_col].sum()
        ),
        "wpop_positive_meshes_total": int((age_known[wpop_col].fillna(0) > 0).sum()),
        "wpop_positive_meshes_outside_center_gap": int(
            (not_center_gap[wpop_col].fillna(0) > 0).sum()
        ),
    }
    center_gap_bins = center_gap.groupby("fraction_bin", observed=False).agg(
        meshes=("mesh", "size"),
        age65=("age65", "sum"),
        wpop_target=(wpop_col, "sum"),
    )
    center_gap_bins.to_csv(OUTPUT / "center-gap-fraction-bins.csv")

    # Top-10 detail table.
    detail_rows = []
    for name, table in tables.items():
        for _, row in table.head(10).iterrows():
            detail_rows.append({
                "allocation": name,
                "rank": int(row["rank"]),
                "mesh": row["mesh"],
                "municipality": row["municipality"],
                "age65": row["age65"],
                "target_age65": row[ALLOCATIONS[name]],
                "wpop_fraction": row["wpop_fraction"],
                "uniform_fraction": row["uniform_fraction"],
                "center_gap": row["center_gap"],
                "center_bus_m": row["center_bus_m"],
                "center_rail_m": row["center_rail_m"],
                "wpop_census_ratio": row["wpop_census_ratio"],
                "nodata_pixels": row["nodata_pixels"],
                "valid_pixels": row["valid_pixels"],
                "pixels_inside": row["pixels_inside"],
                "unknown_weight_share": row["wpop_unknown_weight_share_main_500"],
            })
    detail = pd.DataFrame(detail_rows)
    detail.to_csv(OUTPUT / "top10-detail.csv", index=False)

    # Key mesh positions and distances.
    key_rows = []
    for mesh in KEY:
        row = frame[frame["mesh"] == mesh].iloc[0]
        key_rows.append({
            "mesh": mesh,
            "municipality": row["municipality"],
            "age65": row["age65"],
            "center_gap": row["center_gap"],
            "center_bus_m": row["center_bus_m"],
            "center_rail_m": row["center_rail_m"],
            "wpop_fraction": row["wpop_fraction"],
            "uniform_fraction": row["uniform_fraction"],
            "wpop_target": row["wpop_age65_main_500"],
            "uniform_target": row["uniform_age65_main_500"],
            "wpop_census_ratio": row["wpop_census_ratio"],
            "nodata_pixels": row["nodata_pixels"],
            "valid_pixels": row["valid_pixels"],
            "unknown_weight_share": row["wpop_unknown_weight_share_main_500"],
            "pixels_inside": row["pixels_inside"],
            "ranks": {
                name: (int(tables[name].index[tables[name]["mesh"] == mesh][0]) + 1
                       if mesh in set(tables[name]["mesh"]) else None)
                for name in tables
            },
        })
    pd.DataFrame(key_rows).to_csv(OUTPUT / "key-meshes.csv", index=False)

    # Composition by ratio bin for each top 10.
    ratio_bins = pd.cut(
        frame["wpop_census_ratio"],
        bins=[-np.inf, 0.5, 2.0, np.inf],
        labels=["lt0.5", "0.5-2.0", "gt2.0"],
        right=False,
    )
    frame["ratio_bin"] = ratio_bins
    top_ratio = {}
    for name, codes in top.items():
        sub = frame[frame["mesh"].isin(codes)]
        top_ratio[name] = {
            "bins": {str(k): int(v) for k, v in sub["ratio_bin"].value_counts().items()},
            "outside_0.5_2.0": int((~sub["wpop_census_ratio"].between(0.5, 2.0)).sum()),
            "ratio_min": float(sub["wpop_census_ratio"].min()),
            "ratio_max": float(sub["wpop_census_ratio"].max()),
        }

    # Border/water sensitivity: meshes fully inside (150 pixels).
    fully_inside = frame[frame["pixels_inside"] == 150]
    border_tables = {name: rank_table(fully_inside, col) for name, col in ALLOCATIONS.items()}
    border = {
        "meshes_full_inside": int(len(fully_inside)),
        "meshes_partial": int((frame["pixels_inside"] < 150).sum()),
        "top10": {name: border_tables[name]["mesh"].head(10).tolist() for name in border_tables},
        "top10_retained_from_full": {
            name: sorted(set(top[name]) & set(border_tables[name]["mesh"].head(10)))
            for name in top
        },
        "top10_removed": {
            name: sorted(set(top[name]) - set(border_tables[name]["mesh"].head(10)))
            for name in top
        },
        "overlaps": overlap_at_k(border_tables, 10),
        "partial_top10_members": {
            name: sorted(set(top[name]) & set(frame.loc[frame["pixels_inside"] < 150, "mesh"]))
            for name in top
        },
    }

    # Ratio-restricted top-10 composition and the all-four intersection.
    ratio_frame = frame[frame["wpop_census_ratio"].between(0.5, 2.0, inclusive="both")]
    ratio_tables = {name: rank_table(ratio_frame, col) for name, col in ALLOCATIONS.items()}
    ratio_summary = {
        "meshes": int(len(ratio_frame)),
        "top10": {name: ratio_tables[name]["mesh"].head(10).tolist() for name in ratio_tables},
        "overlaps": overlap_at_k(ratio_tables, 10),
        "all_four_intersection": sorted(
            set.intersection(*[set(ratio_tables[name]["mesh"].head(10)) for name in ratio_tables])
        ),
        "key_positions": {
            mesh: {
                name: (int(ratio_tables[name].index[ratio_tables[name]["mesh"] == mesh][0]) + 1
                       if mesh in set(ratio_tables[name]["mesh"]) else None)
                for name in ratio_tables
            }
            for mesh in KEY
        },
    }

    result = {
        "top10": top,
        "overlaps_at_k": overlaps,
        "spearman": spearman,
        "decomposition": decomposition,
        "top10_ratio_composition": top_ratio,
        "border_sensitivity": border,
        "ratio_restricted": ratio_summary,
        "key_meshes": key_rows,
    }
    (OUTPUT / "diagnostics.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=float) + "\n"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=float))


if __name__ == "__main__":
    main()
