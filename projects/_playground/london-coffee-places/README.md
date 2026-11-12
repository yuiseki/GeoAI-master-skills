# london-coffee-places

Google の Geospatial Analytics Playground の例「Find the top 20 coffee shop clusters in London aggregated by H3 cell」を、オープンデータ (Overture Maps の places、Kontur の人口、OpenStreetMap) で行う。スキルは `.agents/skills/poi-insights`。

- 報告: [report.md](report.md)
- 小さな表と図: `outputs/`。取り出したデータと中間のファイル: `artifacts/_playground/london-coffee-places/`

## 再実行

```sh
CAP="systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% --"
PY="uvx -q --python 3.12 --from duckdb==1.5.6 --with h3 --with s2sphere --with numpy --with scipy --with matplotlib"
cd projects/_playground/london-coffee-places
$CAP $PY python scripts/run.py fetch extract boroughs population hotspots compare osm crosscheck sensitivity maps
```

- fetch は S3 から範囲の places を 1 回写す (この環境で約 7 分、101 MB)。
- osm は自前の Overpass (`overpass.yuiseki.net`、データ時刻 2025-09-14) を呼ぶ。OpenStreetMap の公開サーバーは使わない。別の Overpass を使うなら `OVERPASS` を変える。データ時刻が違えば照合の数字も変わる。
- 2026-11-12 に流した。DuckDB 1.5.6、h3 4.x、Python 3.12。
