# akita-bear-mast-exposure

年に 1 つの秋田県のブナの豊凶 (mast_scarcity) と、100 m セルごとのブナ・ナラ類の植生の exposure の積を、既存の B_env (akita-bear-risk-grid-100m) のスコアに 1 つの係数で足すと、クマ出没の通報のセルの順位が良くなるかを確かめる。B_env は作り直さない。

- 計画 (確認の前に固定): [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)
- 実行の記録: [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)

```
scripts/     コードとテスト (pytest)
outputs/     報告が引く小さな結果 (CSV、JSON、PNG)
artifacts/akita-bear-mast-exposure/   セルごとの exposure などの大きな中間物 (commit しない)
```
