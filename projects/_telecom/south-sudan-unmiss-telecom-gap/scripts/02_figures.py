"""Create Japanese, geographically contextual maps of observed source records."""

import argparse
import json
import math
from pathlib import Path
import sys

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

ROOT = Path("projects/_telecom/south-sudan-unmiss-telecom-gap")
OUT = ROOT / "outputs"
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / ".agents/skills/analysis-visualize/scripts"))
from cjk_font import use_cjk_font  # noqa: E402

NE_REVISION = "efdd0668c57c9d42307e12eacbf66d8d151de5b9"
NE_VERSION = "5.1.2"
EXTENT = (23.5, 36.5, 3.2, 12.5)
COUNTRY_CODES = ["SSD", "SDN", "ETH", "KEN", "UGA", "COD", "CAF"]
AUTHOR = ('調査者：yuiseki (Yui Matsumura), volunteer member of UN Open GIS Initiative, '
          'Domain Working Group 7 ("Smart Maps Group")')
OOKLA_ATTRIBUTION = (
    "Speedtest by Ookla® Global Fixed and Mobile Network Performance Maps. "
    "Based on analysis by Ookla of Speedtest Intelligence® data for 2024 Q2; accessed 11 November 2026. "
    "CC BY-NC-SA 4.0; trademarks used under license and reprinted with permission. 非商用調査研究。"
)
OPENCELLID_ATTRIBUTION = "OpenCelliD contributors, 2026-10-06 snapshot, MCC 659 extract; CC BY-SA 4.0."
OSM_ATTRIBUTION = "© OpenStreetMap contributors, ODbL 1.0; 2026-11-11取得。"


def _sites():
    path = OUT / "unmiss_record_proximity.csv"
    if not path.exists():
        path = OUT / "legacy_unmiss_site_cellular_distance.csv"
    df = pd.read_csv(path, encoding="utf-8")
    lon = "site_lon" if "site_lon" in df else "longitude_wgs84"
    lat = "site_lat" if "site_lat" in df else "latitude_wgs84"
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[lon], df[lat]), crs="EPSG:4326")


def _context(directory):
    directory = Path(directory)
    countries = gpd.read_parquet(directory / "ne_10m_admin_0_countries.parquet")
    states = gpd.read_parquet(directory / "ne_10m_admin_1_states_provinces.parquet")
    places = gpd.read_parquet(directory / "ne_10m_populated_places.parquet")
    countries = countries[countries["ISO_A3_EH"].isin(COUNTRY_CODES)].copy()
    south_sudan = countries[countries["ISO_A3_EH"] == "SSD"]
    states = states[states["adm0_a3"] == "SDS"].copy()
    places = places[places["ADM0_A3"] == "SSD"].copy()
    return countries, south_sudan, states, places


def _draw_context(ax, countries, south_sudan, states, places):
    neighbors = countries[countries["ISO_A3_EH"] != "SSD"]
    neighbors.plot(ax=ax, color="#edf0f1", edgecolor="#92999d", linewidth=0.55, zorder=0)
    south_sudan.plot(ax=ax, color="#fffdf7", edgecolor="#30383d", linewidth=1.15, zorder=1)
    states.boundary.plot(ax=ax, color="#9da3a5", linewidth=0.48, zorder=2)
    state_label_positions = {
        "Central Equatoria": (30.55, 4.28),
        "Warrap": (28.95, 7.15),
        "Western Bahr el Ghazal": (25.3, 8.25),
        "Northern Bahr el Ghazal": (26.0, 9.2),
    }
    for _, row in states.iterrows():
        point = row.geometry.representative_point()
        x, y = state_label_positions.get(row["name"], (point.x, point.y))
        ax.text(x, y, row.get("name_ja") or row["name"], color="#697174", fontsize=7.0,
                ha="center", va="center", zorder=3,
                clip_on=True,
                bbox={"boxstyle": "round,pad=0.12", "fc": "white", "ec": "none", "alpha": 0.65})
    for _, row in places[places["POP_MAX"] >= 100000].iterrows():
        point = row.geometry
        ax.scatter([point.x], [point.y], s=8, c="#30383d", zorder=5)
        place_offsets = {"Juba": (7, -12), "Wau": (6, 6), "Malakal": (6, 6), "Yei": (6, -10)}
        ax.annotate(row.get("NAME_JA") or row["NAME"], (point.x, point.y),
                    xytext=place_offsets.get(row["NAME"], (4, 4)),
                    textcoords="offset points", fontsize=7.2, color="#30383d", zorder=6,
                    annotation_clip=True,
                    bbox={"boxstyle": "round,pad=0.12", "fc": "white", "ec": "none", "alpha": 0.8})
    for _, row in neighbors.iterrows():
        point = row.geometry.representative_point()
        if not (EXTENT[0] <= point.x <= EXTENT[1] and EXTENT[2] <= point.y <= EXTENT[3]):
            continue
        ax.text(point.x, point.y, row.get("NAME_JA") or row["ADMIN"], color="#70777a", fontsize=8,
                ha="center", va="center", zorder=2, clip_on=True)
    ax.set_xlim(EXTENT[:2])
    ax.set_ylim(EXTENT[2:])
    ax.set_aspect(1 / math.cos(math.radians(7.8)))
    ax.set_xlabel("経度（度、WGS 84）")
    ax.set_ylabel("緯度（度、WGS 84）")
    ax.grid(color="#cbd0d1", linewidth=0.35, alpha=0.7, zorder=0)


