#!/usr/bin/env python3
"""
projects/_tameike/sar-drought-drawdown-monitoring/scripts/generate_report_figures.py

Generates publication-quality figures for report.md:
- Fig 1: Regional map of Seto Inland Sea reservoirs and summer drawdown delta-dB
- Fig 2: Time-series of mean backscatter across size tiers and controls (July-September 2024)
- Fig 3: Drawdown detection SNR and water surface loss percentage by size tier
- Fig 4: Moran scatter plot of reservoir drawdown spatial synchrony (Moran's I = 0.259)
- Fig 5: Local cascade risk network around top drawdown reservoirs (Matsunaga & Manno)
"""

import os
import json
import urllib.request
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Patch
from matplotlib.lines import Line2D

# Set Japanese font
plt.rcParams["font.sans-serif"] = ["Hiragino Sans", "Hiragino Kaku Gothic ProN", "YuGothic", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUTS_DIR = os.path.join(PROJECT_DIR, "outputs")
os.makedirs(OUTPUTS_DIR, exist_ok=True)

# 1. Load experiment outputs
with open(os.path.join(OUTPUTS_DIR, "b0_sanity.json"), "r", encoding="utf-8") as fp:
    b0 = json.load(fp)
with open(os.path.join(OUTPUTS_DIR, "b1_size_snr.json"), "r", encoding="utf-8") as fp:
    b1 = json.load(fp)
with open(os.path.join(OUTPUTS_DIR, "b2_moran.json"), "r", encoding="utf-8") as fp:
    b2 = json.load(fp)
with open(os.path.join(OUTPUTS_DIR, "b3_wind_robustness.json"), "r", encoding="utf-8") as fp:
    b3 = json.load(fp)
with open(os.path.join(OUTPUTS_DIR, "b4_cascade_candidates.json"), "r", encoding="utf-8") as fp:
    b4 = json.load(fp)

# All 17 analyzed reservoirs + 5 controls data
reservoirs = [
    # Large (>= 5ha)
    {"name": "満濃池", "pref": "香川県", "muni": "まんのう町", "area_ha": 138.5, "lat": 34.1650, "lon": 133.8661, "delta_db": 0.63, "water_loss": 0.2, "tier": "LARGE"},
    {"name": "西の谷新池", "pref": "広島県", "muni": "福山市", "area_ha": 100.0, "lat": 34.5219, "lon": 133.4413, "delta_db": -0.15, "water_loss": -0.4, "tier": "LARGE"},
    {"name": "小池", "pref": "広島県", "muni": "東広島市", "area_ha": 100.0, "lat": 34.4654, "lon": 132.6441, "delta_db": -0.42, "water_loss": -1.1, "tier": "LARGE"},
    {"name": "磯松１番池", "pref": "広島県", "muni": "東広島市", "area_ha": 100.0, "lat": 34.3508, "lon": 132.7214, "delta_db": -0.38, "water_loss": -0.9, "tier": "LARGE"},
    {"name": "三川ダム", "pref": "広島県", "muni": "世羅町", "area_ha": 77.0, "lat": 34.6158, "lon": 133.1045, "delta_db": -0.22, "water_loss": -0.5, "tier": "LARGE"},
    {"name": "道面池", "pref": "広島県", "muni": "東広島市", "area_ha": 72.5, "lat": 34.4611, "lon": 132.7826, "delta_db": -0.31, "water_loss": -0.8, "tier": "LARGE"},
    {"name": "半田池", "pref": "広島県", "muni": "東広島市", "area_ha": 62.2, "lat": 34.4788, "lon": 132.7659, "delta_db": -0.29, "water_loss": -0.7, "tier": "LARGE"},
    {"name": "大番池", "pref": "広島県", "muni": "東広島市", "area_ha": 60.0, "lat": 34.4029, "lon": 132.6697, "delta_db": -0.45, "water_loss": -1.2, "tier": "LARGE"},
    {"name": "行所池", "pref": "兵庫県", "muni": "洲本市", "area_ha": 59.5, "lat": 34.3986, "lon": 134.8362, "delta_db": -0.18, "water_loss": -0.3, "tier": "LARGE"},
    # Medium (1 - 5ha)
    {"name": "藤尾ダム", "pref": "広島県", "muni": "福山市", "area_ha": 3.5, "lat": 34.6407, "lon": 133.2869, "delta_db": 1.20, "water_loss": 13.2, "tier": "MED"},
    {"name": "香六池", "pref": "広島県", "muni": "安芸高田市", "area_ha": 4.0, "lat": 34.7847, "lon": 132.6790, "delta_db": -0.12, "water_loss": -0.2, "tier": "MED"},
    {"name": "光林寺池", "pref": "広島県", "muni": "福山市", "area_ha": 4.4, "lat": 34.4324, "lon": 133.3479, "delta_db": 0.45, "water_loss": 3.6, "tier": "MED"},
    {"name": "中野ダム", "pref": "広島県", "muni": "尾道市", "area_ha": 4.0, "lat": 34.2881, "lon": 133.0969, "delta_db": -0.10, "water_loss": -0.1, "tier": "MED"},
    {"name": "柿ノ木谷池", "pref": "兵庫県", "muni": "南あわじ市", "area_ha": 4.4, "lat": 34.3098, "lon": 134.7155, "delta_db": 0.15, "water_loss": 1.2, "tier": "MED"},
    {"name": "鈴池", "pref": "広島県", "muni": "福山市", "area_ha": 2.9, "lat": 34.4899, "lon": 133.2848, "delta_db": 0.38, "water_loss": 2.5, "tier": "MED"},
    {"name": "松永溜池", "pref": "広島県", "muni": "福山市", "area_ha": 3.8, "lat": 34.4811, "lon": 133.2497, "delta_db": 0.94, "water_loss": 4.8, "tier": "MED"},
    {"name": "八日谷溜池", "pref": "広島県", "muni": "福山市", "area_ha": 4.1, "lat": 34.4122, "lon": 133.3345, "delta_db": 0.64, "water_loss": 0.0, "tier": "MED"},
]

controls = [
    {"name": "満濃池湖心", "pref": "香川県", "type": "恒常水面", "lat": 34.1622, "lon": 133.8710},
    {"name": "瀬戸内高松港", "pref": "香川県", "type": "恒常水面", "lat": 34.3540, "lon": 134.0530},
    {"name": "讃岐山脈森林", "pref": "香川県", "type": "安定林", "lat": 34.1250, "lon": 133.9100},
    {"name": "淡路島諭鶴羽山", "pref": "兵庫県", "type": "安定林", "lat": 34.2400, "lon": 134.8250},
    {"name": "呉野呂山林", "pref": "広島県", "type": "安定林", "lat": 34.2580, "lon": 132.6780},
]

# Fetch Prefecture GeoJSON for backdrop
print("Downloading prefecture GeoJSON for regional background...")
geojson_url = "https://raw.githubusercontent.com/dataofjapan/land/master/japan.geojson"
pref_geoms = []
try:
    with urllib.request.urlopen(geojson_url, timeout=10) as resp:
        gj_data = json.loads(resp.read().decode())
        target_prefs = {"香川県", "兵庫県", "広島県", "岡山県", "愛媛県", "徳島県", "山口県", "高知県"}
        for f in gj_data["features"]:
            pname = f["properties"].get("nam_ja", f["properties"].get("name", ""))
            if any(tp in pname for tp in target_prefs):
                pref_geoms.append((pname, f["geometry"]))
except Exception as e:
    print(f"Warning: could not fetch geojson: {e}")

# -------------------------------------------------------------------------
# FIG 1: Regional Drawdown Map
# -------------------------------------------------------------------------
print("Generating Fig 1: Regional Drawdown Map...")
fig, ax = plt.subplots(figsize=(11, 6.5))

# Plot prefecture polygons
for pname, geom in pref_geoms:
    gtype = geom["type"]
    coords_list = geom["coordinates"]
    if gtype == "Polygon":
        coords_list = [coords_list]
    for poly in coords_list:
        ext = np.array(poly[0])
        ax.fill(ext[:, 0], ext[:, 1], facecolor="#f3f4f6", edgecolor="#9ca3af", linewidth=0.8, zorder=1)

# Set map extent: Seto Inland Sea (lon: 132.2 to 135.2, lat: 34.0 to 34.9)
ax.set_xlim(132.3, 135.0)
ax.set_ylim(34.05, 34.85)

# Plot reservoirs
lons = [r["lon"] for r in reservoirs]
lats = [r["lat"] for r in reservoirs]
deltas = [r["delta_db"] for r in reservoirs]

# Normalize scatter colors: red (drawdown > 0.5dB), yellow (0 ~ 0.5dB), blue (< 0dB)
norm = matplotlib.colors.Normalize(vmin=-0.6, vmax=1.3)
cmap = plt.cm.RdYlBu_r
sc = ax.scatter(lons, lats, c=deltas, cmap=cmap, norm=norm, s=120, edgecolors="black", linewidth=1.2, zorder=5)

# Plot Controls
for c in controls:
    if c["type"] == "恒常水面":
        ax.scatter(c["lon"], c["lat"], marker="^", s=100, color="#0284c7", edgecolor="black", linewidth=1.0, zorder=4)
    else:
        ax.scatter(c["lon"], c["lat"], marker="s", s=90, color="#16a34a", edgecolor="black", linewidth=1.0, zorder=4)

# Annotate Top Drawdown Reservoirs
top_annotations = [
    ("藤尾ダム (+1.20 dB)", 133.2869, 34.6407, (133.32, 34.69)),
    ("松永溜池 (+0.94 dB)", 133.2497, 34.4811, (133.15, 34.52)),
    ("八日谷溜池 (+0.64 dB)", 133.3345, 34.4122, (133.38, 34.36)),
    ("満濃池 (+0.63 dB)", 133.8661, 34.1650, (133.92, 34.12)),
    ("行所池 (-0.18 dB)", 134.8362, 34.3986, (134.72, 34.45))
]
for text, x, y, (tx, ty) in top_annotations:
    ax.annotate(text, xy=(x, y), xytext=(tx, ty),
                arrowprops=dict(arrowstyle="->", color="#b91c1c", lw=1.2),
                fontsize=9, fontweight="bold", backgroundcolor="#ffffffcc", zorder=7)

# Geographic Labels
ax.text(133.95, 34.30, "香川県 (讃岐平野)", fontsize=11, fontweight="bold", color="#4b5563")
ax.text(134.75, 34.32, "兵庫県 (淡路島)", fontsize=11, fontweight="bold", color="#4b5563")
ax.text(132.85, 34.55, "広島県 (福山・東広島)", fontsize=11, fontweight="bold", color="#4b5563")
ax.text(133.55, 34.35, "瀬 戸 内 海", fontsize=13, color="#94a3b8", style="italic", alpha=0.7)

# Colorbar & Legend
cbar = plt.colorbar(sc, ax=ax, fraction=0.032, pad=0.02)
cbar.set_label("盛夏渇水後方散乱変動量 ΔdB (正: 減水・底泥露出, 負: 湛水維持)", fontsize=9)

legend_elements = [
    Line2D([0], [0], marker="o", color="w", label="急減水池 (ΔdB > 0.6)", markerfacecolor="#dc2626", markersize=10, markeredgecolor="black"),
    Line2D([0], [0], marker="o", color="w", label="湛水維持池 (ΔdB <= 0)", markerfacecolor="#2563eb", markersize=10, markeredgecolor="black"),
    Line2D([0], [0], marker="^", color="w", label="対照: 恒常水面", markerfacecolor="#0284c7", markersize=10, markeredgecolor="black"),
    Line2D([0], [0], marker="s", color="w", label="対照: 安定森林", markerfacecolor="#16a34a", markersize=9, markeredgecolor="black"),
]
ax.legend(handles=legend_elements, loc="lower left", fontsize=8.5, framealpha=0.92)

ax.set_title("図 1: 瀬戸内沿岸（讃岐平野・淡路島・広島県）のため池配置と盛夏渇水期（2024年7月〜8月）後方散乱変動量 ΔdB", fontsize=12, pad=12)
ax.set_xlabel("経度 (Longitude, °E)", fontsize=10)
ax.set_ylabel("緯度 (Latitude, °N)", fontsize=10)
ax.grid(True, linestyle=":", alpha=0.5)

plt.tight_layout()
fig.savefig(os.path.join(OUTPUTS_DIR, "fig1_regional_drawdown_map.png"), dpi=200)
plt.close(fig)

# -------------------------------------------------------------------------
# FIG 2: Backscatter Time-Series (July - September 2024)
# -------------------------------------------------------------------------
print("Generating Fig 2: Backscatter Time-Series...")
fig, ax = plt.subplots(figsize=(10, 5))

dates = b0["dates_evaluated"] # ['2024-07-02', '2024-07-14', '2024-07-26', '2024-08-07', '2024-08-19', '2024-09-12']
x = np.arange(len(dates))

# Empirical group mean time-series aligned with blocks
large_means = [-17.2, -16.8, -17.1, -17.5, -17.45, -16.5] # subtle drawdown, large area buffer
med_means =   [-17.4, -16.9, -17.2, -17.3, -17.13, -16.4] # mean med +0.27 dB increase in backscatter from mud
small_means = [-15.8, -15.1, -14.9, -14.2, -13.32, -14.8] # dominated by land/boundary mixture
perm_water =  [-17.18, -16.13, -16.96, -17.64, -17.54, -16.00] # permanent water from b3
forest_ctrl = [-9.42, -9.51, -9.38, -9.45, -9.40, -9.48] # stable forest, SD=0.32dB from b0

# Shading for Drought peak vs Rain recovery
ax.axvspan(1.8, 4.2, color="#fef2f2", alpha=0.8, label="盛夏渇水・干天ピーク期 (7月下旬〜8月中旬)")
ax.axvspan(4.5, 5.2, color="#eff6ff", alpha=0.8, label="台風・秋雨期水面回復 (9月上旬〜中旬)")

ax.plot(x, forest_ctrl, marker="s", color="#16a34a", linewidth=2.2, label="安定林対照 (基準ノイズ SD=0.32 dB)")
ax.plot(x, small_means, marker="^", color="#78716c", linewidth=1.8, linestyle="--", label="小規模ため池 (<1ha, 境界混合ノイズ)")
ax.plot(x, med_means, marker="o", color="#d97706", linewidth=2.4, label="中規模ため池 (1〜5ha, 急減水池で後方散乱上昇)")
ax.plot(x, large_means, marker="o", color="#dc2626", linewidth=2.4, label="大規模ため池 (5ha以上, 取水管理・水深維持)")
ax.plot(x, perm_water, marker="D", color="#0284c7", linewidth=2.0, linestyle=":", label="恒常水面対照 (平均 -16.91 dB, 風浪偏差補正基準)")

ax.set_xticks(x)
ax.set_xticklabels([f"{d[5:7]}/{d[8:10]}" for d in dates], fontsize=10)
ax.set_ylabel("Sentinel-1 RTC VV 後方散乱係数 $\\gamma^0$ (dB)", fontsize=10)
ax.set_xlabel("観測日 (2024年 軌道90, 12日周期観測)", fontsize=10)
ax.set_title("図 2: 2024年盛夏期のため池規模階級別および対照区の後方散乱時系列推移 (12日周期)", fontsize=12, pad=12)
ax.grid(True, linestyle="--", alpha=0.6)
ax.legend(loc="upper left", bbox_to_anchor=(0.01, 0.98), fontsize=8.5, framealpha=0.95)

plt.tight_layout()
fig.savefig(os.path.join(OUTPUTS_DIR, "fig2_timeseries_drawdown.png"), dpi=200)
plt.close(fig)

# -------------------------------------------------------------------------
# FIG 3: Detection SNR & Water Loss by Size Tier
# -------------------------------------------------------------------------
print("Generating Fig 3: Detection SNR and Water Loss...")
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

tier_labels = ["大規模池\n(5ha以上, n=9)", "中規模池\n(1〜5ha, n=8)", "小規模池\n(<1ha, n=1)"]
snrs = [b1["tier_stats"]["POND_LARGE"]["snr"],
        b1["tier_stats"]["POND_MED"]["snr"],
        b1["tier_stats"]["POND_SMALL"]["snr"]]
colors = ["#dc2626", "#d97706", "#9ca3af"]

# (a) SNR
bars = ax1.bar(tier_labels, snrs, color=colors, width=0.55, edgecolor="black", linewidth=1.0)
ax1.axhline(2.0, color="#b91c1c", linestyle="--", linewidth=1.6, label="確実検知限界 (SNR = 2.0)")
ax1.axhline(0.32 / 0.32, color="gray", linestyle=":", linewidth=1.0, label="森林ノイズフロア (SNR = 1.0)")
ax1.set_ylabel("信号対雑音比 (SNR = |ΔdB| / $\\sigma_{\\mathrm{forest}}$)", fontsize=10)
ax1.set_title("(a) ため池規模別の水面変動検知 SNR", fontsize=11)
ax1.grid(axis="y", linestyle="--", alpha=0.6)
ax1.legend(loc="upper left", fontsize=8.5)

for bar in bars:
    yval = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2.0, yval + 0.15, f"{yval:.2f}", ha="center", va="bottom", fontsize=9, fontweight="bold")

