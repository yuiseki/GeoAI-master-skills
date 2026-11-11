"""Chart nearest observed tile values; these are not site measurements."""
import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / ".agents/skills/analysis-visualize/scripts"))
from cjk_font import use_cjk_font  # noqa: E402


def transfer_minutes(mbps):
    if mbps is None or not math.isfinite(mbps) or mbps <= 0:
        return None
    return 800 / mbps / 60


def eligible_speed(row):
    value = float(row["nearest_tile_mean_download_mbps"])
    distance = float(row["nearest_tile_distance_km"])
    return value if math.isfinite(value) and value > 0 and math.isfinite(distance) and distance <= 10 else None


def build_rows(sites, capital):
    tokyo = capital["groups"]["tokyo_50km"]
    result = [{"label": "首都圏の近似（東京50 km）", "kind": "capital", "speed_mbps": tokyo["median_mbps"], "time_minutes": transfer_minutes(tokyo["median_mbps"]), "distance_km": None, "tests": tokyo["tests"], "tiles": tokyo["tile_count"]}]
    for _, row in sites.iterrows():
        value = eligible_speed(row)
        result.append({"label": str(row["unverified_map_label"]), "kind": "map_coordinate", "speed_mbps": value, "time_minutes": transfer_minutes(value), "distance_km": float(row["nearest_tile_distance_km"]), "tests": int(row["nearest_tile_tests"]), "tiles": 1})
    return pd.DataFrame(result)


def draw(frame, value_column, name, title, xlabel, unit, font):
    fig, ax = plt.subplots(figsize=(12, 10))
    for i, row in frame.iterrows():
        val = row[value_column]
        if pd.notna(val):
            color = "#16648b" if row.kind == "capital" else "#d06b2d"
            ax.barh(i, val, color=color, height=.68)
            note = f"{val:.2f} {unit}"
            if row.kind != "capital":
                note += f"  （距離 {row.distance_km:.1f} km、{row.tests}回測定）"
            ax.annotate(note, (val, i), xytext=(5, 0), textcoords="offset points", va="center", fontsize=8.5)
        else:
            ax.text(.01, i, f"未表示：最寄り {row.distance_km:.1f} km（10 km超）", transform=ax.get_yaxis_transform(), va="center", fontsize=8.5, color="#555555")
    vals = frame[value_column].dropna()
    ax.set_xlim(0, max(vals) * 1.7)
    ax.set_yticks(np.arange(len(frame)), frame.label)
    ax.invert_yaxis()
    ax.set_xlabel(xlabel)
    ax.set_title(title, loc="left", fontsize=13)
    ax.grid(axis="x", alpha=.2)
    ax.set_axisbelow(True)
    fig.text(.03, .055, "橙：配置図の座標に最も近い観測タイル（10 km以内のみ）。ラベルは自動抽出で未検証。", fontsize=9)
    fig.text(.03, .04, "青：東京中心50 km以内のタイル中央値。地点値と集計単位が異なる。未表示は通信不能を意味しない。", fontsize=9)
    fig.text(.03, .025, "100 MB＝1億バイト。速度が一定で継続すると仮定した理想時間で、実測時間ではない。", fontsize=9)
    fig.text(.03, .01, "Speedtest by Ookla 2024年第2四半期、2026-11-11取得。CC BY-NC-SA 4.0。", fontsize=8)
    fig.tight_layout(rect=(0, .08, 1, .98))
    fig.savefig(OUT / f"{name}.png", dpi=180)
    metadata = {"question": title, "source": "site_transfer_comparison.csv", "ookla_period": "2024 Q2", "license": "CC BY-NC-SA 4.0", "font": font, "axis_scale": "linear", "units": unit, "coordinate_groups": int((frame.kind == "map_coordinate").sum()), "coordinate_groups_shown": int(((frame.kind == "map_coordinate") & frame[value_column].notna()).sum()), "zero_is_missing": False}
    (OUT / f"{name}.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    plt.close(fig)


def main():
    sites = pd.read_csv(OUT / "nearest_observed_speed_by_map_coordinate.csv")
    capital = json.loads((OUT / "capital_speed_comparison.json").read_text(encoding="utf-8"))
    frame = build_rows(sites, capital)
    frame.to_csv(OUT / "site_transfer_comparison.csv", index=False)
    frame = pd.read_csv(OUT / "site_transfer_comparison.csv")
    font = use_cjk_font("首都圏の近似東京配置図座標観測タイル平均下り速度距離測定回理想転送時間分未表示最寄超通信不能第四半期取得以内のみラベル自動抽出未検証青橙単位が異なるを意味しない億バイト一定継続仮実測ではない0123456789（）：、。 −＝")
    draw(frame, "speed_mbps", "site_observed_speed", "首都圏と配置図座標：近傍の観測下り速度", "下り速度（Mbps、線形軸）", "Mbps", font)
    draw(frame, "time_minutes", "site_100mb_transfer", "首都圏と配置図座標：100 MBの理想転送時間", "理想転送時間（分、線形軸）", "分", font)


if __name__ == "__main__":
    main()
