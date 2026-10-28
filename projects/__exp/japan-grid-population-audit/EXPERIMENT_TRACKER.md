# 実行記録: 格子人口代用の整合性監査

計画: [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)。過去の `533946` の100メッシュpilotは[候補生成時の dry run](../../../evals/curriculum/dry-runs/2026-10-25-paperworthy-population-grid.md)であり、ここに確認済みの新しい実行として混ぜない。

| run_id | block_id | mode | status | result_path | deviation / notes |
|---|---|---|---|---|---|
| R000 | S0 | sanity | done | [テスト](scripts/test_analyze.py)、[全国監査](outputs/full-summary.json) | 合成テスト10件を通過。国勢調査177,861行、県境の重複897コードを合算。入力合計126,146,099人。GHSL5タイルの格子・人数合計と面の標本を照合 |
| R001 | B0 | exploratory | done | [pilot](outputs/pilot-summary.json) | 既知の都心100メッシュを再実行し、上位20の重なりを面積按分8・中心点6件で再現。主評価から100件を除外 |
| R002 | B1 | confirmatory descriptive | done | [全国](outputs/full-summary.json) | 固定タイル内の正人口175,000メッシュ。1,964メッシュは範囲外。pilot除外後174,900メッシュで上位10%重なり15,300/17,490、0.8748。業務上の合否閾値は未設定 |
| R003 | B2 | confirmatory method check | done | [全国](outputs/full-summary.json)、[人口下限](outputs/population-sensitivity.json) | 中心点割当は14,437/17,490、0.8254。面積按分は46都道府県のそれぞれで中心点割当を上回った。5%・20%、人口下限100・1,000人でも向きは保たれた |
| R004 | B3 | exploratory auxiliary | done | [土地被覆](outputs/landcover-summary.json) | 2021年WorldCover矩形内の1,899メッシュ。計画では市街地率の四分位を予定したが、実装は固定幅0–25%、25–50%、50–75%、75–100%。四分位とは呼ばない。2020年の誤差との対応は記述のみ |
| R005 | B3 diagnostic | exploratory | done | [空間診断](outputs/spatial-diagnostics.json) | B3の層別結果後に実行。k=4/8/12のMoran's Iと、完全な2×2/4×4/8×8メッシュ集計・原点半セル移動を追加。8×8では相関の符号も条件で変わる。元計画は空間依存と単位の感度を求めたが、具体的なk・格子幅は後決め |
| R006 | visualization | descriptive | done | [図](outputs/prefecture-recall.png)、[来歴](outputs/prefecture-recall.json) | 全国集計済みの都道府県別一致率のみを描画。PNGを目視確認 |

2026-10-25 に実行。R002・R003の「確認」は、既知の都心pilotを除いた後に固定した比較規則を指す。日本全域の独立な外部検証という意味ではない。結果のうち都道府県内上位10%は全国上位10%とは別の順位である。R004の固定幅区間への変更は記録したが、元計画の四分位を再実行したわけではない。R005は探索として扱う。
