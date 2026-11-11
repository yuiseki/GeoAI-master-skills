# 南スーダンの UNMISS 配置図と公開通信・電力データの空間的照合

## 問い

2024年の UNMISS 配置図から抽出された座標群の周辺に、公開通信・電力データの記録がどの程度あるかを照合し、そこから言える範囲を確認する。

## 結論

照合したのは実際の基地や利用可能なサービスではなく、配置図から抽出された座標群と、各データベースに登録された記録との距離です。2024年10月25日付の配置図から得た記録は、座標を小数第4位で丸めると19群・77レコードになりました。原データは自動抽出で正確性を保証せず、`nearest_text` は地名の手がかりにすぎません ([un-pko-deployments.md](../../../.agents/skills/dataset-discovery/references/huggingface/yuiseki/un-pko-deployments.md))。

OpenCelliD の固定版には MCC 659 の登録セルレコードが554件 (GSM 550件、LTE 4件) あり、配置図座標から最寄りレコードまでの距離中央値は454.120 km、最大は768.025 kmでした。10 km以内にレコードがある座標群は1群です ([opencellid_summary.csv](outputs/opencellid_summary.csv), [opencellid_record_proximity_summary.json](outputs/opencellid_record_proximity_summary.json))。これは OpenCelliD 上の登録状況を示すだけで、基地局の実数・稼働・電波到達・通信サービスの有無は示しません。

一方、2024年第2四半期の Ookla モバイル測定タイル中心点は、19座標群のうち11群から10 km以内にありました ([observation_proximity_audit.json](outputs/observation_proximity_audit.json))。OpenCelliD の記録分布と Ookla の測定記録が一致しない地域があることは分かりますが、タイル中心点が配置地点の正確な位置や、継続的な接続可能性を証明するわけではありません。2026年取得の OSM 電力データでも、電力関連点が10群、送電線が1群で10 km以内に記録されています。これも設備の稼働や UNMISS による利用可能性を示すものではなく、配置図との時点も一致していません ([observation_proximity_audit.json](outputs/observation_proximity_audit.json))。

したがって、この分析から「地方拠点は通信圏外／完全なオフグリッド」「`unvt/portable` が唯一の実用解」とは結論できません。言えるのは、公開データの記録が空間的に食い違い、拠点単位のサービス利用可能性をこれらの資料だけでは確定できないことです。

## 要点

| 項目 | 値 | 根拠 |
|---|---:|---|
| 配置図由来の座標群 / 抽出レコード | 19群 / 77件 | [opencellid_record_proximity_summary.json](outputs/opencellid_record_proximity_summary.json) |
| OpenCelliD MCC 659 登録セルレコード | 554件 (GSM 550、LTE 4) | [opencellid_summary.csv](outputs/opencellid_summary.csv) |
| 最寄り OpenCelliD レコード距離 | 中央値 454.120 km、最大 768.025 km | [opencellid_record_proximity_summary.json](outputs/opencellid_record_proximity_summary.json) |
| 10 km以内の記録数 (OpenCelliD / Ooklaタイル / OSM電力関連点 / OSM送電線) | 1 / 11 / 10 / 1 群 | [observation_proximity_audit.json](outputs/observation_proximity_audit.json) |
| Ookla モバイル測定タイル / テスト数 | 152 / 724 | [summary_metrics.json](outputs/summary_metrics.json) |

## 可視化

![配置図座標群から各データの最寄り記録までの距離](outputs/recorded_feature_proximity.png)

距離は各データベース内の記録への幾何学的な近さです。サービス提供、設備稼働、現場からの利用可能性を表しません。OpenCelliD は固定スナップショットから抽出した登録セルに対する WGS84 楕円体測地線距離です。

![Ookla 2024年第2四半期の観測タイル](outputs/ookla_observed_tiles.png)

色は各タイルの平均下り速度、点は観測タイル中心です。点のない場所は未観測であり、速度ゼロやサービス不存在ではありません。空間補間はしていません。

## データ