def _base_metadata():
    return {
        "language": "ja", "crs": "EPSG:4326", "map_extent": "South Sudan and neighboring countries",
        "deployment_coordinate_clusters": int(len(_sites())),
        "geographic_context": {
            "source": f"Natural Earth v{NE_VERSION}", "revision": NE_REVISION,
            "layers": ["10m_admin_0_countries", "10m_admin_1_states_provinces", "10m_populated_places"],
            "license": "Public Domain",
        },
        "researcher": AUTHOR,
    }


def _save_metadata(name, metadata):
    (OUT / f"{name}.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _plot_deployment_markers(ax, sites):
    """Use transparent markers so measurements and mapped assets underneath remain legible."""
    ax.scatter(sites.geometry.x, sites.geometry.y, s=62, marker="o", facecolors="none",
               edgecolors="#e34a33", linewidths=1.35, zorder=8)


def plot_opencellid_map(natural_earth_dir):
    countries, south_sudan, states, places = _context(natural_earth_dir)
    sites = _sites()
    cells = pd.read_csv(OUT / "opencellid_mcc659_cell_records.csv", encoding="utf-8")
    points = gpd.GeoDataFrame(cells, geometry=gpd.points_from_xy(cells["lon"], cells["lat"]), crs="EPSG:4326")
    text = ("南スーダン：OpenCelliD 登録セル記録と UNMISS 配置図由来座標", "国境・州境・都市名",
            "GSM 登録セル", "LTE 登録セル", "UNMISS 配置図由来座標群", "記録位置は稼働・電波到達を示さない",
            "拠点位置はPDFからの自動抽出で未検証", "公開データベース上の位置記録", AUTHOR,
            OPENCELLID_ATTRIBUTION, "ジュバ", "マラカル", "ワーウ", "ボー")
    font = use_cjk_font(" ".join(text))
    fig, ax = plt.subplots(figsize=(11.6, 8.7))
    _draw_context(ax, countries, south_sudan, states, places)
    gsm = points[points["radio"] == "GSM"]
    lte = points[points["radio"] == "LTE"]
    ax.scatter(gsm.geometry.x, gsm.geometry.y, s=13, marker="o", c="#6a51a3", alpha=0.76,
               edgecolors="white", linewidths=0.25, zorder=5)
    ax.scatter(lte.geometry.x, lte.geometry.y, s=43, marker="^", c="#d73027", alpha=0.9,
               edgecolors="white", linewidths=0.4, zorder=6)
    _plot_deployment_markers(ax, sites)
    handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor="none", markeredgecolor="#e34a33",
               markersize=8, label=f"UNMISS 配置図由来座標群（中抜き輪、{len(sites)}群）"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor="#6a51a3", markersize=6,
               label=f"GSM 登録セル記録（{len(gsm)}件）"),
        Line2D([0], [0], marker="^", color="none", markerfacecolor="#d73027", markersize=8,
               label=f"LTE 登録セル記録（{len(lte)}件）"),
    ]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1), title="地図記号", fontsize=8.2)
    ax.set_title("南スーダン：OpenCelliD の登録位置と UNMISS 配置図由来座標", fontsize=13.5, pad=12)
    fig.text(0.73, 0.16, "登録位置の分布を示します。基地局の実数・稼働状態・電波到達・サービス可用性は示しません。\n"
             "UNMISS座標は2024年配置図からの自動抽出で、個々の拠点位置と地名は未確認です。",
             ha="left", va="top", fontsize=8.1, color="#353b3e")
    fig.text(0.08, 0.055, f"背景：Natural Earth v{NE_VERSION}・EPSG:4326　|　{AUTHOR}",
             ha="left", va="bottom", fontsize=6.8, color="#41474a")
    fig.text(0.08, 0.032, OPENCELLID_ATTRIBUTION,
             ha="left", va="bottom", fontsize=6.8, color="#41474a")
    fig.subplots_adjust(left=0.08, right=0.73, top=0.91, bottom=0.17)
    fig.savefig(OUT / "recorded_feature_map.png", dpi=220, bbox_inches="tight")
    plt.close(fig)
    metadata = _base_metadata()
    metadata.update({
        "question": "配置図由来座標と OpenCelliD 登録セル記録は、地理的にどこに位置するか。",
        "font": font, "record_counts": {"opencellid_mcc659": len(points), "gsm": len(gsm), "lte": len(lte)},
        "deployment_marker": "small hollow orange ring; underlying records remain visible",
        "opencellid_attribution": OPENCELLID_ATTRIBUTION,
        "caveat": "登録記録の位置であり、実設備・稼働・電波到達・サービス可用性を意味しない。",
    })
    _save_metadata("recorded_feature_map", metadata)


