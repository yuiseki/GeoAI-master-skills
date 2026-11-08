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

## 2026-11-09 に直したバグ

テストを足したときに、次の 4 つが見つかり、直した。課題の採点基準 (W4、W6、W7) と提案の JSON に写した pilot の数字は、直す前のコードから出たもので、流し直していない。入力の `data/` が手元に無いため。

| スクリプト | 直す前 | 影響を受ける数字 |
|---|---|---|
| `base2.py` | 中心が 2 つの国の境の上にあるセルが、両方の国に入り、人口が 2 回数えられた | セルを国に割り当てた後の全ての人口の和 (境の上の中心はまれで、影響は小さいと見込むが測っていない) |
| `pilot_cells.py` | 記録の無いセルが 1 つも無い国の gap0、gap1 が 0 でなく NULL になり、相関と順位から落ちた | W4 の契約数との相関 (−0.52) と順位 |
| `pilot_refugee_dist.py` | 地図で結べない組の難民が、加重平均の距離の分母にだけ残った | W6 の加重平均の距離 (結べない割合の分だけ短い。2025 年は 0.6%) |
| `pilot_gtfs.py` | 範囲に入るセルの無い国が、所得との相関から落ちた (同じスクリプトの当てはめの表は 0 として扱っていた) | W7 の相関 |
