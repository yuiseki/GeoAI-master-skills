# bear-outbreak-weather

秋田県、岐阜県、京都府、石川県の県 × 年の秋 (9〜12 月) のクマの出没通報の多さが、夏の気温、日射量、降水量で説明できるかを調べた。流す前に固定した H1 は、前年の夏 − 前々年の夏の気温差 (ΔT) が小さい年ほど秋の通報が多い、というもの。

- [報告](report.md)
- [計画](EXPERIMENT_PLAN.md) と [実行の記録](EXPERIMENT_TRACKER.md)

スクリプトは次の順に使う。使い方は各スクリプトの先頭にある。

| 順 | スクリプト | 作るもの |
|---:|---|---|
| 1 | `scripts/outcomes.py OUT.csv` | 県 × 年の秋と年全体の通報の数 |
| 2 | `scripts/climate.py OUT_DIR` | 県ごとの月の最高気温と夏の平均 (AgERA5) |
| 3 | `scripts/solar_precip.py FILES.csv OUT.csv` | 夏の日射量と降水量 (AgERA5) |
| 4 | `scripts/analysis.py OUTCOMES.csv SUMMER_TMAX.csv OUT.json` | H1 と、計画した頑健性と反証の確認 (`outputs/h1.json`) |
| 5 | `scripts/explore_weather.py OUTCOMES.csv SUMMER_TMAX.csv SOLAR_PRECIP.csv OUT.json` | 結果を見た後の探索 (`outputs/explore_weather.json`) |
| 6 | `scripts/plot.py`、`scripts/plot_rho.py` | 図 |

この分析で実際に渡した引数 (中間ファイルの場所) は、記録に残っていない (未確認)。テストは `scripts/test_*.py` にある。
