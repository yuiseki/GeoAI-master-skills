# 記録: 23 区の浸水の起こりやすさの地図と、国の洪水浸水想定 (A31a) の比較

| run_id | block_id | claim_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|---|
| R001 | sanity | - | - | grid_100 | 入力は scripts/01_fetch.py の固定版 | done | ../../artifacts/tokyo23-flood-record-vs-a31a/grid_100/audit.json | rain_clim の観測所の条件を足した (計画の変更) | 66,460 セル、664.6 km² (区の面 664.5 km²)。標高の無いセル 3,842。陽性セル 学習 13,555、試験 3,057 |
| R002 | B1, B2, B4 | C1, C2, C4 | main | grid_100、学習 1974-1996、試験 1997-2019 | R001 と同じ | done | outputs/b1_main.json | B4 は学習の陽性と履歴が同じ記録から作られて漏れた。設計の誤りとして扱い、B4b を足した | capture@k_A: モデル 0.843、A31a 0.646、でたらめ 0.476。モデル − A31a +0.197 [+0.147, +0.273]、A31a − でたらめ +0.170 [+0.089, +0.218] |
| R003 | B4b | C4 | exploratory | 履歴 1974-1985、ラベル 1986-1996 | R001 と同じ | done | outputs/b4b.json | 計画の変更で足した | 履歴の上乗せ +0.010 [−0.010, +0.028]。効かない |
| R004 | robustness | C1, C2 | robustness | 10 通り (scripts/06_robustness.sh) | R001 と同じ | done | outputs/rob_*.json | - | C1 は 10 通り全てで下限 > 0。C2 は 500 m、250 m ずらし、計画規模、0.5 m 以上で 0 をまたぐ |
| R005 | B3 | C3 | main | セル × 年 1976-2019、試験 1997- | R001 と同じ | done | outputs/b3_main.json | 1 年の 80% 以上の時別値がある本土の観測所は各年 5〜6 地点だけ | AP: 雨なし 0.0087、雨あり 0.0063、雨の並べ替え 0.0060。雨あり − 雨なし −0.0023 [−0.0042, −0.0006]、雨あり − 並べ替え +0.0004 [−0.0013, +0.0023]。C3 は支持されない |
| R006 | maps | - | - | 図 1〜3 (scripts/07_maps.py、08_draw.sh) | R002 の maps_main.parquet | done | outputs/fig*.png | - | 目視で確かめた (R007)。図 3 の凡例の NoData は試験期間に記録の無いセル |
| R007 | checks | - | - | 残差の Moran's I、並べ替えの重要度、図 4 | R002 と同じ | done | outputs/checks.json、outputs/fig4_intervals.png | - | 残差の I: 100 m 0.63、2 km 0.09、5 km 0.03。5 km ブロックでも C1、C2 の下限 > 0。最も効いたのは rel_elev_1000 (0.196) |
