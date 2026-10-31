# tokyo23-daytime-evac-stress

東京 23 区の 1 km メッシュで、平日昼間の滞在人口を夜間人口の代わりに使うと、指定避難所 1 件あたりの潜在需要が最も悪化するのはどこかを調べた。

- [報告](report.md)
- [計画](EXPERIMENT_PLAN.md) と [実行の記録](EXPERIMENT_TRACKER.md)

入力はスクリプトの先頭に版つきで書いてある (国勢調査 2020 の 1 km メッシュ、全国人流オープンデータ、国土地理院の指定避難所、行政界)。中間のデータは `artifacts/_evacuation_shelter/tokyo23-daytime-evac-stress/` に置き、報告の数字と図の来歴は `outputs/` に置く。

再実行はプロジェクトのディレクトリで、次の順に流す。

```sh
uvx --with 'duckdb>=1.5.5' python scripts/recon.py
~/.venvs/geoai/bin/python scripts/build_dataset.py
~/.venvs/geoai/bin/python scripts/analyze.py
~/.venvs/geoai/bin/python scripts/make_figures.py
```

`~/.venvs/geoai` は作者の環境で、各スクリプトが読み込むパッケージ (DuckDB、pandas、NumPy、SciPy、Shapely、matplotlib) が入っている。
