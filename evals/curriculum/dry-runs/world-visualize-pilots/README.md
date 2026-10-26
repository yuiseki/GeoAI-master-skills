# 世界地図の課題の pilot

`2026-10-26-world-visualize.md` の候補を確かめた小さいスクリプト。入力は固定版の Hugging Face のファイルを、作業ディレクトリの `data/` に置いて読む (リポジトリには入れない)。DuckDB は uv で入れた 2.0.0、`spatial` と community の `h3` の拡張を使う。

| 入力 (`data/`) | ファイル |
|---|---|
| `kontur.parquet` | `kontur-population-2023-11-01-22km@2e7291f…/parquet/kontur_population_20231101_r4.parquet` |
| `ne0.parquet` | `natural-earth@efdd066…/parquet/v5.1.2/10m_cultural/ne_10m_admin_0_countries.parquet` |
| `ibtracs.parquet` | `ibtracs-v04r01@7492b1a…/parquet/since1980/ibtracs.parquet` |
| `ucdp.parquet` | `ucdp-ged@d72fe7e…/parquet/26.1/ged.parquet` |
| `ocid.parquet` | `opencellid@82e4acd…/parquet/2026-10-06/cell_towers.parquet` |
| `airports.parquet`、`runways.parquet` | `ourairports-2026-08@6c1d115…/parquet/` |
| `tz.parquet` | `timezone-boundary-builder-2026d@cc26444…/parquet/timezones.parquet` |
| `unhcr.parquet` | `unhcr-refugee-stats@5f3eea4…/parquet/2026-10-04/population.parquet` |
| `wdi.parquet` | `worldbank-wdi@d0b1ad8…/parquet/2026-10-01/data.parquet` |
| `feeds_v2.csv` | Mobility Database の目録 (sha256 `0d90eb4e…`、Last-Modified 2026-10-20)。Hugging Face への凍結は未 |
| `wiki_coords.parquet` | `fetch_wiki.py` が `wikipedia-geotagged@24e53f6…` の英語版と日本語版から座標の列だけを取る |

順番: `base.py`、`base2.py` (セルを国に割り当てる) の後に、各 `pilot_*.py`。`pilot_refugee_dist.py` は `pilot_refugee.py` の、`pilot_air_residual.py` は `pilot_air.py` の表 (`ap`) と `pilot_gtfs.py` の表 (`gdp`) を使う。`pilot_tz.py` は `uvx --with tzdata==2025.2` で流した。どれも `uvx --from 'duckdb>=1.5.5' python -I <スクリプト>` で、`pilot.duckdb` を作業ディレクトリに作る。

作業ディレクトリに標準ライブラリと同じ名前の `.py` (`types.py` など) があると、DuckDB の import が壊れる。`python -I` で流すか、空のディレクトリで流す。
