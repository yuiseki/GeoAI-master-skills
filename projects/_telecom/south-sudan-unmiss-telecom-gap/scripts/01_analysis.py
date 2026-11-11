import duckdb
import pandas as pd
import json
import os
import geopandas as gpd
from shapely.geometry import Point

os.makedirs('projects/_telecom/south-sudan-unmiss-telecom-gap/outputs', exist_ok=True)
conn = duckdb.connect()

# 1. WDI analysis
wdi_q = """
SELECT 
    d.indicator_code, 
    s."Indicator Name" as indicator_name, 
    d.year, 
    d.value
FROM 'data/cache/wdi_data.parquet' d
JOIN 'data/cache/wdi_series.parquet' s ON d.indicator_code = s."Series Code"
WHERE d.country_code = 'SSD'
  AND d.indicator_code IN (
      'EG.ELC.ACCS.ZS',       -- Access to electricity (% of population)
      'EG.ELC.ACCS.RU.ZS',    -- Access to electricity, rural (% of rural population)
      'EG.ELC.ACCS.UR.ZS',    -- Access to electricity, urban (% of urban population)
      'IT.NET.USER.ZS',       -- Individuals using the Internet (% of population)
      'IT.NET.BBND.P2',       -- Fixed broadband subscriptions (per 100 people)
      'IT.CEL.SETS.P2',       -- Mobile cellular subscriptions (per 100 people)
      'SP.POP.TOTL'           -- Population, total
  )
ORDER BY d.indicator_code, d.year DESC
"""
wdi_df = conn.sql(wdi_q).df()
latest_wdi = wdi_df.groupby('indicator_code').head(1)
latest_wdi.to_csv('projects/_telecom/south-sudan-unmiss-telecom-gap/outputs/wdi_national_indicators.csv', index=False, encoding='utf-8')

# 2. OpenCelliD national distribution
cell_q = """
SELECT 
    radio,
    count(*) as cell_count,
    round(min(lon), 4) as min_lon,
    round(max(lon), 4) as max_lon,
    round(min(lat), 4) as min_lat,
    round(max(lat), 4) as max_lat
FROM 'data/cache/cell_towers.parquet'
WHERE mcc = 659
GROUP BY radio
ORDER BY cell_count DESC
"""
cell_df = conn.sql(cell_q).df()
cell_df.to_csv('projects/_telecom/south-sudan-unmiss-telecom-gap/outputs/opencellid_summary.csv', index=False, encoding='utf-8')

# 3. UNMISS deployments across all years
pko_all_q = """
SELECT 
    year,
    count(DISTINCT map_date) as map_dates_count,
    count(*) as total_units_recorded,
    count(DISTINCT (round(lon, 4), round(lat, 4))) as distinct_sites_count
FROM (
    SELECT 2022 as year, * FROM read_json_auto('data/cache/pko_points_2022.jsonl') WHERE mission = 'UNMISS'
    UNION ALL
    SELECT 2023 as year, * FROM read_json_auto('data/cache/pko_points_2023.jsonl') WHERE mission = 'UNMISS'
    UNION ALL
    SELECT 2024 as year, * FROM read_json_auto('data/cache/pko_points_2024.jsonl') WHERE mission = 'UNMISS'
    UNION ALL
    SELECT 2025 as year, * FROM read_json_auto('data/cache/pko_points_2025.jsonl') WHERE mission = 'UNMISS'
)
GROUP BY year
ORDER BY year
"""
pko_years_df = conn.sql(pko_all_q).df()
pko_years_df.to_csv('projects/_telecom/south-sudan-unmiss-telecom-gap/outputs/unmiss_annual_summary.csv', index=False, encoding='utf-8')

# 4. UNMISS latest deployment sites (2024-10-25) & Distance to cell towers
spatial_match_q = """
WITH pko AS (
    SELECT 
        nearest_text as site_name, 
        count(*) as deployed_units, 
        round(lon, 4) as site_lon, 
        round(lat, 4) as site_lat
    FROM read_json_auto('data/cache/pko_points_2024.jsonl')
    WHERE mission = 'UNMISS' AND map_date = '20241025'
    GROUP BY nearest_text, round(lon, 4), round(lat, 4)
),
cells AS (
    SELECT radio, lon as cell_lon, lat as cell_lat
    FROM 'data/cache/cell_towers.parquet'
    WHERE mcc = 659
)
SELECT 
    p.site_name,
    p.deployed_units,
    p.site_lon,
    p.site_lat,
    round(min(sqrt((c.cell_lon - p.site_lon)*(c.cell_lon - p.site_lon)*cos(radians(p.site_lat))*cos(radians(p.site_lat)) + (c.cell_lat - p.site_lat)*(c.cell_lat - p.site_lat))) * 111.32, 2) as dist_any_cell_km,
    round(min(CASE WHEN c.radio = 'LTE' THEN sqrt((c.cell_lon - p.site_lon)*(c.cell_lon - p.site_lon)*cos(radians(p.site_lat))*cos(radians(p.site_lat)) + (c.cell_lat - p.site_lat)*(c.cell_lat - p.site_lat)) END) * 111.32, 2) as dist_lte_km
FROM pko p
CROSS JOIN cells c
GROUP BY p.site_name, p.deployed_units, p.site_lon, p.site_lat
ORDER BY dist_any_cell_km ASC
"""
site_distance_df = conn.sql(spatial_match_q).df()

