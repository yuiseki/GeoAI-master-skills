# projects/_telecom/south-sudan-unmiss-telecom-gap

南スーダンにおける移動体通信網 (4G/5G/2G)・固定ブロードバンド・電力網カバレッジの実態と、国連 PKO ミッション (UNMISS) 部隊展開地点との空間的ギャップの分析。

本研究は、**UN Open GIS Initiative, Domain Working Group 7 "Smart Maps Group" のボランティアメンバーである yuiseki (Yui Matsumura) による非商用調査研究**として実施されたものです。

オフライン可搬型地理空間情報配信環境 ([unvt/portable](https://github.com/unvt/portable)) が PKO 現場で持つ不可欠な役割を、実証的データに基づいて根拠づけます。

## 再実行の手順

```sh
# 依存関係のインストール
pip install duckdb pandas geopandas shapely pyarrow matplotlib seaborn requests scipy

# 1. 空間結合および指標集計スクリプトの実行 (OpenCelliD, PKO, WDI, OpenInfraMap/OSM, Ookla Speedtest)
python projects/_telecom/south-sudan-unmiss-telecom-gap/scripts/01_analysis.py

# 2. 地図・比較図・拡大図・ヒートマップの生成 (全6図を個別の PNG として出力)
python projects/_telecom/south-sudan-unmiss-telecom-gap/scripts/02_figures.py

# 3. テストの実行
python -m pytest projects/_telecom/south-sudan-unmiss-telecom-gap/scripts/test_analysis.py

# 4. レポート検証関門のチェック
python .agents/skills/analysis-reporting/scripts/check_project.py projects/_telecom/south-sudan-unmiss-telecom-gap
```

## ディレクトリ構成

- `scripts/`: 分析・可視化スクリプト
  - `01_analysis.py`: OpenCelliD、UN PKO 部隊配置、世界開発指標 (WDI)、OSM 電力インフラ、Ookla 実測通信のデータ結合および空間距離・カバレッジ算出
  - `02_figures.py`: 地図、距離比較図、部隊内訳図、首都ジュバ拡大図、最孤立拠点 Bunji 拡大図、Ookla 地名付きヒートマップの個別描画
  - `test_analysis.py`: 分析集計の完全性を検証するテスト
- `outputs/`: 算出された集計テーブル、要約指標、画像
  - `wdi_national_indicators.csv`: 世界銀行 WDI による南スーダンの電力・通信指標
  - `opencellid_summary.csv`: OpenCelliD 南スーダン (MCC 659) の無線規格別セル数
  - `unmiss_annual_summary.csv`: UNMISS 年次別部隊配置数
  - `unmiss_site_cellular_distance.csv`: 各 UNMISS 基地から最寄り基地局・送電線までの距離
  - `summary_metrics.json`: 主要要約指標 JSON
  - `osm_power_points.parquet`: 南スーダン内の発電所・変電所・発電機
  - `osm_power_lines.parquet`: 南スーダン内の高圧送電線
  - `ookla_mobile_tiles_ssd.parquet`: Ookla Speedtest 南スーダン内実測タイル
  - `unmiss_cellular_gap_map.png`: 図 1 (全国インフラ統合地図)
  - `unmiss_distance_breakdown.png`: 図 2 (拠点別通信基地局・送電線離隔距離)
  - `unmiss_units_connectivity_pie.png`: 図 3 (UNMISS 展開部隊の通信接続状況内訳)
  - `juba_infrastructure_inset.png`: 図 4 (首都ジュバ周辺インフラ拡大図)
  - `isolated_bunji_inset.png`: 図 5 (極限の孤立拠点 Bunji 周辺拡大図)
  - `ookla_speed_heatmap.png`: 図 6 (南スーダン全土 Ookla 実測通信速度ヒートマップ・地名入り)
- `report.md`: 分析報告書
