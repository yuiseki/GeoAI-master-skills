#!/usr/bin/env bash
# Draw the maps of the report with analysis-visualize's classify_map.py (run 07_maps.py first).
set -euo pipefail
cd "$(dirname "$0")/.."
V=../../../.agents/skills/analysis-visualize/scripts
M=../../../artifacts/_flood/tokyo23-flood-record-vs-a31a/maps
SRC="tokyo-flood-record-jp@354b0d9, ksj-a31a-flood-tokyo23@5b22592, GSI DEM5A (2026-10-26), OSM 2026-08, WorldCover 2021"
draw() {
  uvx --with numpy --with duckdb --with shapely --with matplotlib python $V/classify_map.py $M/cells_sq.parquet cell "$@" \
    --crs EPSG:6677 --source "$SRC" --no-labels --context $M/wards_6677.parquet --context-name name \
    --context-crs EPSG:6677 --context-source "jp-admin-2026-09@e6c87b1, EPSG:6677" --expect-units 66460
}
draw model_pct --kind level --unit "上位からの百分位" --method fixed --thresholds 1 5 10 20 46.66 --palette YlOrRd_r \
  --title "記録から学んだ地図の順位 (1974〜1996 年の記録で学習)" --png outputs/fig1_model_rank.png
draw agree --kind category --unit "1 両方、2 地図だけ、3 A31a だけ、4 どちらでもない" \
  --title "記録から学んだ地図の上位 46.7% と A31a 想定最大規模の区域" --png outputs/fig2_agreement.png
draw test_cat --kind category --unit "1 両方、2 地図だけ、3 A31a だけ、4 どちらでもない" \
  --title "1997〜2019 年に浸水が記録されたセルは、どちらの地図に入ったか" --png outputs/fig3_test_cells.png
