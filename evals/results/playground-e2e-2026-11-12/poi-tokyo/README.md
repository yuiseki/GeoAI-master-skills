# tokyo23-convenience-stores

問い: 東京 23 区のコンビニを H3 のセルで数えて集積の上位 10 を地図と表にし、区ごとに 1 万人あたりの店数とチェーンの寡占度 (HHI) を比べる。オープンデータだけを使う (Overture Maps places 2026-10-21.0、jp-admin-2026-09 の 2020 年国勢調査人口、OSM 2026-08-31)。

- 報告: [report.md](report.md)。図は `figures/`、表と数字は `outputs/`、大きな中間ファイルは `artifacts/tokyo23-convenience-stores/`。
- 実行環境: Python 3.12.15 (uvx)。duckdb 2.0.0 (Python パッケージ、`duckdb>=1.5.5` で解決)、h3 4.5.0、numpy 2.5.4、scipy 1.18.1、pandas 3.1.1、pyarrow 26.0.1、shapely 2.2.0、matplotlib 3.11.2。2026-11-12 に各パッケージを import して表示した値。
- 上限: systemd-run が無いので `scripts/run.sh` が `ulimit -v` 14 GB と `timeout` 1500 秒で囲む。

## 再実行

```sh
cd /work/projects/tokyo23-convenience-stores
./scripts/run.sh --from 'duckdb>=1.5.5' python scripts/00_fetch.py
./scripts/run.sh --from 'duckdb>=1.5.5' python scripts/01_regions.py
./scripts/02_extract.sh                      # S3 から Overture places (外接矩形)
./scripts/run.sh --from 'duckdb>=1.5.5' --with pandas --with scipy --with numpy --with pyarrow python scripts/03_prepare.py
./scripts/run.sh --with pandas --with scipy --with pyarrow --with numpy python scripts/04_sets.py
./scripts/run.sh --with h3 --with numpy --with scipy --with pandas --with pyarrow --with duckdb --with shapely --with s2sphere python scripts/05_hotspots.py
for s in primary rawbrand all; do ./scripts/run.sh --from 'duckdb>=1.5.5' --with numpy --with scipy --with h3 python /work/.agents/skills/poi-insights/scripts/poi_compare.py /work/artifacts/tokyo23-convenience-stores/pts_$s.parquet /work/artifacts/tokyo23-convenience-stores/wards.parquet outputs/compare_$s.csv; done
./scripts/run.sh --from 'duckdb>=1.5.5' python scripts/06_osm.py
./scripts/run.sh --from 'duckdb>=1.5.5' --with h3 --with numpy --with scipy --with pandas --with pyarrow python scripts/07_analysis.py > outputs/analysis_log.txt
./scripts/run.sh --with h3 --with numpy --with pandas --with pyarrow python scripts/08_checks.py
./scripts/run.sh --with h3 --with numpy --with pandas --with pyarrow --with duckdb --with shapely --with matplotlib python scripts/09_figures.py
uvx --with pandas python scripts/10_tables.py && uvx python scripts/11_report.py
```