def plot_ookla_map(natural_earth_dir):
    countries, south_sudan, states, places = _context(natural_earth_dir)
    sites = _sites()
    ookla = gpd.read_parquet(OUT / "ookla_mobile_tiles_ssd.parquet")
    speeds = ookla["avg_d_kbps"].to_numpy() / 1000
    tests = ookla["tests"].to_numpy()
    text = ("南スーダン：Ookla モバイル測定地点と UNMISS 配置図由来座標", "平均下り速度（Mbps）",
            "測定回数（点の大きさ、30回で上限）", "Ookla 測定タイル中心", "UNMISS 配置図由来座標群",
            "観測の無い場所は速度ゼロを意味しない", "配置地点の接続可能性は未検証", AUTHOR,
            OOKLA_ATTRIBUTION, "ジュバ", "マラカル", "ワーウ", "ボー")
    font = use_cjk_font(" ".join(text))
    fig, ax = plt.subplots(figsize=(11.3, 8.2))
    _draw_context(ax, countries, south_sudan, states, places)
    points = ax.scatter(ookla.geometry.x, ookla.geometry.y, c=speeds,
                        s=16 + np.minimum(tests, 30) * 1.5, cmap="viridis", vmin=0,
                        vmax=float(speeds.max()), alpha=0.86, edgecolors="white", linewidths=0.35, zorder=5)
    colorbar = fig.colorbar(points, ax=ax, fraction=0.034, pad=0.025)
    colorbar.set_label("タイル内の平均下り速度（Mbps）")
    _plot_deployment_markers(ax, sites)
    ax.legend(handles=[
        Line2D([0], [0], marker="o", color="none", markerfacecolor="#555555", markersize=7,
               label="Ookla 測定地点（色：平均速度、点の大きさ：テスト数）"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor="none", markeredgecolor="#e34a33",
               markersize=8, label=f"UNMISS 配置図由来座標群（中抜き輪、{len(sites)}群）"),
    ], loc="upper left", bbox_to_anchor=(1.28, 1), fontsize=8, frameon=True, title="地図記号")
    ax.set_title("南スーダン：Ookla モバイル測定地点と UNMISS 配置図由来座標", fontsize=13, pad=12)
    fig.text(0.72, 0.16, "色はタイル内の平均下り速度、点の大きさはテスト回数（30回で上限）。\n"
             "点の無い場所は未観測です。速度ゼロやサービス不存在を意味しません。\n"
             "測定結果は配置地点での通信品質・接続可能性を保証しません。",
             ha="left", va="top", fontsize=8.1, color="#353b3e")
    fig.text(0.08, 0.055, f"背景：Natural Earth v{NE_VERSION}・EPSG:4326　|　{AUTHOR}",
             ha="left", va="bottom", fontsize=6.7, color="#41474a")
    fig.text(0.08, 0.032, OOKLA_ATTRIBUTION,
             ha="left", va="bottom", fontsize=6.7, color="#41474a")
    fig.subplots_adjust(left=0.08, right=0.72, top=0.91, bottom=0.17)
    fig.savefig(OUT / "ookla_observed_tiles.png", dpi=220, bbox_inches="tight")
    plt.close(fig)
    metadata = _base_metadata()
    metadata.update({
        "question": "2024年第2四半期に記録された Ookla モバイル測定値はどこに分布するか。",
        "font": font, "observed_tile_centres": len(ookla), "value": "tile mean download speed (Mbps)",
        "deployment_marker": "small hollow orange ring; underlying records remain visible",
        "size": "tests per tile, capped at 30", "speed_range_mbps": [0, round(float(speeds.max()), 3)],
        "ookla_attribution": OOKLA_ATTRIBUTION,
        "caveat": "未観測地点は速度ゼロではなく、配置地点での可用性・性能を保証しない。",
    })
    _save_metadata("ookla_observed_tiles", metadata)