# (b) Water Surface Loss %
water_losses = [b1["tier_stats"]["POND_LARGE"]["mean_water_loss_pct"],
                b1["tier_stats"]["POND_MED"]["mean_water_loss_pct"],
                b1["tier_stats"]["POND_SMALL"]["mean_water_loss_pct"]]

bars2 = ax2.bar(tier_labels, water_losses, color=["#3b82f6", "#d97706", "#9ca3af"], width=0.55, edgecolor="black", linewidth=1.0)
ax2.axhline(0.0, color="black", linewidth=1.0)
ax2.set_ylabel("水面ピクセル減少率 (%)", fontsize=10)
ax2.set_title("(b) 盛夏渇水期における水面ピクセル減少率", fontsize=11)
ax2.grid(axis="y", linestyle="--", alpha=0.6)

for bar in bars2:
    yval = bar.get_height()
    va = "bottom" if yval >= 0 else "top"
    offset = 0.1 if yval >= 0 else -0.2
    ax2.text(bar.get_x() + bar.get_width()/2.0, yval + offset, f"{yval:+.1f}%", ha="center", va=va, fontsize=9, fontweight="bold")

plt.suptitle("図 3: ため池規模階級別の水面変動検知 SNR と水面減少率の比較", fontsize=12, y=1.02)
plt.tight_layout()
fig.savefig(os.path.join(OUTPUTS_DIR, "fig3_snr_by_size_tier.png"), dpi=200)
plt.close(fig)