# 5. Add OSM Power Infrastructure distance
power_pts = gpd.read_parquet('projects/_telecom/south-sudan-unmiss-telecom-gap/outputs/osm_power_points.parquet')
power_lines = gpd.read_parquet('projects/_telecom/south-sudan-unmiss-telecom-gap/outputs/osm_power_lines.parquet')
ookla_tiles = gpd.read_parquet('projects/_telecom/south-sudan-unmiss-telecom-gap/outputs/ookla_mobile_tiles_ssd.parquet')

power_pts_proj = power_pts.to_crs("EPSG:32636")
power_lines_proj = power_lines.to_crs("EPSG:32636")
ookla_proj = ookla_tiles.to_crs("EPSG:32636")

def calc_proj_dist_km(lon, lat, target_gdf_proj):
    pt = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs("EPSG:32636").values[0]
    return round(float(target_gdf_proj.distance(pt).min() / 1000.0), 2)

site_distance_df['dist_power_line_km'] = [calc_proj_dist_km(r['site_lon'], r['site_lat'], power_lines_proj) for _, r in site_distance_df.iterrows()]
site_distance_df['dist_power_gen_km'] = [calc_proj_dist_km(r['site_lon'], r['site_lat'], power_pts_proj) for _, r in site_distance_df.iterrows()]
site_distance_df['dist_ookla_km'] = [calc_proj_dist_km(r['site_lon'], r['site_lat'], ookla_proj) for _, r in site_distance_df.iterrows()]

# Add coverage threshold flags
site_distance_df['has_cellular_coverage_10km'] = site_distance_df['dist_any_cell_km'] <= 10.0
site_distance_df['has_lte_coverage_10km'] = site_distance_df['dist_lte_km'] <= 10.0
site_distance_df['has_power_line_10km'] = site_distance_df['dist_power_line_km'] <= 10.0
site_distance_df['has_ookla_test_10km'] = site_distance_df['dist_ookla_km'] <= 10.0

site_distance_df.to_csv('projects/_telecom/south-sudan-unmiss-telecom-gap/outputs/unmiss_site_cellular_distance.csv', index=False, encoding='utf-8')

# Key metrics summary for checking
summary_metrics = {
    "total_unmiss_sites": int(len(site_distance_df)),
    "total_unmiss_units": int(site_distance_df['deployed_units'].sum()),
    "sites_with_cellular_10km": int(site_distance_df['has_cellular_coverage_10km'].sum()),
    "sites_with_lte_10km": int(site_distance_df['has_lte_coverage_10km'].sum()),
    "sites_without_cellular_10km": int((~site_distance_df['has_cellular_coverage_10km']).sum()),
    "sites_without_lte_10km": int((~site_distance_df['has_lte_coverage_10km']).sum()),
    "units_without_cellular_10km": int(site_distance_df[~site_distance_df['has_cellular_coverage_10km']]['deployed_units'].sum()),
    "units_without_lte_10km": int(site_distance_df[~site_distance_df['has_lte_coverage_10km']]['deployed_units'].sum()),
    "pct_sites_without_cellular_10km": round(float((~site_distance_df['has_cellular_coverage_10km']).mean() * 100), 2),
    "pct_sites_without_lte_10km": round(float((~site_distance_df['has_lte_coverage_10km']).mean() * 100), 2),
    "pct_units_without_cellular_10km": round(float(site_distance_df[~site_distance_df['has_cellular_coverage_10km']]['deployed_units'].sum() / site_distance_df['deployed_units'].sum() * 100), 2),
    "pct_units_without_lte_10km": round(float(site_distance_df[~site_distance_df['has_lte_coverage_10km']]['deployed_units'].sum() / site_distance_df['deployed_units'].sum() * 100), 2),
    "median_distance_to_cellular_km": round(float(site_distance_df['dist_any_cell_km'].median()), 2),
    "median_distance_to_lte_km": round(float(site_distance_df['dist_lte_km'].median()), 2),
    "max_distance_to_cellular_km": round(float(site_distance_df['dist_any_cell_km'].max()), 2),
    "max_distance_to_lte_km": round(float(site_distance_df['dist_lte_km'].max()), 2),
    "total_mcc659_cells": int(cell_df['cell_count'].sum()),
    "total_mcc659_lte_cells": int(cell_df[cell_df['radio'] == 'LTE']['cell_count'].sum()),
    "total_mcc659_gsm_cells": int(cell_df[cell_df['radio'] == 'GSM']['cell_count'].sum()),
    "total_osm_power_plants_generators": int(len(power_pts)),
    "total_osm_power_lines": int(len(power_lines)),
    "sites_without_power_line_10km": int((~site_distance_df['has_power_line_10km']).sum()),
    "pct_sites_without_power_line_10km": round(float((~site_distance_df['has_power_line_10km']).mean() * 100), 2),
    "median_distance_to_power_line_km": round(float(site_distance_df['dist_power_line_km'].median()), 2),
    "total_ookla_tiles_ssd": int(len(ookla_tiles)),
    "total_ookla_tests_ssd": int(ookla_tiles['tests'].sum()),
    "total_ookla_devices_ssd": int(ookla_tiles['devices'].sum()),
    "ookla_median_download_mbps": round(float(ookla_tiles['avg_d_kbps'].median() / 1000.0), 2),
    "ookla_median_latency_ms": round(float(ookla_tiles['avg_lat_ms'].median()), 2)
}

with open('projects/_telecom/south-sudan-unmiss-telecom-gap/outputs/summary_metrics.json', 'w', encoding='utf-8') as f:
    json.dump(summary_metrics, f, indent=2, ensure_ascii=False)

print("Comprehensive analysis (WDI, OpenCelliD, OSM Power, Ookla) executed successfully.")
print(json.dumps(summary_metrics, indent=2))
