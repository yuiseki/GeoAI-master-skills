import duckdb
import pandas as pd
import json
import os
import geopandas as gpd
from shapely.geometry import Point
from spatial_helpers import geodesic_distance_km, within_distance

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

# 4. UNMISS deployment coordinate clusters on the 2024-10-25 source map.
# nearest_text is a map-text hint, not a verified site name.
spatial_match_q = """
WITH pko AS (
    SELECT 
        string_agg(DISTINCT nearest_text, '; ' ORDER BY nearest_text) as map_text_hint,
        count(*) as deployment_records_at_coordinate,
        round(lon, 4) as site_lon, 
        round(lat, 4) as site_lat
    FROM read_json_auto('data/cache/pko_points_2024.jsonl')
    WHERE mission = 'UNMISS' AND map_date = '20241025'
    GROUP BY round(lon, 4), round(lat, 4)
),
cells AS (
    SELECT radio, lon as cell_lon, lat as cell_lat
    FROM 'data/cache/cell_towers.parquet'
    WHERE mcc = 659
)
SELECT p.*, c.radio, c.cell_lon, c.cell_lat
FROM pko p CROSS JOIN cells c
"""
cell_pairs_df = conn.sql(spatial_match_q).df()
site_distance_df = cell_pairs_df[['map_text_hint', 'deployment_records_at_coordinate', 'site_lon', 'site_lat']].drop_duplicates().copy()
cell_pairs_df['dist_cell_record_km'] = geodesic_distance_km(
    cell_pairs_df['site_lon'].to_numpy(), cell_pairs_df['site_lat'].to_numpy(),
    cell_pairs_df['cell_lon'].to_numpy(), cell_pairs_df['cell_lat'].to_numpy(),
)
any_nearest = cell_pairs_df.loc[cell_pairs_df.groupby(['site_lon', 'site_lat'])['dist_cell_record_km'].idxmin()]
site_distance_df = site_distance_df.merge(
    any_nearest[['site_lon', 'site_lat', 'radio', 'dist_cell_record_km']]
        .rename(columns={'radio': 'nearest_cell_record_radio', 'dist_cell_record_km': 'dist_any_cell_record_km'}),
    on=['site_lon', 'site_lat'], how='left', validate='one_to_one')
lte_pairs = cell_pairs_df[cell_pairs_df['radio'] == 'LTE']
lte_nearest = lte_pairs.loc[lte_pairs.groupby(['site_lon', 'site_lat'])['dist_cell_record_km'].idxmin()]
site_distance_df = site_distance_df.merge(
    lte_nearest[['site_lon', 'site_lat', 'dist_cell_record_km']]
        .rename(columns={'dist_cell_record_km': 'dist_lte_cell_record_km'}),
    on=['site_lon', 'site_lat'], how='left', validate='one_to_one')
site_distance_df = site_distance_df.sort_values('dist_any_cell_record_km')

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
site_distance_df['dist_osm_power_related_point_km'] = [calc_proj_dist_km(r['site_lon'], r['site_lat'], power_pts_proj) for _, r in site_distance_df.iterrows()]
site_distance_df['dist_ookla_tile_km'] = [calc_proj_dist_km(r['site_lon'], r['site_lat'], ookla_proj) for _, r in site_distance_df.iterrows()]

# Thresholds classify proximity to records only, not coverage or access.
for column, label in [
    ('dist_any_cell_record_km', 'opencellid_record'),
    ('dist_lte_cell_record_km', 'opencellid_lte_record'),
    ('dist_power_line_km', 'osm_power_line'),
    ('dist_osm_power_related_point_km', 'osm_power_related_point'),
    ('dist_ookla_tile_km', 'ookla_mobile_tile'),
]:
    site_distance_df[f'{label}_within_10km'] = site_distance_df[column].apply(lambda d: within_distance(d, 10) if pd.notna(d) else False)

site_distance_df.to_csv('projects/_telecom/south-sudan-unmiss-telecom-gap/outputs/unmiss_record_proximity.csv', index=False, encoding='utf-8')

# Key metrics summary for checking
summary_metrics = {
    "deployment_coordinate_clusters": int(len(site_distance_df)),
    "deployment_records_on_2024_10_25_source_map": int(site_distance_df['deployment_records_at_coordinate'].sum()),
    "opencellid_mcc659_registered_cell_records": int(cell_df['cell_count'].sum()),
    "opencellid_gsm_records": int(cell_df[cell_df['radio'] == 'GSM']['cell_count'].sum()),
    "opencellid_lte_records": int(cell_df[cell_df['radio'] == 'LTE']['cell_count'].sum()),
    "opencellid_record_distance_median_km": round(float(site_distance_df['dist_any_cell_record_km'].median()), 3),
    "opencellid_record_distance_max_km": round(float(site_distance_df['dist_any_cell_record_km'].max()), 3),
    "coordinate_clusters_with_opencellid_record_within_10km": int(site_distance_df['opencellid_record_within_10km'].sum()),
    "coordinate_clusters_with_ookla_2024_q2_tile_within_10km": int(site_distance_df['ookla_mobile_tile_within_10km'].sum()),
    "coordinate_clusters_with_osm_power_related_point_within_10km": int(site_distance_df['osm_power_related_point_within_10km'].sum()),
    "coordinate_clusters_with_osm_power_line_within_10km": int(site_distance_df['osm_power_line_within_10km'].sum()),
    "osm_power_related_point_records": int(len(power_pts)),
    "osm_power_line_records": int(len(power_lines)),
    "ookla_2024_q2_mobile_tiles": int(len(ookla_tiles)),
    "ookla_2024_q2_tests": int(ookla_tiles['tests'].sum()),
    "sum_of_tile_level_device_counts_not_national_unique": int(ookla_tiles['devices'].sum()),
    "ookla_median_download_mbps_across_tiles": round(float(ookla_tiles['avg_d_kbps'].median() / 1000.0), 2),
    "ookla_median_latency_ms_across_tiles": round(float(ookla_tiles['avg_lat_ms'].median()), 2),
    "interpretation_note": "Spatial thresholds are record-proximity summaries, not coverage, active-service, or operational-access tests."
}

with open('projects/_telecom/south-sudan-unmiss-telecom-gap/outputs/summary_metrics.json', 'w', encoding='utf-8') as f:
    json.dump(summary_metrics, f, indent=2, ensure_ascii=False)

print("Comprehensive analysis (WDI, OpenCelliD, OSM Power, Ookla) executed successfully.")
print(json.dumps(summary_metrics, indent=2))
