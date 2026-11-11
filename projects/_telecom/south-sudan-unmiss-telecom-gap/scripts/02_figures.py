import matplotlib.pyplot as plt
import geopandas as gpd
import pandas as pd
import numpy as np
import duckdb
import os
from scipy.interpolate import Rbf
from shapely.geometry import Point

os.makedirs('projects/_telecom/south-sudan-unmiss-telecom-gap/outputs', exist_ok=True)
conn = duckdb.connect()

# 日本語フォント設定
plt.rcParams['font.sans-serif'] = ['Yu Gothic', 'Meiryo', 'MS Gothic', 'Noto Sans JP', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 1. 境界データのロード
ne_countries = gpd.read_parquet('data/cache/ne_countries.parquet')
ssd_boundary = ne_countries[ne_countries['ISO_A3_EH'] == 'SSD']
neighbor_countries = ne_countries[ne_countries['ISO_A3_EH'].isin(['SDN', 'ETH', 'KEN', 'UGA', 'COD', 'CAF'])]

# 2. 携帯電話基地局 (OpenCelliD MCC 659)
cells_df = conn.sql("""
    SELECT radio, lon, lat
    FROM 'data/cache/cell_towers.parquet'
    WHERE mcc = 659
""").df()

# 3. 電力網インフラ (OSM / OpenInfraMap)
power_points = gpd.read_parquet('projects/_telecom/south-sudan-unmiss-telecom-gap/outputs/osm_power_points.parquet')
power_lines = gpd.read_parquet('projects/_telecom/south-sudan-unmiss-telecom-gap/outputs/osm_power_lines.parquet')

# 4. Ookla Speedtest モバイル実測タイル
ookla_tiles = gpd.read_parquet('projects/_telecom/south-sudan-unmiss-telecom-gap/outputs/ookla_mobile_tiles_ssd.parquet')

# 5. UNMISS 展開拠点 (2024-10-25)
sites_df = pd.read_csv('projects/_telecom/south-sudan-unmiss-telecom-gap/outputs/unmiss_site_cellular_distance.csv')

# ==============================================================================
# 図 1: 全国インフラ統合地図 (クレジットを最下部に独立配置)
# ==============================================================================
fig, ax = plt.subplots(figsize=(11, 9.5), dpi=300)

neighbor_countries.plot(ax=ax, color='#f2f2f2', edgecolor='#b0b0b0', linewidth=0.8, zorder=1)
ssd_boundary.plot(ax=ax, color='#faf8f5', edgecolor='#222222', linewidth=1.5, zorder=2)

power_lines.plot(ax=ax, color='#8c564b', linewidth=2.0, alpha=0.85, 
                 label=f'高圧送電線 (OSM, {len(power_lines)}件)', zorder=3)

plants = power_points[power_points['type'] == 'plant']
gens = power_points[power_points['type'].isin(['generator', 'substation'])]
ax.scatter(gens['geometry'].x, gens['geometry'].y, c='#bcbd22', s=16, alpha=0.6, marker='s', 
           label=f'地域独立発電機・太陽光・変電所 ({len(gens)}件)', zorder=4)
ax.scatter(plants['geometry'].x, plants['geometry'].y, c='#8c564b', s=55, alpha=0.9, marker='P', edgecolors='black', linewidth=0.8,
           label=f'主要発電所 ({len(plants)}件)', zorder=5)

gsm_cells = cells_df[cells_df['radio'] == 'GSM']
lte_cells = cells_df[cells_df['radio'] == 'LTE']
ax.scatter(gsm_cells['lon'], gsm_cells['lat'], c='#ff7f0e', s=15, alpha=0.5, 
           label=f'OpenCelliD 2G (GSM) 基地局 ({len(gsm_cells)}基)', zorder=6)
ax.scatter(lte_cells['lon'], lte_cells['lat'], c='#d62728', s=65, marker='^', edgecolors='black', linewidth=0.8,
           label=f'OpenCelliD 4G (LTE) 基地局 ({len(lte_cells)}基・ジュバ限定)', zorder=7)

covered_sites = sites_df[sites_df['has_cellular_coverage_10km']]
uncovered_sites = sites_df[~sites_df['has_cellular_coverage_10km']]

ax.scatter(uncovered_sites['site_lon'], uncovered_sites['site_lat'], 
           s=uncovered_sites['deployed_units']*22,
           c='#1f77b4', edgecolors='#042a42', linewidth=1.4, alpha=0.9, 
           label=f'UNMISS 展開拠点: 通信圏外 ({len(uncovered_sites)}拠点, {uncovered_sites["deployed_units"].sum()}部隊)', 
           zorder=8)

ax.scatter(covered_sites['site_lon'], covered_sites['site_lat'], 
           s=covered_sites['deployed_units']*22,
           c='#2ca02c', edgecolors='#0e3a0e', linewidth=1.6, alpha=0.95,
           label=f'UNMISS 展開拠点: 10km圏内 ({len(covered_sites)}拠点: ジュバ本部, {covered_sites["deployed_units"].sum()}部隊)', 
           zorder=9)

for _, row in sites_df.iterrows():
    if row['deployed_units'] >= 3 or row['site_name'] in ['Juba', 'Malakal', 'Bentiu', 'Bor', 'Kuacjok', 'Bunji']:
        ax.annotate(f"{row['site_name']} ({row['deployed_units']}部隊)", 
                    (row['site_lon'] + 0.06, row['site_lat'] + 0.16),
                    fontsize=8.5, fontweight='bold', color='#111111',
                    bbox=dict(boxstyle='round,pad=0.25', facecolor='white', alpha=0.85, edgecolor='#888888', linewidth=0.5))

ax.set_xlim(23.5, 36.5)
ax.set_ylim(3.2, 12.5)
ax.set_title("南スーダン: UNMISS部隊展開拠点 vs 携帯通信網(OpenCelliD)・電力網(OpenInfraMap)",
             fontsize=12, fontweight='bold', pad=12)
ax.set_xlabel("経度 (度)", fontsize=10, labelpad=8)
ax.set_ylabel("緯度 (度)", fontsize=10)
ax.legend(loc='lower left', frameon=True, facecolor='white', framealpha=0.92, fontsize=8.5)
ax.grid(True, linestyle='--', alpha=0.4)

# クレジットをフィギュア全体の最下部に配置 (軸ラベルと被らない)
fig.text(0.95, 0.015, "調査者：yuiseki (Yui Matsumura), volunteer member of UN Open GIS Initiative, Domain Working Group 7 (\"Smart Maps Group\")",
         fontsize=8, color='#555555', ha='right', va='bottom')

plt.subplots_adjust(left=0.08, right=0.92, top=0.93, bottom=0.08)
fig1_path = 'projects/_telecom/south-sudan-unmiss-telecom-gap/outputs/unmiss_cellular_gap_map.png'
plt.savefig(fig1_path, dpi=300)
plt.close()
print("Saved Fig 1 to", fig1_path)

# ==============================================================================
# 図 2: UNMISS 展開拠点から通信基地局および高圧送電線への離隔距離
# ==============================================================================
fig, ax = plt.subplots(figsize=(11, 8), dpi=300)

sorted_sites = sites_df.sort_values('dist_any_cell_km')
y_pos = range(len(sorted_sites))

ax.barh([p - 0.2 for p in y_pos], sorted_sites['dist_any_cell_km'], height=0.38, 
        color='#1f77b4', alpha=0.85, label='最寄り携帯基地局までの距離 (km)')
ax.barh([p + 0.2 for p in y_pos], sorted_sites['dist_power_line_km'], height=0.38, 
        color='#8c564b', alpha=0.85, label='最寄り高圧送電線までの距離 (km)')
ax.axvline(10, color='red', linestyle='--', linewidth=1.5, label='10 km 到達圏ライン')

ax.set_yticks(y_pos)
ax.set_yticklabels(sorted_sites['site_name'], fontsize=9.5)
ax.set_xlabel("UNMISS 拠点からの測地線距離 (km)", fontsize=10.5)
ax.set_title("UNMISS 展開拠点から通信基地局および高圧送電線への離隔距離", fontsize=12, fontweight='bold', pad=15)
ax.set_xlim(0, 850)
ax.grid(True, axis='x', linestyle='--', alpha=0.5)
ax.legend(loc='lower right', fontsize=9.5, framealpha=0.95)

plt.subplots_adjust(left=0.18, right=0.95, top=0.92, bottom=0.10)
fig2_path = 'projects/_telecom/south-sudan-unmiss-telecom-gap/outputs/unmiss_distance_breakdown.png'
plt.savefig(fig2_path, dpi=300)
plt.close()
print("Saved Fig 2 to", fig2_path)

# ==============================================================================
# 図 3: UNMISS 展開部隊の通信インフラ接続状況 (文字はみ出し完全防止)
# ==============================================================================
fig, ax = plt.subplots(figsize=(9, 6.5), dpi=300)

covered_units = int(covered_sites['deployed_units'].sum())
uncovered_units = int(uncovered_sites['deployed_units'].sum())
total_units = covered_units + uncovered_units

unit_counts = [covered_units, uncovered_units]
colors = ['#2ca02c', '#d62728']

wedges, texts, autotexts = ax.pie(
    unit_counts, 
    autopct='%1.1f%%',
    pctdistance=0.6,
    startangle=140, 
    explode=(0.06, 0),
    colors=colors,
    wedgeprops=dict(edgecolor='#333333', linewidth=1.4)
)

for autotext in autotexts:
    autotext.set_color('white')
    autotext.set_fontsize(12)
    autotext.set_weight('bold')

legend_labels = [
    f'首都ジュバ拠点 (商用通信圏内 10km以内)\n計 {covered_units} 部隊 ({covered_units/total_units*100:.1f}%)',
    f'地方前進拠点 (完全オフグリッド 10km圏外)\n計 {uncovered_units} 部隊 ({uncovered_units/total_units*100:.1f}%)'
]

ax.legend(
    wedges, 
    legend_labels,
    title="部隊の通信接続環境区分",
    title_fontsize=10.5,
    loc="center left",
    bbox_to_anchor=(0.85, 0.5),
    fontsize=9.5,
    frameon=True,
    facecolor='white',
    edgecolor='#cccccc',
    framealpha=0.95
)

ax.set_title("UNMISS 展開部隊の通信インフラ接続状況 (全77部隊の内訳)", fontsize=12.5, fontweight='bold', pad=15)

plt.subplots_adjust(left=0.05, right=0.65, top=0.90, bottom=0.08)
fig3_path = 'projects/_telecom/south-sudan-unmiss-telecom-gap/outputs/unmiss_units_connectivity_pie.png'
plt.savefig(fig3_path, dpi=300)
plt.close()
print("Saved Fig 3 to", fig3_path)

# ==============================================================================
# 図 4: 首都ジュバ周辺のインフラ集積拡大図
# ==============================================================================
fig, ax = plt.subplots(figsize=(9, 7), dpi=300)

ax.set_title("首都ジュバ周辺のインフラ集積拡大図\n(通信基地局・発電施設・高圧送電線が集中)", fontsize=12, fontweight='bold', pad=12)
ssd_boundary.plot(ax=ax, color='#fdfbf7', edgecolor='#444444', linewidth=1)
power_lines.plot(ax=ax, color='#8c564b', linewidth=2.5, zorder=3)
ax.scatter(power_points['geometry'].x, power_points['geometry'].y, c='#8c564b', s=60, marker='P', edgecolors='black', label='発電施設', zorder=4)
ax.scatter(gsm_cells['lon'], gsm_cells['lat'], c='#ff7f0e', s=25, alpha=0.7, label='2G (GSM) 基地局', zorder=5)
ax.scatter(lte_cells['lon'], lte_cells['lat'], c='#d62728', s=90, marker='^', edgecolors='black', label='4G (LTE) 基地局', zorder=6)
juba_site = sites_df[sites_df['site_name'] == 'Juba']
ax.scatter(juba_site['site_lon'], juba_site['site_lat'], s=350, c='#2ca02c', edgecolors='black', linewidth=2, label='UNMISS ジュバ本部 (20部隊)', zorder=7)

ax.set_xlim(31.45, 31.70)
ax.set_ylim(4.70, 4.95)
ax.set_xlabel("経度 (度)", fontsize=10)
ax.set_ylabel("緯度 (度)", fontsize=10)
ax.legend(loc='upper left', fontsize=8.5, framealpha=0.9)
ax.grid(True, linestyle='--', alpha=0.5)

plt.tight_layout()
fig4_path = 'projects/_telecom/south-sudan-unmiss-telecom-gap/outputs/juba_infrastructure_inset.png'
plt.savefig(fig4_path, dpi=300)
plt.close()
print("Saved Fig 4 to", fig4_path)

# ==============================================================================
# 図 5: 最もインフラ隔絶された地方前進拠点 (Bunji) 周辺拡大図
# ==============================================================================
fig, ax = plt.subplots(figsize=(9, 7), dpi=300)

bunji_site = sites_df[sites_df['site_name'] == 'Bunji'].iloc[0]
ax.set_title("極限の孤立拠点: ブンジ (Bunji, 上ナイル州東部) 周辺拡大図\n"
             "通信・電力インフラ皆無 (最寄り基地局: 612km, 送電線: 197km, Ookla観測: 227km)",
             fontsize=11.5, fontweight='bold', pad=12)

neighbor_countries.plot(ax=ax, color='#f2f2f2', edgecolor='#b0b0b0', linewidth=0.8, zorder=1)
ssd_boundary.plot(ax=ax, color='#fdfbf7', edgecolor='#444444', linewidth=1.2, zorder=2)

power_lines.plot(ax=ax, color='#8c564b', linewidth=2.0, zorder=3)
ax.scatter(power_points['geometry'].x, power_points['geometry'].y, c='#8c564b', s=50, marker='P', edgecolors='black', label='発電施設', zorder=4)
ax.scatter(gsm_cells['lon'], gsm_cells['lat'], c='#ff7f0e', s=30, alpha=0.7, label='2G (GSM) 基地局', zorder=5)

bunji_lon = bunji_site['site_lon']
bunji_lat = bunji_site['site_lat']

circle_100km = plt.Circle((bunji_lon, bunji_lat), 0.9, color='#d62728', fill=False, linestyle='--', linewidth=1.5, label='半径 100 km 圏 (基地局・送電線ゼロ)')
ax.add_patch(circle_100km)

ax.scatter([bunji_lon], [bunji_lat], s=300, c='#1f77b4', edgecolors='black', linewidth=2, label=f'UNMISS ブンジ拠点 ({bunji_site["deployed_units"]}部隊)', zorder=7)

ax.annotate(f"Bunji 拠点\n携帯基地局: {bunji_site['dist_any_cell_km']:.0f}km 離隔\n送電線: {bunji_site['dist_power_line_km']:.0f}km 離隔\n速度測定: {bunji_site['dist_ookla_km']:.0f}km 離隔",
            (bunji_lon - 0.7, bunji_lat + 0.3),
            fontsize=9.5, fontweight='bold', color='#900C3F',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='white', alpha=0.9, edgecolor='#900C3F', linewidth=1.2))

