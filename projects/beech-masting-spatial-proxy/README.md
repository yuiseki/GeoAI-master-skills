# beech-masting-spatial-proxy

東北 98 地点のブナの結実の評価 (地点 × 年、0〜3、1989〜2008 年) を、前年の結実、地形、年ごとの気象と水分、地形 × 気象の交互作用で当て、学習に使っていない年と地点の両方で当たるかを確かめる。当たるなら、観測の無い場所の豊凶を環境のラスタから作る面 (proxy) の根拠になる。県 × 年で調べた [beech-masting-triggers](../beech-masting-triggers/) の続きだが、分析の単位が地点 × 年なので別にした。

計画は [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)、実行の記録は [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)。

## 置き場所

- `scripts/`: コードとテスト。
- `outputs/`: 報告が引く小さな表と図。
- `artifacts/beech-masting-spatial-proxy/`: 読んだ DEM のタイル、地点 × 月の気象の値などの大きな中間物 (git に入れない)。

## データ

- 目的変数: `yuiseki/fagus-crenata-masting-jp-2026-06` 版 db40a09 (Dryad、Masaki ほか、CC0)。東北 98 地点だけ。北海道 4 地点は別の地域の検証のために読まない。
- 地形: Mapterhorn の複製 `z.yuiseki.net/static/mapterhorn/2026-01-06/planet.pmtiles` のズーム 12。
- 気温: `yuiseki/agera5-japan-monthly-temperature-1979-2026` 版 348e459。
- 水分: `yuiseki/agera5-japan-monthly-water-1979-2026` 版 b3d1a83 (AgERA5 の月別降水と FAO の月別基準蒸発散量、CC BY-SA 4.0)。この研究のために凍結した。作り方は Hugging Face の `scripts/build.py`。

## 再現

リポジトリの直下から。版は全て固定してある (Dryad db40a09、気温 348e459、水分 b3d1a83、Mapterhorn の 2026-01-06 の複製)。

```sh
# 1. 地形 (Mapterhorn のズーム 12 を読み、タイルを artifacts に保存)
uvx --from 'duckdb>=1.5.5' --with pmtiles --with pillow --with pyproj --with pandas --with numpy python \
  projects/beech-masting-spatial-proxy/scripts/terrain.py projects/beech-masting-spatial-proxy/outputs \
  artifacts/beech-masting-spatial-proxy

# 2. 気温と水分 (地点のセルの月の値と、地点 × 年の偏差)
uvx --from 'duckdb>=1.5.5' --with pandas --with numpy --with pyarrow python \
  projects/beech-masting-spatial-proxy/scripts/climate.py projects/beech-masting-spatial-proxy/outputs \
  artifacts/beech-masting-spatial-proxy

# 3. 行と分け方の数
uvx --from 'duckdb>=1.5.5' --with pandas --with numpy --with pyproj python \
  projects/beech-masting-spatial-proxy/scripts/splits.py projects/beech-masting-spatial-proxy/outputs

# 4. B1: 開発期間で選んで凍結 (選択のファイルがあれば止まる)
uvx --from 'duckdb>=1.5.5' --with pandas --with numpy --with pyproj python \
  projects/beech-masting-spatial-proxy/scripts/run_dev.py projects/beech-masting-spatial-proxy/outputs

# 5. B2、B3: 確認期間で 1 回 (出力があれば止まる。並べ替え 400 回を含めて 40 分ほど)
uvx --from 'duckdb>=1.5.5' --with pandas --with numpy --with pyproj --with pyarrow python \
  projects/beech-masting-spatial-proxy/scripts/run_confirm.py projects/beech-masting-spatial-proxy/outputs \
  artifacts/beech-masting-spatial-proxy

# 6. E1: 結果を見た後の探索 (年の中の地点の順位、気象の空間の違いを消した版)
uvx --from 'duckdb>=1.5.5' --with pandas --with numpy --with pyproj --with pyarrow python \
  projects/beech-masting-spatial-proxy/scripts/explore_within_year.py projects/beech-masting-spatial-proxy/outputs \
  artifacts/beech-masting-spatial-proxy

# 7. 図
uvx --with matplotlib --with pandas --with pyproj python projects/beech-masting-spatial-proxy/scripts/plot.py \
  projects/beech-masting-spatial-proxy/outputs

# テスト
cd projects/beech-masting-spatial-proxy/scripts && uvx --with numpy --with pandas --with pytest python -m pytest -q
```

確認の段 (5) は計画どおり 1 回だけ流す。やり直すときは、出力を消す理由を記録に書いてから消す。
