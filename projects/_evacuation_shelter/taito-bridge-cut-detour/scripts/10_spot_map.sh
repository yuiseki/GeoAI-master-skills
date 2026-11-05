#!/bin/sh
# Map the main spot-blockage variant with analysis-visualize/network_map.py. Run after 09_spot_compare.py.
set -e
A=../../../artifacts/_evacuation_shelter/taito-bridge-cut-detour
for th in light dark; do
  uvx --with numpy --with duckdb --with shapely --with matplotlib --with pyarrow --with pandas \
    python ../../../.agents/skills/analysis-visualize/scripts/network_map.py "$A/spot_r10_a50_o50/spot_edges.parquet" \
    --crs EPSG:6677 --source "OSM 2026-08-31 (ODbL)、国土地理院 指定緊急避難場所 2026-10-06 取得。加工して作成" \
    --question "台東区で、道のどこか 1 か所 (半径 10 m) が塞がると、洪水の避難場所までの道のりが 1.5 倍以上になるか届かなくなる出発点は、どこを塞いだときに多いか" \
    --value n_flagged --value-label "そこを塞ぐと 1.5 倍以上か届かない出発点" --unit "点" --bins 1 5 20 50 130 --theme "$th" \
    --highlight top --highlight-label "効きの大きい 8 か所 (数は出発点)" --label-col label \
    --points "$A/main/sites_xy.csv,避難場所 (洪水),^,#3aa0ff" \
    --title "台東区: 1 か所の封鎖 (陥没、管の破裂など) で避難の道のりが大きく伸びる場所" \
    --note "封鎖の半径 10 m、避難場所と出発点の入口 50 m" --png "outputs/spot_r10_a50_o50/map_spot_$th.png"
done
