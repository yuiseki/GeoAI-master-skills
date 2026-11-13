# 実行記録

| 条件 | 状態 | 出力 | 備考 |
|---|---|---|---|
| キャッシュ準備 | 失敗 | なし | 既定Hugging Faceキャッシュの権限エラー。専用一時キャッシュで再取得して解消。計測には含めない。 |
| 逐次・4スレッド | 完了 | [sequential.json](outputs/sequential.json) | 全8ビュー、別cgroup。 |
| 2ワーカー・各2スレッド | 完了 | [workers2.json](outputs/workers2.json) | 全8ビュー。終了時にPython resource_trackerのセマフォ2個の警告。 |
| バッチ2・4スレッド | 完了 | [batch2.json](outputs/batch2.json) | 全8ビュー。 |
| 検出結果の照合 | 完了 | [comparison.json](outputs/comparison.json) | ビュー・クエリごとにIoU 0.5以上で一対一照合。 |