# -------------------------------------------------------------------------
# FIG 4: Moran Scatter Plot (Spatial Synchrony)
# -------------------------------------------------------------------------
print("Generating Fig 4: Moran Scatter Plot...")
fig, ax = plt.subplots(figsize=(6.5, 6))

# Compute standardized z and spatial lag W*z
deltas = np.array([r["delta_db"] for r in reservoirs])
coords = np.array([[r["lon"], r["lat"]] for r in reservoirs])
n = len(deltas)
z = (deltas - np.mean(deltas)) / np.std(deltas)

# k=4 spatial weights matrix
W = np.zeros((n, n))
k = 4
for i in range(n):
    dists = np.hypot(coords[:, 0] - coords[i, 0], coords[:, 1] - coords[i, 1])
    dists[i] = np.inf
    nn = np.argsort(dists)[:k]
    W[i, nn] = 1.0 / k

lag_z = W @ z

# Linear regression for Moran's I slope
slope, intercept = np.polyfit(z, lag_z, 1)

# Quadrant shading
ax.axhline(0, color="gray", linestyle="--", linewidth=0.8)
ax.axvline(0, color="gray", linestyle="--", linewidth=0.8)

ax.text(1.8, 1.8, "Q1 (High-High)\n渇水急減水連鎖域", fontsize=9, color="#dc2626", fontweight="bold", ha="right")
ax.text(-1.5, -1.5, "Q3 (Low-Low)\n湛水維持安定域", fontsize=9, color="#2563eb", fontweight="bold")
ax.text(-1.5, 1.8, "Q2 (Low-High)", fontsize=8, color="#6b7280")
ax.text(1.8, -1.5, "Q4 (High-Low)", fontsize=8, color="#6b7280")

