# 記録: Landsat 5 の偏差でブナの豊凶の年の中の地点の順位を当てる

流すたびに 1 行足す。行を消さない。失敗した実行、捨てた実行も残す。計画と違うことをしたら deviation に書く (何を見た後に、何を、なぜ)。計画どおりなら `-`。データの取得と QA の問題、ライセンス、仕様の不明は、補わずにここに書く。

| run_id | block_id | claim_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|---|
| R001 | B0 | - | sanity | Landsat 5 の出典、ライセンス、尺度、QA の確認と dataset-discovery の reference | Planetary Computer `landsat-c2-l2` (2026-10-28)、USGS の FAQ (尺度) | done | .agents/skills/dataset-discovery/references/planetary-computer/landsat-c2-l2.md | - | collection の license は proprietary の表記で、link の先が USGS のデータ方針 (Public Domain)。USGS は大半の情報を public domain とする。尺度 0.0000275、オフセット −0.2、fill 0、有効範囲 7273〜43636。qa_pixel と qa_radsat のビットは item の `classification:bitfields` で確認。102 地点に重なる 1989〜2008 年の 4〜5 月と 7〜8 月の Landsat 5 の item は 1,394 件 (T1 915、T2 479)、path/row 13 通り。1 つの item で 300 m の窓 (21 × 21 画素) を 5 つの帯で読めた (署名はコレクション名のトークン、期限 約 1 時間) |
