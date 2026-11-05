#!/bin/sh
# Draw the main run's shortest-path tree with analysis-visualize/network_map.py, in the dark and light themes.
# Run from the project directory after scripts/06_tree_edges.py.
set -e
A=../../../artifacts/_evacuation_shelter/taito-bridge-cut-detour/main
for th in dark light; do
  uvx --with numpy --with duckdb --with shapely --with matplotlib --with pyarrow --with pandas \
    python ../../../.agents/skills/analysis-visualize/scripts/network_map.py "$A/tree_edges.parquet" \
    --crs EPSG:6677 --source "OSM 2026-08-31 (ODbL)、国土地理院 指定緊急避難場所 2026-10-06 取得。加工して作成" \
    --question "台東区の出発点から洪水の避難場所への最短経路は、どの道に集まり、外すと伸びる橋はどこか" \
    --value n_origins --value-label "経路が通る出発点の数" --unit "点" --bins 1 5 20 80 300 --theme "$th" \
    --highlight lengthening --highlight-label "外すと道のりが伸びる橋" --label-col name \
    --points "$A/sites_xy.csv,避難場所 (洪水),^,#3aa0ff" \
    --title "台東区: 洪水の避難場所への最短経路の重なり (出発点 3,900)" --png "outputs/main/network_tree_$th.png"
done
