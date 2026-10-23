# tokyo-town-types

東京の地区を統計・POI・街路画像から類型化し、地域施策の対象を検討する前の下見に使えるかを検証した既存事例です。

- [整理したレポート](report.md)
- 移植元: [`study-geoai-algo-py/case-studies/004-town-types`](https://github.com/yuiseki/study-geoai-algo-py/tree/6880b32c097a7c65a6bd72a38682ce1dce1c9a2b/case-studies/004-town-types)
- 状態: 既存結果の整理。分析の再実行やデータの複製はしていません。

図は `outputs/source-values.csv` の値から再生成できます。

```sh
uv run --with matplotlib python scripts/plot.py
```