ax.set_xlim(32.2, 35.0)
ax.set_ylim(8.5, 11.2)
ax.set_xlabel("経度 (度)", fontsize=10)
ax.set_ylabel("緯度 (度)", fontsize=10)
ax.legend(loc='lower left', fontsize=8.5, framealpha=0.9)
ax.grid(True, linestyle='--', alpha=0.5)

plt.tight_layout()
fig5_path = 'projects/_telecom/south-sudan-unmiss-telecom-gap/outputs/isolated_bunji_inset.png'
plt.savefig(fig5_path, dpi=300)
plt.close()
print("Saved Fig 5 to", fig5_path)

# ==============================================================================
# 図 6: 南スーダン全土 Ookla 実測通信速度ヒートマップ (重なり完全解消版)
# ==============================================================================
fig, ax = plt.subplots(figsize=(11, 9.5), dpi=300)

ax.set_title("南スーダン全土: モバイル実測通信速度ヒートマップ\n(Ookla Open Data 2024年Q2実測・RBF空間内挿による下り速度推定)", fontsize=12, fontweight='bold', pad=12)
ssd_boundary.plot(ax=ax, color='#f5f5f5', edgecolor='#333333', linewidth=1.2, zorder=1)

grid_x = np.linspace(24.0, 36.0, 200)
grid_y = np.linspace(3.5, 12.3, 200)
gx, gy = np.meshgrid(grid_x, grid_y)

