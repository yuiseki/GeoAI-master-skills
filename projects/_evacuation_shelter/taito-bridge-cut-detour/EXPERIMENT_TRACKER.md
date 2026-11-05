# 記録: 台東区の避難経路の単一構造物切断による迂回

流すたびに 1 行足す。行を消さない。

データの版: gsi-evacuation-sites-jp@d8ad216、osm-japan-src-2026-08@9a9b4a7、estat-census-mesh-2020@6c486c8、jp-admin-2026-09@e6c87b1 (以下「4 版」)。

| run_id | block_id | claim_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|---|
| R001 | B1 | - | sanity | 合成のテスト 6 件 | なし | done | scripts/test_cutdetour.py | - | 全て通過。平行な 3 本の線を 1 本ずつ外すと迂回が出ず、まとめると出ることを確かめた |
| R002 | B2 | C1 | descriptive | main (初回) | 4 版 | abandoned | outputs/main/ (上書き) | D1 | 出発点 4,033 のうち 42 (1.04%) が到達不能。迂回の合計 0 で到達不能の行が多く、川の上の格子点が橋の上の節点に寄せられ、その橋を外すと孤立していた |
| R003 | B2 | C1 | descriptive | main (D1 の後) | 4 版 | abandoned | outputs/main/ (上書き) | D2 | 水面の 133 点を除き 3,900 点。到達不能は 13 点 (0.33%) に減った。残りは節点 2〜20 個、道 13〜416 m の島 (駅の階段、線路の敷地の通路、もみじばしの取り付け) に寄せた点 |
| R004 | B2 | C1 | descriptive | main (D2 の後) | 4 版 | done | outputs/main/ | D3 | 到達不能 0。伸びる点 3.7%、最大の伸び 293 m、500 m 以上 0。Δ の中央値が 0 より大きいメッシュは 57 のうち 1 つ |
| R005 | B4 | C1 | robustness | cluster5、cluster20、sites_taito、corridor、buffer3000、buffer8000、tunnels | 4 版 | done | outputs/robustness.csv | - | 上位 5 の共通は 4〜5。規則の上では C1 支持。ただし主の指標が 0 より大きいメッシュは 1 つだけで、2 位以下は最大の伸びによる並び |
| R006 | B3 | C2 | descriptive | main の構造物を川と線路で集計 | 4 版 | done | outputs/crossing_kinds.csv | - | 線路 7,598.8 m、川 453.9 m。C2 支持 |
| R007 | B3 | - | exploratory | all_rail、all_river (同じ種類の橋を同時に外す) | 4 版 | done | outputs/all_rail/、outputs/all_river/ | D4 | 計画の B3 の「同時に外した場面」。主張の根拠にしない |
| R008 | B6 | - | exploratory | 出発点が公園、霊園、動物園、線路の敷地にあるか、建物の近くか | 4 版 | done | outputs/main/origin_context.json、outputs/main/cells_near_buildings.csv | D5 | 伸びた 144 点のうち 94 点が人の住まない場所。533946712 の中央値は建物の近くの点だけでは 0 |
| R009 | B4 | - | unit | 500 m と 1 km のメッシュ | 4 版 | done | outputs/unit_500m_vs_1km.csv | D5 | 1 km では中央値が 0 より大きいメッシュは 0 |
| R010 | B5 | - | exploratory | allways (歩ける道を 1 本ずつ外す) | 4 版 | running | outputs/allways/ | - | |

## deviation

- D1 (R002 の結果を見た後): 出発点と避難場所を、橋の線だけにつながる節点には寄せないことにした。水面 (OSM の natural=water、waterway=riverbank の面) の中の格子点を出発点から除いた。理由: 川の上の点は住む人がいない。橋の上の節点に寄せると、その橋を外したときに点ごと孤立し、到達不能と読める。結論への効き: 到達不能が 42 から 13 に減った。合成のテスト (test_origin_on_bridge_deck_is_snapped_to_ground) を足した。
- D2 (R003 の結果を見た後): 寄せ先を、橋とトンネルを全て外した地上の道の連結成分のうち、道の総延長が 1 km 以上の成分の節点に限った。理由: 残った到達不能 13 点は、どれも 416 m 以下の小さな島に寄せた点で、住む地区ではない。1 km は、川や線路に囲まれた本物の街区 (道が数 km) と、階段や構内の通路 (数十〜数百 m) を分ける区切りで、根拠のある値ではない。結論への効き: 到達不能が 0 になった。主の指標の順位には、到達不能の 4 つのメッシュの最大値が効かなくなる形で効く。合成のテスト (test_small_ground_pocket_is_not_a_snap_target) を足した。
- D3: 迂回倍率は d0 = 0 の点で NaN になるので、メッシュの倍率の中央値は NaN を除いて取ることにした。主の指標 (Δ の中央値) には効かない。

- D4: 計画では同時に外す場面を B3 に入れていた。実装は変種 all_rail、all_river として 02_run.py に足した。
- D5: 計画に無かった区画 B6 (出発点の場所の印) と、単位の比較 (500 m と 1 km) を、結果を見た後に足した。地図で上野公園と谷中霊園に伸びる点が集まっていたのを見たため。探索として扱う。

D1 と D2 は、決め手の指標 (Δ の中央値の順位) でなく、到達不能の点の中身を見て決めた。ただし結果を見た後の変更なので、B2 は探索として扱う。
