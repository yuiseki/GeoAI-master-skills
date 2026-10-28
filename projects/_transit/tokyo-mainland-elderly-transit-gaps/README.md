# 課題39：東京都本土の高齢者と駅・バス停の徒歩空白

[報告書](report.md)と[地図](outputs/elderly-transit-gap-map.png)をご覧ください。結果は[要約JSON](outputs/analysis.json)と[全メッシュCSV](outputs/mesh-results.csv)にも保存しています。

リポジトリのルートから再現します。入力は`analyze.py`冒頭で指定したHugging Face上の固定版5データセットのみです。初回はOSMの切り出しに時間とメモリが必要です。中間Parquetは無視対象の`artifacts/_transit/tokyo-mainland-elderly-transit-gaps/`にキャッシュします。

```sh
uv run --no-project --with 'duckdb==1.5.5' --with scipy --with numpy --with shapely --with pyproj python projects/_transit/tokyo-mainland-elderly-transit-gaps/scripts/analyze.py
uv run --no-project --with 'duckdb==1.5.5' --with numpy --with shapely --with matplotlib --with matplotlib-fontja python projects/_transit/tokyo-mainland-elderly-transit-gaps/scripts/plot.py
uv run --no-project --with 'duckdb==1.5.5' --with scipy --with numpy --with shapely --with pyproj --with matplotlib --with matplotlib-fontja --with pytest pytest -q projects/_transit/tokyo-mainland-elderly-transit-gaps/scripts/test_analyze.py projects/_transit/tokyo-mainland-elderly-transit-gaps/scripts/test_plot.py
python3 .agents/skills/analysis-reporting/scripts/check_report.py projects/_transit/tokyo-mainland-elderly-transit-gaps/report.md --level full --evidence projects/_transit/tokyo-mainland-elderly-transit-gaps/outputs/analysis.json projects/_transit/tokyo-mainland-elderly-transit-gaps/outputs/elderly-transit-gap-map.json projects/_transit/tokyo-mainland-elderly-transit-gaps/EXPERIMENT_TRACKER.md
```

データの座標系は[集計JSON](outputs/analysis.json)、図の階級と版は[図のJSON](outputs/elderly-transit-gap-map.json)に記録。主の定義は[事前計画](EXPERIMENT_PLAN.md)、結果を見た後の感度実装変更は[実行記録](EXPERIMENT_TRACKER.md)に記録しています。派生したメッシュ距離・空白判定・地図は観測データではありません。道路グラフはOSMの全交差を道路頂点で近似しており、実際の徒歩経路の保証はありません。
