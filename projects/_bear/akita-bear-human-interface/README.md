# akita-bear-human-interface

秋田県の 100 m セルの翌年度のクマ出没通報の順位を当てる環境だけの地図 B_env ([akita-bear-risk-grid-100m](../akita-bear-risk-grid-100m/)) の中身を、熊側の環境 proxy (bear-side)、人側の環境・活動 proxy (human-side)、両者の境目を直接表す proxy (interface) に分け、予測力がどこから来ているか、通報のあったセルが年度ごとにその 2 次元の上でどう動いたかを調べる。

新しい予測変数を足す研究ではない。特徴量は B_env の静的な 28 個だけで、外部データは足さない。

- 計画 (結果を見る前に固定): [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)
- 特徴量の役割 (モデルを流す前に固定): [feature_roles.csv](feature_roles.csv)
- 実行の記録: [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)
- 報告: report.md (最後に書く)

```
scripts/     コードとテスト (pytest)
outputs/     報告が引く小さな結果 (JSON、CSV) と図 (PNG)
artifacts/_bear/akita-bear-human-interface/
  scores/    セルごとの予測 (*.npz、派生物で観測ではない)
  labels/    4〜9 月の通報のセルのラベル (派生物)
```

再現のコマンドは各段のスクリプトができたら足す。
