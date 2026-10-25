---
kind: catalog
id: mobility-database
description: MobilityData の公共交通フィード目録。公開 CSV には GTFS と GTFS Realtime の供給元と取得先が載る。
url: https://mobilitydatabase.org/
access: https://files.mobilitydatabase.org/feeds_v2.csv は認証なしで取得可能。API にはアカウントが必要。個別フィードのアクセス条件は別
license: MobilityData が生成した目録メタデータは CC0 1.0。個々のフィードは各提供者の利用条件に従う
crs: 目録には任意の緯度経度 bbox がある。フィード本体の座標系は個別確認
spatial_coverage: 世界の登録フィード。未登録地域は交通サービスが無いことを意味しない
temporal_coverage: 更新される目録。2026-10-25 に取得した CSV の Last-Modified は 2026-10-20
as_of:
  fetched: 2026-10-25
  sha256: 0d90eb4ea0364ae4d66580f3b264763ecc9667850829cd161e09184982cca3e4
contents:
- GTFS と GTFS Realtime のフィード識別子、種別、供給者、国、公式性、取得 URL、認証、ライセンス URL、bbox
---

# Mobility Database

[公式のカタログ説明](https://github.com/MobilityData/mobility-database-catalogs)に従い、まず [feeds_v2.csv](https://files.mobilitydatabase.org/feeds_v2.csv) を読む。2026-10-25 の実読では 2,729,383 バイト、6,686 行、`id` は全行一意。`data_type` は `gtfs` 4,646 行、`gtfs_rt` 2,040 行で、この CSV に GBFS の行は無かった。GBFS が必要なら別の配布入口を探す。

| 確認した列 | 結果 |
|---|---:|
| `is_official` | True 4,835、False 489、空欄 1,362 |
| `urls.authentication_type` | 0 が 6,089、1 が 291、2 が 306 |
| `urls.license` の空欄 | 3,054 |
| bbox の4座標すべてが空欄 | 650 |
| `urls.latest` の空欄 | 2,249 |
| `location.country_code` の空欄 | 26 |

国コードの上位は US 2,509、FR 1,177、JP 827。これらは公開フィードの登録件数であり、交通サービスの総数ではない。1 行は目録の1フィードであり、停留所、運行便、利用者の観測ではない。`id` はこの目録内の識別子。複数フィードを地域で結ぶなら国コードと bbox の有無、feed の範囲を実ファイルで確認する。

[利用条件](https://mobilitydatabase.org/terms-and-conditions)は、目録メタデータを CC0 1.0 とし、個々の GTFS 等には提供者の条件を適用する。`urls.license` が空欄でも自由利用と決めない。`urls.latest` は更新され得る。分析で使う場合は CSV の SHA-256 と取得日を保存し、各フィードの URL・版・許諾を別途固定する。フィード本体の一括ミラーや Hugging Face への再配布は行わない。API の認証方式の値は[カタログのスキーマ](https://github.com/MobilityData/mobility-database-catalogs)を参照する。