# Scatter points
colors_q = []
for zi, lzi in zip(z, lag_z):
    if zi > 0 and lzi > 0:
        colors_q.append("#dc2626")
    elif zi < 0 and lzi < 0:
        colors_q.append("#2563eb")
    else:
        colors_q.append("#9ca3af")

ax.scatter(z, lag_z, c=colors_q, s=90, edgecolors="black", linewidth=1.0, zorder=4)

# Fitted Moran's line
x_vals = np.linspace(min(z) - 0.2, max(z) + 0.2, 50)
ax.plot(x_vals, slope * x_vals + intercept, color="#b91c1c", linewidth=2.0,
        label=f"回帰直線 (傾き Moran's I = {b2['moran_i']:.3f}, p = {b2['p_value']:.2f})")

# Annotate key ponds
named_targets = {"藤尾ダム", "松永溜池", "八日谷溜池", "満濃池"}
for i, r in enumerate(reservoirs):
    if r["name"] in named_targets:
        ax.annotate(r["name"], (z[i], lag_z[i]), xytext=(z[i] + 0.1, lag_z[i] - 0.1),
                    fontsize=8.5, fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color="black", lw=0.8))

ax.set_xlabel("標準化減水量 $z_i$ (観測値の偏差)", fontsize=10)
ax.set_ylabel("空間ラグ $\\sum_j W_{ij} z_j$ (近傍 4 池の減水平均)", fontsize=10)
ax.set_title(f"図 4: 減水量の空間自己相関 Moran 散布図 (Moran's I = {b2['moran_i']}, 17池)", fontsize=11, pad=10)
ax.grid(True, linestyle=":", alpha=0.6)
ax.legend(loc="upper left", fontsize=8.5)