def plot_osm_map(natural_earth_dir):
    countries, south_sudan, states, places = _context(natural_earth_dir)
    sites = _sites()
    power_points = gpd.read_parquet(OUT / "osm_power_points.parquet")
    power_lines = gpd.read_parquet(OUT / "osm_power_lines.parquet")
    text = ("南スーダン：OSM 電力関連地物と UNMISS 配置図由来座標", "電力関連地物の登録位置",
            "OSM 送電線", "電力関連点（種類別）", "配置図由来座標", "登録地物は稼働・接続可能性を示さない",
            AUTHOR, OSM_ATTRIBUTION, "ユニティ州", "ジュングレイ州", "ジュバ")
    font = use_cjk_font(" ".join(text))
    fig, ax = plt.subplots(figsize=(11.3, 8.2))
    _draw_context(ax, countries, south_sudan, states, places)
    power_lines.plot(ax=ax, color="#8c6d31", linewidth=1.0, alpha=0.78, zorder=4)
    type_styles = {
        "plant": ("発電所タグ", "#d95f02", "P"),
        "generator": ("発電機タグ", "#1b9e77", "s"),
        "substation": ("変電所タグ", "#7570b3", "D"),
    }
    present = set(power_points["type"].dropna())
    for kind, (label, color, marker) in type_styles.items():
        subset = power_points[power_points["type"] == kind]
        if len(subset):
            subset.plot(ax=ax, color=color, marker=marker, markersize=22, alpha=0.82, zorder=5)
    _plot_deployment_markers(ax, sites)
    handles = [
        Line2D([0], [0], color="#8c6d31", linewidth=1.6, label=f"OSM 送電線（{len(power_lines)}地物）"),
        *[Line2D([0], [0], marker=type_styles[k][2], color="none", markerfacecolor=type_styles[k][1],
                 markersize=7, label=f"{type_styles[k][0]}（{int((power_points['type'] == k).sum())}地物）")
          for k in type_styles if k in present],
        Line2D([0], [0], marker="o", color="none", markerfacecolor="none", markeredgecolor="#e34a33",
               markersize=8, label=f"UNMISS 配置図由来座標群（中抜き輪、{len(sites)}群）"),
    ]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1), title="地図記号", fontsize=8)
    ax.set_title("南スーダン：OSM 電力関連地物の登録位置", fontsize=13, pad=12)
    fig.text(0.72, 0.16, "OSM上のタグと位置を表示しています。設備の稼働、容量、送電網への接続、\n"
             "UNMISSによる利用可能性は確認していません。記録の完全性も保証されません。",
             ha="left", va="top", fontsize=8.1, color="#353b3e")
    fig.text(0.08, 0.055, f"背景：Natural Earth v{NE_VERSION}・EPSG:4326　|　{AUTHOR}",
             ha="left", va="bottom", fontsize=6.8, color="#41474a")
    fig.text(0.08, 0.032, OSM_ATTRIBUTION,
             ha="left", va="bottom", fontsize=6.8, color="#41474a")
    fig.subplots_adjust(left=0.08, right=0.72, top=0.91, bottom=0.17)
    fig.savefig(OUT / "osm_power_records_map.png", dpi=220, bbox_inches="tight")
    plt.close(fig)
    metadata = _base_metadata()
    metadata.update({
        "question": "OSMには南スーダンのどこに電力関連地物が登録されているか。",
        "font": font, "osm_power_points": len(power_points), "osm_power_lines": len(power_lines),
        "deployment_marker": "small hollow orange ring; underlying records remain visible",
        "osm_tags": sorted(present), "attribution": OSM_ATTRIBUTION,
        "caveat": "OSMの登録は稼働・容量・接続・サービス・UNMISSからの利用可能性を示さない。",
    })
    _save_metadata("osm_power_records_map", metadata)


