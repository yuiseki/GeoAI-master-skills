#!/bin/sh
# Map the flood sites by their number of approaches (B8, site access 50 m, R = 100 m) over the B7 blockage edges.
# Run after 09_spot_compare.py and 11_site_approaches.py.
set -e
A=../../../artifacts/_evacuation_shelter/taito-bridge-cut-detour
P=$A/site_approaches
mkdir -p "$P"
uvx --with pandas python - "$P" <<'PY'
import sys
import pandas as pd
p = sys.argv[1]
t = pd.read_csv("outputs/site_approaches/sites.csv")
for name, sel in (("k2", t.k_r100 <= 2), ("k3_4", t.k_r100.between(3, 4)), ("k5", t.k_r100 >= 5)):
    t.loc[sel, ["x", "y"]].to_csv(f"{p}/sites_{name}.csv", index=False)
g = pd.read_csv("outputs/site_approaches/cut_groups.csv")
g[(g.R == 100) & g.site.isin(t.site[t.k_r100 <= 2])][["x", "y"]].to_csv(f"{p}/gates_k2.csv", index=False)
PY
for th in light dark; do
  uvx --with numpy --with duckdb --with shapely --with matplotlib --with pyarrow --with pandas \
    python ../../../.agents/skills/analysis-visualize/scripts/network_map.py "$A/spot_r10_a50_o50/spot_edges.parquet" \
    --crs EPSG:6677 --source "OSM 2026-08-31 (ODbL)、国土地理院 指定緊急避難場所 2026-10-06 取得。加工して作成" \
    --question "台東区の住民が向かう洪水の避難場所は、近づく道がいくつに分かれているか" \
    --value n_flagged --value-label "そこを塞ぐと 1.5 倍以上か届かない出発点" --unit "点" --bins 1 5 20 50 130 --theme "$th" \
    --points "$P/sites_k2.csv,進入路 2 か所の避難場所,^,#d62728" \
    --points "$P/sites_k3_4.csv,進入路 3〜4 か所,^,#ff9f1c" \
    --points "$P/sites_k5.csv,進入路 5 か所以上,^,#3aa0ff" \
    --points "$P/gates_k2.csv,進入路 2 か所の避難場所の進入路,o,#d62728" \
    --title "台東区: 避難場所ごとの進入路の数と、1 か所の封鎖で道のりが大きく伸びる場所" \
    --note "進入路は入口 (地点から 50 m) から 100 m の範囲で数えた。辺の値は B7 (封鎖の半径 10 m)" \
    --png "outputs/site_approaches/map_sites_$th.png"
done
