# 記録: 東京 23 区のアンダーパスと国の一覧

| run_id | block_id | claim_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|---|
| R001 | sanity | - | - | 母集団とラベル | osm-tokyo23-src-2026-08@38f7a5f、mlit-underpass@4d00072、mlit-kansui-flood-prone-points-jp-2026-09@d4e2e1f、tokyo-flood-record-jp@354b0d9、jp-admin-2026-09@e6c87b1 | done | outputs/build_summary.json、outputs/unmatched_list_points.csv | - | 主の母集団 252 か所 (課題 28 と同じ)。一覧の 23 区の点 99、うち 24 点は 100 m 以内に区域が無い |
| R002 | B1〜B4 | C1〜C3 | main | 計画の規則 | R001 と同じ | done | outputs/blocks.json、outputs/b4_by_kind.csv | - | C1 支持 (31.7 % [26.3, 37.2])、C2 判定できない (差 0.037 [−0.067, 0.148])、C3 支持 (63.6 % [47.2, 78.1])。載る割合は幹線 77.2 %、細い道路 5.7 % |
| R003 | 頑健性 | C1〜C3 | main | 距離 50、200 m、service、浸水 30 m、内水、ガード下 | R001 と同じ | done | outputs/blocks.json の variants | - | どの行でも C1 支持、C2 判定できない、C3 支持。ガード下 1,153 か所のうち載るのは 4.3 % |
| R004 | 図 | C1〜C3 | - | 23 区の地図 | R002 | done | outputs/map_listing.png | - | - |