def plot_record_proximity():
    sites = pd.read_csv(OUT / "legacy_unmiss_site_cellular_distance.csv", encoding="utf-8")
    current = OUT / "unmiss_record_proximity.csv"
    if current.exists():
        sites = pd.read_csv(current, encoding="utf-8")
    cell_distances = pd.read_csv(OUT / "opencellid_record_proximity.csv", encoding="utf-8")
    series = [
        ("OpenCelliD 登録セル記録", "nearest_any_record_distance_km", "#756bb1", cell_distances),
        ("Ookla 2024年第2四半期\n測定タイル中心", "dist_ookla_tile_km" if "dist_ookla_tile_km" in sites else "dist_ookla_km", "#2b8cbe", sites),
        ("OSM 電力関連点", "dist_osm_power_related_point_km" if "dist_osm_power_related_point_km" in sites else "dist_power_gen_km", "#41ab5d", sites),
        ("OSM 送電線", "dist_power_line_km", "#d95f0e", sites),
    ]
    font = use_cjk_font("配置図由来座標群 最寄り記録までの距離（km、対数目盛） 10 km参照線 通信圏ではない")
    fig, ax = plt.subplots(figsize=(10.5, 6.3))
    for y, (label, column, color, source) in enumerate(series):
        values = source[column].dropna().to_numpy()
        ax.scatter(values, [y] * len(values), alpha=0.78, s=30, color=color)
        ax.plot([values.min(), values.max()], [y, y], color=color, alpha=0.22, linewidth=2)
    ax.axvline(10, color="#555555", linestyle="--", linewidth=1, label="10 km の参照線（通信圏ではない）")
    ax.set_xscale("log")
    ax.set_yticks(range(len(series)), [row[0] for row in series])
    ax.set_xlabel("最寄りの記録までの距離（km、対数目盛）")
    ax.set_title("配置図由来座標から最寄りの公開記録までの距離")
    ax.text(0.01, -0.21, "位置的な近さだけを示します。通信サービス、設備稼働、利用可能性は判定していません。",
            transform=ax.transAxes, fontsize=8.5, va="top", wrap=True)
    ax.grid(axis="x", alpha=0.25)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8)
    fig.subplots_adjust(left=0.25, right=0.74, top=0.88, bottom=0.22)
    fig.savefig(OUT / "recorded_feature_proximity.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    _save_metadata("recorded_feature_proximity", {
        "question": "配置図由来座標から各ソースの最近傍記録までの距離分布。",
        "language": "ja", "font": font, "unit": "km", "axis_scale": "logarithmic", "sample_size": 19,
        "reference_threshold_km": 10, "threshold_interpretation": "参照線であり、通信カバレッジ閾値ではない。",
        "source_files": ["opencellid_record_proximity.csv", "legacy_unmiss_site_cellular_distance.csv"],
    })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--natural-earth-dir", type=Path, required=True,
                        help="the pinned Natural Earth directory containing the three 10m GeoParquet files")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    plot_opencellid_map(args.natural_earth_dir)
    plot_ookla_map(args.natural_earth_dir)
    plot_osm_map(args.natural_earth_dir)
    plot_record_proximity()


if __name__ == "__main__":
    main()
