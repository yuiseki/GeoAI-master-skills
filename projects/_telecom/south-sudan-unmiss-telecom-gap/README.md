# south-sudan-unmiss-telecom-gap

南スーダンの UNMISS 配置図から自動抽出された座標群と、公開通信・電力データベースの記録との距離を照合する探索的分析です。距離や近接閾値は通信カバレッジ、設備稼働、現場からの利用可能性を示しません。

## 再実行

`01_analysis.py` は `data/cache/` に固定版 WDI、OpenCelliD、PKO、行政境界データがある環境向けです。このリポジトリ checkout には同キャッシュ一式を含めていません。OpenCelliD の距離だけを再計算する場合は、固定版から MCC 659 の対象行だけを抽出します (元 Parquet 126 MB):

キャッシュ一式が別途揃っている場合の全体分析コマンド:

```sh
systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --with duckdb --with pandas --with geopandas --with shapely --with pyarrow --with pyproj \
  python projects/_telecom/south-sudan-unmiss-telecom-gap/scripts/01_analysis.py
```

```sh
mkdir -p /tmp/ssd-opencellid-review
systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  curl -fL -o /tmp/ssd-opencellid-review/cell_towers.parquet \
  'https://huggingface.co/datasets/yuiseki/opencellid/resolve/82e4acdb5ea93250ea6128ce08c03a4ca8870c88/parquet/2026-10-06/cell_towers.parquet'
systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --with duckdb python -c "import duckdb; duckdb.connect().execute(\"COPY (SELECT radio,lon,lat,range,samples FROM read_parquet('/tmp/ssd-opencellid-review/cell_towers.parquet') WHERE mcc=659) TO '/tmp/ssd-opencellid-review/ssd_cells.csv' (HEADER)\")"
systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  python3 projects/_telecom/south-sudan-unmiss-telecom-gap/scripts/04_recompute_opencellid_distances.py \
  --cells-csv /tmp/ssd-opencellid-review/ssd_cells.csv
```

`03_observation_audit.py` は保存済みのタイル・OSM距離出力から記録への近接数をまとめます。図を再生成する場合は、地図背景用の Natural Earth v5.1.2 の固定版を取得します (Public Domain)。

```sh
mkdir -p /tmp/ssd-map-context
systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  curl -fL -o /tmp/ssd-map-context/ne_10m_admin_0_countries.parquet \
  'https://huggingface.co/datasets/yuiseki/natural-earth/resolve/efdd0668c57c9d42307e12eacbf66d8d151de5b9/parquet/v5.1.2/10m_cultural/ne_10m_admin_0_countries.parquet' \
  -o /tmp/ssd-map-context/ne_10m_admin_1_states_provinces.parquet \
  'https://huggingface.co/datasets/yuiseki/natural-earth/resolve/efdd0668c57c9d42307e12eacbf66d8d151de5b9/parquet/v5.1.2/10m_cultural/ne_10m_admin_1_states_provinces.parquet' \
  -o /tmp/ssd-map-context/ne_10m_populated_places.parquet \
  'https://huggingface.co/datasets/yuiseki/natural-earth/resolve/efdd0668c57c9d42307e12eacbf66d8d151de5b9/parquet/v5.1.2/10m_cultural/ne_10m_populated_places.parquet'
systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --with geopandas --with pyarrow --with matplotlib --with matplotlib-fontja --with pandas --with numpy \
  python projects/_telecom/south-sudan-unmiss-telecom-gap/scripts/02_figures.py \
  --natural-earth-dir /tmp/ssd-map-context
```

地図は日本語で、国境・州境・都市名を背景に重ねています。OpenCelliD 座標抽出図、Ookla 測定図、OSM 電力地物図を別々に作成し、ソース別のライセンスと帰属表示を図中に載せます。Ookla データは CC BY-NC-SA 4.0 のため、本成果は非商用調査研究として扱います。速度面の内挿は行いません。実データを読むコマンドはすべてメモリ・CPU上限内で実行してください。

## 主なファイル

速度比較は保存済み Ookla タイルと上記 Natural Earth 都市点だけから再実行できます。

```sh
systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --with geopandas --with pyarrow --with matplotlib --with matplotlib-fontja --with numpy --with pandas --with pyproj \
  python projects/_telecom/south-sudan-unmiss-telecom-gap/scripts/05_speed_comparison.py \
  --places /tmp/ssd-map-context/ne_10m_populated_places.parquet
```

- `scripts/01_analysis.py`: 固定版キャッシュから距離・要約を生成。OpenCelliDには WGS84 楕円体測地線を使い、列名・閾値は記録への近接として表現。
- `scripts/02_figures.py`: 固定版 Natural Earth の地理的文脈を重ねた日本語地図と距離補助図を作成。未観測域に補間値を描かない。
- `scripts/03_observation_audit.py`: Ooklaタイル、OSM電力関連点・送電線への近接数を要約。
- `scripts/04_recompute_opencellid_distances.py`: 固定版 MCC 659 登録セルへの測地線距離を再計算。
- `scripts/05_speed_comparison.py`: 保存済み Ookla タイルとジュバ都市点から記述的な速度比較、距離一覧と分布図を作る。
- `scripts/06_capital_speed_comparison.py`: Ookla 2024 Q2 モバイル Parquet（元ファイルまたは東京・ジュバ周辺を抽出したもの）と Natural Earth 都市点から東京とジュバの速度分布を比較する。元ファイルは [Ookla](https://ookla-open-data.s3.amazonaws.com/parquet/performance/type=mobile/year=2024/quarter=2/2024-04-01_performance_mobile_tiles.parquet) から入手できる。再集計による変化がありうるため、入力ファイルの SHA-256 を出力に記録する。

```sh
systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --with geopandas --with pyarrow --with matplotlib --with matplotlib-fontja --with numpy --with pandas --with pyproj --with duckdb \
  python projects/_telecom/south-sudan-unmiss-telecom-gap/scripts/06_capital_speed_comparison.py \
  --data /path/to/2024-04-01_performance_mobile_tiles.parquet \
  --places /tmp/ssd-map-context/ne_10m_populated_places.parquet
```
- `outputs/legacy_unmiss_site_cellular_distance.csv`: 旧出力。度ベースのOpenCelliD距離と旧ラベルを含むため、その値は報告に使わない。保存済みOSM・Ookla投影距離を再集計する入力としてのみ保持。
- `outputs/`: 集計と図。
- `report.md`: 根拠と未確認事項を含む報告。

## データ解釈上の注意

- PKO点は配置図PDFからの自動抽出で、地図日付はPDF作成日です。座標は実際の駐屯地と一致する保証がなく、`nearest_text` は検証済みサイト名ではありません。
- OpenCelliD はコミュニティ記録であり、記録の完全性・アンテナ位置・稼働状態を保証しません。
- Ooklaのタイル中心は集計された測定位置で、配置座標での接続成功を意味しません。`devices` のタイル間合計は全国のユニーク端末数ではありません。
- OSMの `plant`、`generator`、`substation` と送電線は別種の地物です。登録は稼働や利用可能性の証拠ではありません。
- 配置図、Ookla、OSMの時点は異なります。
- 報告と図には、調査者 yuiseki (Yui Matsumura) および各データのライセンスに応じた帰属・非商用注記を残します。