pts_x = ookla_tiles['lon'].values
pts_y = ookla_tiles['lat'].values
pts_mbps = (ookla_tiles['avg_d_kbps'] / 1000.0).values

ssd_poly = ssd_boundary.geometry.values[0]
grid_points = [Point(x, y) for x, y in zip(gx.ravel(), gy.ravel())]
mask_within = np.array([ssd_poly.contains(pt) for pt in grid_points]).reshape(gx.shape)

rbf = Rbf(pts_x, pts_y, pts_mbps, function='multiquadric', smooth=1.0)
gz = rbf(gx, gy)
gz = np.clip(gz, 0, 50)
gz_masked = np.ma.masked_where(~mask_within, gz)

cf = ax.contourf(gx, gy, gz_masked, levels=25, cmap='turbo', alpha=0.75, zorder=2)
cbar = plt.colorbar(cf, ax=ax, orientation='vertical', pad=0.02, shrink=0.8)
cbar.set_label('推定下り通信速度 (Mbps)', fontsize=9.5)

ax.scatter(pts_x, pts_y, c='black', s=8, alpha=0.5, label='Ookla 実測サンプル地点 (152タイル)', zorder=3)

ax.scatter(sites_df['site_lon'], sites_df['site_lat'], s=sites_df['deployed_units']*16,
           facecolors='none', edgecolors='red', linewidth=1.6, label='UNMISS 部隊配置拠点', zorder=4)

