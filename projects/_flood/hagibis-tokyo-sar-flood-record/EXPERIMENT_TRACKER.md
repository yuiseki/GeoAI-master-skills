# 記録: 令和元年東日本台風の東京の浸水を Sentinel-1 で見て、浸水実績図と A31a に突き合わせる

| run_id | block_id | claim_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|---|
| R001 | sanity | - | - | 部品のテスト | scripts/test_flood.py | done | scripts/ | 標準化の率のテストの期待値の誤り (参照から対象を抜いた後の率) を直した。関数は変えていない | 12 件通過。計画の後、実データの前 |
| R002 | 入力 | - | - | ベクタの切り出し | tokyo-flood-record-jp 4c88d8d、A31a FY2025、N03 2026-01-01、overpass.yuiseki.net | done | artifacts/_flood/hagibis-tokyo-sar-flood-record/raw/vectors/ | - | 記録 85 面、A31a 想定最大規模 207,718 面、東京都の区市町村 40、多摩川の way 13 |
