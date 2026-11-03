# 記録: 千城台東の団地の解体を Sentinel-1 の時系列で日付けし、周りのタイルの変化を順位付けする

| run_id | block_id | claim_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|---|
| R001 | 正解 | - | - | 写真の見比べ | nendophoto2019、nendophoto2024 (z16、2026-11-03 取得) | done | labels/labels.csv | - | 120 枚に 2 が 18、1 が 17、0 が 85。両端の列 24 枚は写真が欠けて NA。SAR の値を読む前にコミット (9893775) |
| R002 | sanity | - | - | 模擬 | scripts/test_cp.py、scripts/test_rank.py | done | scripts/ | - | 24 件通過。計画の後、実データの前 |
| R003 | A2 | C2 | confirmatory | Sentinel-2 の切れ目 (D_opt) | sentinel-2-l2a 54SVE、718 item (2026-11-03 取得) | done | outputs/s2_break.json、outputs/s2_series.csv | - | 80 % 以上晴れた日 436 日、W の中 289 日。D_opt 2023-10-16 (前の晴れた日 2023-08-25)。切れ目の後は全帯域で暗い (B08 0.2291 → 0.0813) |
| R004 | sanity | - | - | 取得と格子 | sentinel-1-rtc 軌道 46、319 item (2026-11-03 取得)、WorldCover 2021 v200 | done | outputs/grid_summary.json | 取得の途中で 1 件の読み込みが失敗して止まり、やり直しを足して残り 4 ファイルを取り直した | 2017-02-18〜2026-10-24 の 279 日 (2019 年度 30 日、2024 年度 26 日)。格子 640 × 643 (EPSG:32654、10 m)。SITE 363 画素 (輪郭 36,370 m²)、CTRL 19,564 画素。位置のずれは最大 0.55 画素 (行)、0.5 を超えたのは 2021-09-25 と 2024-06-17 |
| R005 | A1、A2 | C1、C2 | confirmatory | 主分析 (α 0.001、ENL 4.4、VV と VH) | R004 と同じ | done | outputs/blocks.json、outputs/site_series.csv | - | C1 は退ける (SITE 0.427、CTRL 0.0657、比 6.496)。C2 は支持 (D_sar 2023-11-26、D_opt 2023-10-16、差 41 日) |
| R006 | B1、B2 | C3、C4 | confirmatory | 主分析 (3 dB、VV と VH) | R004 と同じ、labels/labels.csv | done | outputs/blocks.json、outputs/tiles.csv | - | C3 は支持 (4 位)。C4 は退ける (recall 0.4444、市街地の割合の順 0.2222、差 0.2222。半分に届かない) |
| R007 | 頑健性 | C1〜C4 | confirmatory | 計画の表のとおり | R004 と同じ | done | outputs/blocks.json の A_variants、B_variants | - | C2 は全設定で保たれる。C1 の 0.5 を超えるのは α 0.01 (0.7961) と ENL 5.5 (0.6722) だけ。B は閾値、偏波を変えても SAR が市街地の割合の順より多い。変化点の検定を点数にすると差が消え、調べた街区は 81 位 |
| R008 | 探索 | - | exploratory | 背景の差、位置のずれを戻した比べ直し、SITE の 3 dB、買う枚数 | R004 と同じ | done | outputs/explore.json | 結果を見た後 | 市街地の 3 dB 以上は 2024 年度と 2019 年度で 8.8 %、2018 年度と 2019 年度で 2.47 %。位置を戻すと 7.32 %。2024 年度の平均のずれは 2019 年度と行で約 0.23 画素違う。正解 2 の半分は SAR の順 31 枚、市街地の割合の順 57 枚 |
| R009 | 図 | - | - | 図 1〜3 | R005〜R007 | done | outputs/site_series.png、outputs/tile_ranking.png、outputs/capture_curve.png | 凡例が出典の行と重なったので位置を直した | - |
| R010 | 図 | - | - | 図 0 (地理院の写真 5 時期と工事区域の輪郭) | gazo4、nendophoto2009、2019、2024、ort (z17、2026-11-03 取得) | done | outputs/site_photos.png | 頼んだ人の求めで、結果の後に足した | 輪郭を写真に重ねると、OSM の工事区域は棟の消えた扇形の街区のほぼ全体を覆っていた。計画の「結果を見る前に知っていたこと」の「街区の一部 (南西寄り)」は、地図に重ねずに書いた誤り。判断の規則と結果は変わらない |
