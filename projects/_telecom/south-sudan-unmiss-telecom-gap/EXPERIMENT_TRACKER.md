# 実行記録

| 日付 | 区画 | 状態 | 出力 | 判断・逸脱 |
|---|---|---|---|---|
| 2026-11-11 | 2024 Q2 速度の地域比較 | exploratory | [集計](outputs/speed_comparison.json)、[タイル](outputs/speed_comparison_tiles.csv) | 10 km と20 km、等重み中央値とテスト数加重平均。地域全体への一般化はできない。 |
| 2026-11-11 | 最近傍タイル一覧 | exploratory | [一覧](outputs/nearest_observed_speed_by_map_coordinate.csv) | 地域比較の結果を見た後に計画へ追加。座標・地名は未検証、拠点速度ではない。 |
| 2026-11-11 | 東京・ジュバ比較 | exploratory | [集計](outputs/capital_speed_comparison.json)、[分布図](outputs/capital_speed_comparison.png) | 同一公開ファイル、東京10 / 50 kmとジュバ10 km。観測されたタイルのみの比較。 |
