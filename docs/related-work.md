# 関連するスキル集

GeoAI-master-skills の外にある、地理空間のスキル集。中身は写していない。使うときは、それぞれのライセンスと、測った環境を確かめる。

## isaaccorley/geospatial-skills

- 場所: <https://github.com/isaaccorley/geospatial-skills> (2026-10-14 に a203446 を読んだ)
- ライセンス: このリポジトリで書かれたスキルは Apache-2.0。取り込んだスキルは、元のライセンス (Apache-2.0 の portolan-skills、MIT の opengeos/geoai-skills) のまま。
- 中身: 19 のスキル。GDAL、GeoParquet、GeoZarr、PMTiles、STAC のカタログ、衛星画像の取得など、データを作って配る側の道具が多い。
- GeoAI-master-skills との違い: GeoAI-master-skills は、何を測るか (評価の分け方、リーク、空間の自己相関) と、データの罠が中心。向こうは、大きなジョブを壊さずに流す技術が中心。特に `parallel-geospatial`、`planet-bulk-download`、`pmtiles-pipeline` に、実際のジョブの失敗から書いた、次のような知見がある。
  - 独立に分けられる軸 (地域、タイル、ヒルベルト順) で分けて、プロセスプールで流す。
  - 1 行ずつ追記する JSONL に完了を記録して、途中から再開できるようにする。
  - 一時ファイルに書いてから置き換える。ラッパーから `--force` を渡さない。
  - exit 139 (segfault) と exit 137 (メモリ不足で強制終了) の読み方。
- 数字は向こうの環境 (96 コアのノード、DuckDB spatial 1.5.0 のころ) のもの。版が違うと当てはまらないことがある。例: 向こうは「1,500 万行の `ST_Touches` の自己結合は segfault する」と書く。こちらで DuckDB 1.5.6 (CPU 8、メモリ 16 GB の Docker) で測ると、OSM の建物 2,990 万行 (osm-japan-src-2026-08) の自己結合が 50 秒で終わり、segfault しなかった (2026-10-14)。
