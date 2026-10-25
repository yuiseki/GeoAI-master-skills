---
kind: dataset
id: yuiseki/usgs-comcat-2025-m45
description: USGS ComCat の2025年M4.5以上の地震を、優先ネットワークusに限定した版固定GeoParquet。
url: https://huggingface.co/datasets/yuiseki/usgs-comcat-2025-m45
source_url: https://earthquake.usgs.gov/fdsnws/event/1/
license: USGSが作成・生成した情報は米国パブリックドメイン。出典表示を求める。優先ネットワークus以外のイベントは除外し、sources等の由来列を保持
formats:
- GeoParquet
- GeoJSON
crs: OGC:CRS84 (2D longitude, latitude)。深さは別列 depth_km
spatial_coverage: 全球。観測網・検知能力により地域ごとに網羅性が異なる
temporal_coverage: 2025-01-01から2025-12-31の発生イベント。2026-10-25に取得したカタログ状態
as_of:
  checked: 2026-10-25
  service_version: 2.8.2
  hub_revision: 028c1c866c0d49764ab19cdee86208577e088f20
  query_manifest: raw/2026-10-25/MANIFEST.json
contents:
- マグニチュード、発生時刻、位置、深さ、場所名
- 優先・寄与ネットワークとイベント参照 ID
tables:
- name: earthquakes
  read: hf://datasets/yuiseki/usgs-comcat-2025-m45@028c1c866c0d49764ab19cdee86208577e088f20/parquet/earthquakes.parquet
  grain: 優先ネットワークusが付いたM4.5以上の地震イベント1件
  rows: 8502
  id:
  - event_id
  columns:
  - name: event_id
    type: VARCHAR
    meaning: USGS ComCat のイベント ID
  - name: mag
    type: DOUBLE
    meaning: カタログのマグニチュード。magType に測定尺度
  - name: magType
    type: VARCHAR
    meaning: マグニチュード尺度。複数種類が混在
  - name: time
    type: BIGINT
    meaning: 発生時刻の Unix epoch ミリ秒 (UTC)
  - name: updated
    type: BIGINT
    meaning: レコード更新時刻の Unix epoch ミリ秒 (UTC)
  - name: geometry
    type: GEOMETRY (OGC:CRS84)
    meaning: 震央の2D点。経度・緯度
  - name: depth_km
    type: DOUBLE
    meaning: 深さ km。正値が地表から下向き
  - name: net
    type: VARCHAR
    meaning: 優先ネットワーク。本表は全行us
  - name: sources
    type: VARCHAR
    meaning: カタログの寄与元ネットワーク一覧
  - name: ids
    type: VARCHAR
    meaning: 関連イベント ID 一覧
  - name: felt
    type: INTEGER
    meaning: 報告された有感回答数。NULL は報告なし
    missing: 7,143 rows are NULL
  - name: cdi
    type: DOUBLE
    meaning: Community Decimal Intensity。NULL は値なし
    missing: 7,143 rows are NULL
  - name: mmi
    type: DOUBLE
    meaning: Modified Mercalli Intensity。NULL は値なし
    missing: 7,663 rows are NULL
  - name: alert
    type: VARCHAR
    meaning: USGS alert level。NULL は値なし
    missing: 7,758 rows are NULL
  - name: tz
    type: VARCHAR
    meaning: 元 API のタイムゾーンオフセット
    missing: 全8,502行がNULL
---

# USGS ComCat 2025 M4.5+ 地震

2025年に発生したM4.5以上の全球ComCatイベントから、優先ネットワークが `us` で、イベント種別が `earthquake` のもの8,502件を GeoParquet にし、[Hugging Face](https://huggingface.co/datasets/yuiseki/usgs-comcat-2025-m45)に公開しました。API照会全体は8,558件で、他ネットワーク優先の55件と地震以外の1件を選択から除いています。照会 URL、取得時刻、版、除外件数、元応答と公開用GeoJSONのチェックサムはHubの `raw/2026-10-25/MANIFEST.json` に記録しました。

実測では、イベント ID は全件一意、geometry はすべて有効な Point で、null はありません。マグニチュード範囲は4.5〜8.8、深さは1.181〜669.556 kmでした。GeoParquetの全ソース属性、イベント ID、深さ、座標は、公開用GeoJSONと照合しています。

## 利用上の注意

これはM4.5以上、優先ネットワーク `us`、地震種別に限定した取得時点のカタログです。全球の完全な観測一覧ではありません。観測網、検知能力、位置・深さの精度、`magType` は地域やイベントで異なります。後日、ComCat の過去記録が更新される場合もあります。存在しないイベントを地震活動が無い証拠として扱わないでください。深さはGeoJSONの第3座標値（km、正が下向き）を `depth_km` に分け、OGC:CRS84の2D geometryへ誤って高さとして符号化しないようにしました。

## ライセンスと出典

USGSは自ら作成・生成したデータと情報を米国のパブリックドメインとし、出典表示を求めています。本公開版は優先ネットワーク `us` のイベントだけを選び、`net`、`sources`、`ids` を残しています。これらの列が参照する別配布元の製品について、個別のライセンスを再許諾するものではありません。[USGSの著作権・クレジット方針](https://www.usgs.gov/faqs/are-usgs-reportspublications-copyrighted)に従い、「U.S. Geological Survey, ComCat」を表示してください。
