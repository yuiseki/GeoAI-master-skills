# 小さい課題 その 3 (エージェントに渡す側)

問いは、人が尋ねる言葉のまま。使うデータだけを書いた。1 回の実行では 1 つだけ渡す。

## 課題 27: 東京都で一番地価の高いテニスコート

問い: 東京都で一番地価の高いテニスコートはどこ？
使うデータ: テニスコートは Hugging Face の `yuiseki/osm-japan-src-2026-08` (OpenStreetMap、2026-08-31 で凍結)。地価は Hugging Face の `yuiseki/ksj-l01-land-price` (地価公示)。都の範囲は `yuiseki/jp-admin-2026-09` の市区町村の面。ほかのデータや、OpenStreetMap の公開のサーバー (Overpass API など) は使わない。
範囲: 東京都。
