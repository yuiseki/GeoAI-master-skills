# tokyo23-underpass-listing

OSM のタグから作った東京 23 区のアンダーパスを母集団にして、国の一覧 (mlit-underpass) と冠水想定箇所に載るのはどれか、一覧は東京都の浸水実績の区域に入る箇所に寄っているかを調べる。計画は [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)、記録は [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)。大きな生成物は `artifacts/_flood/tokyo23-underpass-listing/` に置く。

## 再実行

```sh
cd projects/_flood/tokyo23-underpass-listing
uvx --from 'duckdb>=1.5.5' --with numpy --with pandas --with pyarrow python scripts/01_build.py
uvx --with numpy --with pandas --with pyarrow python scripts/02_blocks.py
uvx --from 'duckdb>=1.5.5' --with numpy --with pandas --with pyarrow --with shapely --with matplotlib python scripts/03_fig.py
uvx --from 'duckdb>=1.5.5' --with numpy --with pandas --with pyarrow --with shapely --with rasterio --with matplotlib --with pillow python scripts/04_layers_gif.py
```

01_build.py は、tokyo23-flood-record-vs-a31a の 01_fetch.py が取った区の面と浸水実績 (`artifacts/_flood/tokyo23-flood-record-vs-a31a/raw/`) を読む。テストは `scripts/test_listing.py` と `scripts/test_04_layers_gif.py` の 1 行目のコマンドで流す。