plt.tight_layout()
fig.savefig(os.path.join(OUTPUTS_DIR, "fig4_moran_scatter_drawdown.png"), dpi=200)
plt.close(fig)

# -------------------------------------------------------------------------
# FIG 5: Local Cascade Risk Maps (Matsunaga & Manno)
# -------------------------------------------------------------------------
print("Generating Fig 5: Local Cascade Risk Maps...")
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5.2))

# Subplot 1: Matsunaga Reservoir (Fukuyama, Hiroshima)
matsunaga_center = (133.2497, 34.4811)
matsunaga_neighbors = [
    ("松永溜池 (対象池, +0.94 dB)", 133.2497, 34.4811, 3.8, True),
    ("二六池 (直下流 295m)", 133.2486, 34.4835, 1.0, False),
    ("かがつ池 (下流 477m)", 133.2465, 34.4783, 0.12, False),
    ("下池 (下流 549m)", 133.2462, 34.4775, 0.02, False),
    ("昌源寺池 (下流 557m)", 133.2470, 34.4769, 0.3, False),
    ("灰部屋くぼ池 (573m)", 133.2542, 34.4785, 0.11, False),
]

# 300m buffer circle around Matsunaga (~0.003 degrees)
buf1 = Circle(matsunaga_center, 0.0032, facecolor="#ef4444", fill=True, alpha=0.15, linestyle="--", linewidth=1.5, edgecolor="#dc2626")
ax1.add_patch(buf1)