- **UN PKO 配置点**: `yuiseki/un-pko-deployments` 固定版 `528afe3d…`。2024年版のうち `map_date=20241025` を使用。PDFから自動抽出された点で正確性保証なし。日付はPDF作成日で、配置状況の基準日とは限らない。
- **OpenCelliD**: `yuiseki/opencellid` 固定版 `82e4acdb…`、2026-10-06スナップショット。MCC 659 の554レコード。位置はコミュニティ測定による推定で、測量されたアンテナ位置・稼働状態ではない。`range` と `samples` は行ごとに保持したが、網羅性を検証する参照目録はない。
- **Ookla Speedtest Global Performance**: 2024年第2四半期の南スーダン内モバイルタイル。152タイル、724テスト。AWS Registry の説明では、アプリ由来の測定を約610 m（赤道上）のタイルに集計したデータで、ライセンスは CC BY-NC-SA 4.0 です ([AWS Open Data Registry](https://registry.opendata.aws/speedtest-global-performance/))。`devices` の合計255はタイルごとの値の合計で、全国の重複排除済み端末数とは解釈しない。
- **OSM / OpenInfraMap 電力関連データ**: 2026-11-11取得。送電線22地物、電力関連点160地物。点には `plant`、`generator`、`substation` が混在する。UNMISS配置図より後の時点で、完全性・稼働・接続可能性は未確認。
- World Bank の「携帯電話契約数（人口100人当たり）」は、人口カバレッジ率や配置地点の利用可能性と同じ指標ではありません ([World Bank 指標ページ](https://data.worldbank.org/indicator/IT.CEL.SETS.P2))。既存 WDI 出力はこの空間照合の結論には使っていません。全国平均を配置地点の状態へ読み替えないため、報告の根拠から外しました。

## 方法

2024-10-25付配置図の点を経度・緯度の小数第4位でまとめ、座標群ごとに記録数を集計した。`nearest_text` は確認済みサイト名ではなく、図上で近接する文字列として扱う。固定 OpenCelliD 全体から MCC 659 の554行を抽出し、WGS84 楕円体上の測地線距離を再計算した。10 km と25 kmは記録の近接を数える便宜的な閾値で、通信可能範囲を意味しない。OSM地物とOoklaタイル中心点への距離は EPSG:32636 で計算した。2024年の配置図、2024年第2四半期のOokla、2026年のOSMは時点が異なるため、同時点の状態比較ではない。

Ookla図は保存済みタイルの観測値だけを描き、従来の未検証RBF内挿面を表示しない。OpenCelliD の再計算は保存済み成果物ではなく、固定版から改めて抽出した554レコードを使った。従来の `legacy_unmiss_site_cellular_distance.csv` にあった OpenCelliD 距離は度ベース近似であるため、この報告では再計算値に置き換え、旧値を根拠に使わない。この `legacy_` ファイルは、保存済み OSM / Ookla 投影距離から近接数を再集計するためだけに残している。

今回の checkout には WDI・PKO 等の入力キャッシュが無いため、全工程の再実行はしていない。固定版 OpenCelliD から MCC 659 を抽出して測地線距離を再計算し、Ookla・OSMの距離はコミット済み成果物の投影距離を使って記録近接数を再集計した。したがって、後者は保存済み入力の再検証であり、2026年の元 OSM 抽出からの再構築ではない。

## 失敗の型

| ID | 判定 | 根拠 |
|---|---|---|
| F1 | 確かめた | 配置座標群19、抽出レコード77、OpenCelliD MCC 659の554件を照合。出力行数は各リンク先を参照。 |
| F2 | 当てはまらない | 予測モデルを学習していない。 |
| F3 | 当てはまらない | 将来予測・交差検証を行っていない。 |
| F4 | 確かめていない | F4: 地域差とデータベースの記録・観測努力の差を分離できていない。 |
| F5 | 確かめていない | F5: OpenCelliD、Ookla、OSMは独立の完全な参照データではなく、相互一致を真値として扱えない。 |
| F6 | 確かめた | OpenCelliD距離を WGS84 Geod により再計算し、従来の度ベース近似を報告根拠から外した。 |
| F7 | 確かめていない | F7: 時点差、配置点の位置誤差、近接閾値の選択に対する頑健性は未評価。 |
| F8 | 確かめた | 数値は出力ファイルに対応づけた。これは転記整合性の確認で、データの真実性を保証しない。 |
| F9 | 確かめた | 各データの固定版・取得時点を記録し、時点差を明示した。 |

## 確かめていないこと

- F4/F5: 実際の通信事業者カバレッジ、基地局の稼働、現地での信号強度・速度・接続安定性。データベースの網羅性と記録努力。
- 配置図抽出点が個々の実際の駐屯地を示すか、`nearest_text` が正しい地名か。座標群の位置誤差が最近傍判定へ及ぼす影響。
- F7: OSM電力地物の稼働状態、容量、送電網への接続、UNMISS側の利用権・実際の電源、近接閾値を変えたときの頑健性。
- UNMISSの衛星回線、ミッション内ネットワーク、ローカルキャッシュ等の運用。これらを比較していないため、オフライン配信方式の優劣や必要性は判断していない。
