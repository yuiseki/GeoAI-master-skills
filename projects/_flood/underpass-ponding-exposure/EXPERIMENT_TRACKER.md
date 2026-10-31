# 記録: アンダーパスの溜まりやすさの順位

| run_id | block_id | claim_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|---|
| R001 | sanity | - | - | 入力 | 01_fetch.py と README の固定版 | done | - | - | アンダーパス 3,841、冠水想定箇所 4,525、箇所表 4,410、浸水実績 面 5,845 と点 121。OSM の highway の線 10,568,785 のうち点から 400 m の 530,211 (03_roads.py) |
| R002 | sanity | - | - | 東京都の 10 か所の目視 (DEM5A だけ) | R001 と同じ | done | outputs/check_profiles_tokyo.png | 底を縦断の全体で探す規則 (depthw) を探索として足した (計画の変更) | 10 か所とも下を通る道路を選んでいた (対応 3 m 以内)。4 か所で点の上が高く、両側のアプローチだけが低い。9 か所が tunnel の付いた線 |
| R003 | tiles | - | - | 標高タイル | 2026-10-31 取得 | done | ../../../artifacts/_flood/underpass-ponding-exposure/dem/fetch_log.json | - | DEM5A z15 7,198 枚 (404 は 98)、DEM10B z14 3,885 枚 (404 は 1) |
| R004 | B1〜B4 | C1〜C4 | main | 計画の規則 (depth) と探索の規則 (depthw) | R001、R003 | done | outputs/blocks.json | B4 に文章の実績だけの読み方を探索として足した。DEM5A だけとの比較は設計上同じ得点 | C1 支持 (31%)。C2 規則の上で支持 (3 / 6、2 つは 0.5 の際)。C3 支持 (AUC 0.57 [0.43, 0.70])。C4 退けた (0.61 [0.57, 0.64]、文章の実績だけでも 0.60) |
| R005 | report | - | - | report.md | R004 | done | report.md | - | check_report.py --level full で ok |
| R006 | A (探索) | C1〜C4 | exploratory | 途中の節点を通る線もたどる縦断 | R004 と同じ | done | outputs/blocks_vertices.json、outputs/chain_stops_*.json | 結果の後に足した | 測れる箇所 3,256 → 3,304。C1 0.311、C2 3 / 6、C3 0.55 [0.41, 0.69]、C4 0.61 [0.57, 0.64] で判定は変わらない。残りの止まる理由は 45 度より曲がる 275、橋 144、他の種類 22、行き止まり 17 |
| R007 | B (探索) | C1〜C4 | exploratory | Mapterhorn z16 を 3 つ目の DEM にした縦断 (計画の端点の規則) | R004 と同じ。Mapterhorn 0.0.13、2026-10-31 取得 | done | outputs/blocks_mt.json、outputs/check_profiles_tokyo_mt.png、outputs/mt_lost_measurable.txt | 結果の後に足した | 覆いの下は写らない。測れる箇所 2,874 (DEM5A で測れて Mapterhorn で測れない 381 か所は全て周りに 404 のタイル)。C1 0.305、C2 の重なり 0.62、C3 0.53 [0.38, 0.65]、C4 0.60 [0.56, 0.64] で判定は変わらない |