for _, row in sites_df.iterrows():
    if row['deployed_units'] >= 2 or row['site_name'] in ['Juba', 'Malakal', 'Bentiu', 'Bor', 'Kuacjok', 'Renk', 'Bunji', 'Torit']:
        ax.annotate(f"{row['site_name']}", 
                    (row['site_lon'] + 0.08, row['site_lat'] + 0.12),
                    fontsize=8.5, fontweight='bold', color='#111111',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8, edgecolor='#555555', linewidth=0.5),
                    zorder=5)

ax.set_xlim(23.5, 36.5)
ax.set_ylim(3.2, 12.5)
ax.set_xlabel("経度 (度)", fontsize=10, labelpad=8)
ax.set_ylabel("緯度 (度)", fontsize=10)
ax.legend(loc='lower left', fontsize=8.5, framealpha=0.9)
ax.grid(True, linestyle='--', alpha=0.4)

# クレジットをフィギュア全体の最下部に独立して配置 (経度ラベルとの被りを完全に解消)
fig.text(0.95, 0.015, "調査者：yuiseki (Yui Matsumura), volunteer member of UN Open GIS Initiative, Domain Working Group 7 (\"Smart Maps Group\")",
         fontsize=8, color='#555555', ha='right', va='bottom')

plt.subplots_adjust(left=0.08, right=0.92, top=0.93, bottom=0.08)
fig6_path = 'projects/_telecom/south-sudan-unmiss-telecom-gap/outputs/ookla_speed_heatmap.png'
plt.savefig(fig6_path, dpi=300)
plt.close()
print("Saved Fig 6 (no overlap) to", fig6_path)
