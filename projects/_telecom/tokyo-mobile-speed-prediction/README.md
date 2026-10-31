# tokyo-mobile-speed-prediction

東京23区で、街の公開データから携帯通信速度を予測し、通信環境の改善候補を絞れるか検証した既存事例です。

- [整理したレポート](report.md)
- 移植元: [`study-geoai-algo-py/case-studies/001-mobile-speed`](https://github.com/yuiseki/study-geoai-algo-py/tree/6880b32c097a7c65a6bd72a38682ce1dce1c9a2b/case-studies/001-mobile-speed)
- 状態: 既存結果の整理。分析の再実行やデータの複製はしていません。

図は `outputs/source-values.csv` の値から再生成できます。

```sh
uv run --with matplotlib python scripts/plot.py
```

報告で使う元の事例の値のうち `outputs/source-values.csv` に無いものは、固定コミットの元の README から引用して `outputs/source-quotes.json` に書き出す。

```sh
uv run python scripts/quote_source.py
```
