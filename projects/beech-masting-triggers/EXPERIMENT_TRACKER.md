# 記録: ブナの豊凶のトリガー (東北 5 県 × 年)

流すたびに 1 行足す。行を消さない。失敗した実行も残す。計画と違うことをしたら deviation に書く。

| run_id | block_id | claim_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|---|
| R001 | B0 | - | sanity | 東北森林管理局の表の読み取り (`tohoku_index.py`) | buna-57.pdf、buna-55.pdf、buna-56.pdf (2026-10-28 取得、sha256 は json) | done | outputs/tohoku_beech_index.csv | 2011 年の山形の結実時は「凶作 (2.0)」と印刷されている。区分の境目なので丸めの前は 2.0 未満とみて止めずに残す | 345 セル (38 年 × 5 県 × 2 段階、欠け 35: 1989 年の開花時の全県、1990〜2003 年の秋田と山形の開花時、1999 年の秋田と山形の結実時)。2 つのリリースの重なる 335 セルは全て一致。2026 年度の 10 セルは箇所数から計算し直した値と一致 |
| R002 | B0 | - | sanity | Dryad の地点の評価から結実時の指数を作り直して照合 (`dryad_sites.py`) | fagus-crenata-masting-jp-2026-06 db40a09、jp-admin-2026-09 e6c87b1 | done | outputs/dryad_vs_printed_index.json | - | 102 地点は全て市町村の面に 1 つずつ入る。東北 98 地点 (秋田 31、青森 28、山形 23、岩手 13、宮城 3)。県ごとの相関: 青森 0.993、山形 0.988、秋田 0.984、岩手 0.972、宮城 0.952 (3 地点)。同じ調査の一部の地点とみなす |
