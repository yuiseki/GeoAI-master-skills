# 記録: 千城台東の団地の解体を Sentinel-1 の時系列で日付けし、周りのタイルの変化を順位付けする

| run_id | block_id | claim_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|---|
| R001 | 正解 | - | - | 写真の見比べ | nendophoto2019、nendophoto2024 (z16、2026-11-03 取得) | done | labels/labels.csv | - | 120 枚に 2 が 18、1 が 17、0 が 85。両端の列 24 枚は写真が欠けて NA。SAR の値を読む前にコミット (9893775) |
| R002 | sanity | - | - | 模擬 | scripts/test_cp.py、scripts/test_rank.py | done | scripts/ | - | 24 件通過。計画の後、実データの前 |