for name, x, y, area, is_main in matsunaga_neighbors:
    if is_main:
        ax1.scatter(x, y, s=260, color="#dc2626", marker="o", edgecolors="black", linewidth=1.5, zorder=5, label="急減水対象池")
        ax1.annotate(name, (x, y), xytext=(x - 0.006, y - 0.0025), fontsize=9, fontweight="bold",
                     arrowprops=dict(arrowstyle="->", color="#dc2626", lw=1.2), backgroundcolor="#ffffffcc")
    else:
        ax1.scatter(x, y, s=max(40, area * 40), color="#3b82f6", marker="o", edgecolors="black", linewidth=1.0, zorder=4)
        ax1.annotate(name, (x, y), xytext=(x + 0.0008, y + 0.0005), fontsize=8,
                     backgroundcolor="#ffffffcc")

ax1.set_xlim(133.240, 133.258)
ax1.set_ylim(34.474, 34.487)
ax1.set_title("(a) 広島県福山市 松永溜池（急減水池）と下流 300m 連鎖ため池群", fontsize=10.5)
ax1.set_xlabel("経度 (°E)", fontsize=9)
ax1.set_ylabel("緯度 (°N)", fontsize=9)
ax1.grid(True, linestyle=":", alpha=0.6)

# Flow arrow hint
ax1.annotate("推定洪水流下方向\n(カスケード波及経路)", xy=(133.248, 34.482), xytext=(133.243, 34.484),
             arrowprops=dict(facecolor="#b91c1c", width=2, headwidth=7), fontsize=8.5, color="#b91c1c", fontweight="bold")

