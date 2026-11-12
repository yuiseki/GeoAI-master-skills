import pandas as pd
O="outputs/"
P=pd.read_csv(O+"ward_table.csv"); perm=pd.read_csv(O+"hhi_permutation.csv",dtype={"region_id":str}).set_index("region_id")
P["rid"]=P.region_id.astype(str)
L=["| 区 | 人口 (2020) | 店数 | 1 万人あたり | km² あたり | HHI [95% 区間] | 上位 3 社の割合 | 最大のチェーンと割合 | 店を混ぜた時の HHI の 95% 範囲 |","|---|---:|---:|---:|---:|---|---:|---|---|"]
for r in P.itertuples():
    p=perm.loc[r.rid]
    L.append(f"| {r.region_name} | {r.population:,} | {r.poi} | {r.per_10k:.2f} | {r.per_km2:.1f} | {r.hhi:.3f} [{r.hhi_lo:.3f}, {r.hhi_hi:.3f}] | {r.cr3:.3f} | {r.top_brand} {r.top_brand_share:.3f} | {p.null_lo:.3f} 〜 {p.null_hi:.3f} |")
open(O+"ward_table.md","w",encoding="utf-8").write("\n".join(L)+"\n")
t=pd.read_csv(O+"top10_cells_res9.csv")
L=["| 順位 | セル (H3 res 9) | 店数 | Gi* z | BH で有意 | 区 | 最寄り駅 (OSM、直線 m) | 中心の緯度, 経度 | チェーンの内訳 |","|---:|---|---:|---:|---|---|---|---|---|"]
for r in t.itertuples():
    L.append(f"| {r.rank} | {r.cell} | {r.stores} | {r.gi_z:.2f} | {'はい' if r.gi_hot_BH else 'いいえ'} | {r.ward} | {r.nearest_station} ({r.station_m}) | {r.lat:.5f}, {r.lon:.5f} | {r.chains.replace('(other/unmatched)','その他・不明')} |")
open(O+"top10_cells_res9.md","w",encoding="utf-8").write("\n".join(L)+"\n")
for res in (8,9):
    c=pd.read_csv(O+f"top10_clusters_res{res}.csv")
    L=["| 順位 | セル数 | 店数 | 面積 km² | 中心の緯度, 経度 | 最寄り駅 (直線 m) |","|---:|---:|---:|---:|---|---|"]
    for r in c.itertuples(): L.append(f"| {r.rank} | {r.cells} | {r.stores} | {r.area_km2} | {r.lat:.5f}, {r.lon:.5f} | {r.nearest_station} ({r.station_m}) |")
    open(O+f"top10_clusters_res{res}.md","w",encoding="utf-8").write("\n".join(L)+"\n")
