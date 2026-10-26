# 実行記録: 東北海道のAGB推定差

| run_id | 区画 | mode | 状態 | 出力 | deviation / notes |
|---|---|---|---|---|---|
| R000 | B1 | 探索 | failed | なし | DuckDB全件ポリゴン交差が約15GBへ増えたため停止（終了143）。結果は作らなかった。以後は同じ面・同じCRSでShapelyの空間索引へ実装を変えた。分析範囲・主条件は変更なし |
| R001 | B1 | 探索 | done | `outputs/cell_metrics.csv`, `outputs/summary.json` | 63,630面の分類をCTreesの集計面とEPSG:6933で交差。欠け・重複・中心点を別計数 |
| R002 | B2 | 探索 | done | `outputs/summary.json` | 主の上位20面と単純基準を同じ覆い・画素母集団で比較 |
| R003 | B3 | 探索 | done | `outputs/summary.json` | 森林率0.5/0.8/0.9、中心点、不確実性上位四分位除外、100画素を比較 |
| R004 | B3 | 探索 | failed → done | `outputs/common_pixel_audit.csv`, `outputs/common_pixel_summary.json` | 元GeoTIFFの`nodata`メタデータはNoneであり初回実行は停止。配布元変換コードどおり値-9999を欠測としてハッシュ照合後に再実行。元画素の共通マスクを確認した |

事前pilotで件数と一部の差を見ていたため、全区画は探索として報告する。後から主閾値や調査枠を変更していない。R000とR004の失敗を成功に置き換えず記録した。