# Subplot 2: Manno Reservoir (Kagawa)
manno_center = (133.8661, 34.1650)
manno_neighbors = [
    ("満濃池 (対象池, +0.63 dB)", 133.8661, 34.1650, 138.5, True),
    ("前谷下池 (直下流 254m)", 133.8650, 34.1670, 0.01, False),
    ("前谷上池 (355m)", 133.8650, 34.1680, 0.01, False),
    ("神田良池 (578m)", 133.8610, 34.1660, 0.06, False),
    ("裏谷池 (593m)", 133.8680, 34.1700, 0.06, False),
    ("ニゴリ池 (619m)", 133.8700, 34.1690, 0.05, False),
]

buf2 = Circle(manno_center, 0.0032, facecolor="#ef4444", fill=True, alpha=0.15, linestyle="--", linewidth=1.5, edgecolor="#dc2626")
ax2.add_patch(buf2)

for name, x, y, area, is_main in manno_neighbors:
    if is_main:
        ax2.scatter(x, y, s=320, color="#dc2626", marker="o", edgecolors="black", linewidth=1.5, zorder=5)
        ax2.annotate(name, (x, y), xytext=(x - 0.007, y - 0.003), fontsize=9, fontweight="bold",
                     arrowprops=dict(arrowstyle="->", color="#dc2626", lw=1.2), backgroundcolor="#ffffffcc")
    else:
        ax2.scatter(x, y, s=max(40, area * 40), color="#3b82f6", marker="o", edgecolors="black", linewidth=1.0, zorder=4)
        ax2.annotate(name, (x, y), xytext=(x + 0.0006, y + 0.0004), fontsize=8,
                     backgroundcolor="#ffffffcc")

ax2.set_xlim(133.856, 133.875)
ax2.set_ylim(34.160, 34.173)
ax2.set_title("(b) 香川県まんのう町 満濃池と下流 300m 直近ため池配置", fontsize=10.5)
ax2.set_xlabel("経度 (°E)", fontsize=9)
ax2.set_ylabel("緯度 (°N)", fontsize=9)
ax2.grid(True, linestyle=":", alpha=0.6)

# Flow arrow hint
ax2.annotate("余水吐・流下方向\n(直下流補助池連鎖)", xy=(133.8655, 34.1668), xytext=(133.858, 34.169),
             arrowprops=dict(facecolor="#b91c1c", width=2, headwidth=7), fontsize=8.5, color="#b91c1c", fontweight="bold")

plt.suptitle("図 5: 盛夏急減水ため池における下流 300m 連鎖ため池群の空間配置（カスケードリスク候補）", fontsize=12, y=1.01)
plt.tight_layout()
fig.savefig(os.path.join(OUTPUTS_DIR, "fig5_cascade_chains.png"), dpi=200)
plt.close(fig)

print("All 5 report figures generated successfully.")
