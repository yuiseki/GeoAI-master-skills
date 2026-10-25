---
kind: catalog
id: global-fishing-watch
description: Global Fishing Watch の AIS 等から推定した漁業活動、船舶の存在、遭遇などのデータの入口。
url: https://globalfishingwatch.org/datasets-and-code/
access: API は個人 Bearer token 必須。ダウンロードポータルも登録・ログインが必要。2026-10-25 に未認証の API は 401
license: GFW のサイト・データ・サービスは CC BY-NC 4.0 に基づく非商用利用のみ。商用利用には別途許諾が必要。個別製品の条件も確認
crs: API と個別配布形式による。実データは未取得なので未確認
spatial_coverage: AIS 等で観測・推定できる海域。海上活動の全数ではない
temporal_coverage: 製品と版ごと。2026-10-21 以降の latest は pipeline v5 を指す
as_of:
  checked: 2026-10-25
contents:
- apparent fishing activity、vessel presence、encounters、port visits、SAR 検出など
---

# Global Fishing Watch

[製品一覧](https://globalfishingwatch.org/datasets-and-code/)から分析に必要な製品を選ぶ。公開の静的スナップショットと更新される API を混同しない。[API 認証説明](https://api-doc.globalfishingwatch.org/our-apis/documentation/docs/authentication)によると全 API リクエストに個人の Bearer token が必要。2026-10-25 に `GET https://gateway.api.globalfishingwatch.org/v3/datasets` を無認証で試すと HTTP 401 だった。この環境にトークンは無いため、漁業活動の実レコード・行数・粒度・欠損・CRS は未実測。目録カードだけを追加し、個別データカードは実データを確認してから作る。

[2026-10-21 の公式更新](https://globalfishingwatch.org/platform-update/version-5-data-pipeline-release/)で `latest` は pipeline v5 を指すようになった。古い結果と比較するなら `public-global-fishing-effort:v4.0` など版を固定する。2025年の[静的な apparent fishing activity](https://globalfishingwatch.org/platform-update/global-fishing-watch-data-download-portal-version-3/)は2012〜2024年を対象とする別のスナップショットであり、現行 v5 と同じ値とは限らない。

[利用条件](https://globalfishingwatch.org/dataset-and-code-fishing-activity/)は CC BY-NC 4.0 による非商用利用のみ。トークン、ダウンロードファイル、元 AIS の再配布は行わない。AIS 受信範囲や船舶の送信率、モデル版が変わるため、推定された `apparent fishing activity` を確認済みの漁獲や全船舶活動と読まない。商用の分析・サービスでの利用は別途許諾が必要。
