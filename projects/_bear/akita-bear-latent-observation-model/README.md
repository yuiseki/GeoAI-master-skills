# akita-bear-latent-observation-model

人が持つ熊の分布の記録は、全て何かの観測過程を通した記録で、熊の真の生息域や利用の強さの正解 (golden data) は無い。観測の偏りの違う 2 つの熊の観測系 (環境省の分布メッシュ、クマダスの通報) と人側の空間利用の proxy を同時にモデル化したとき、共通する潜在の bear space use と human space use をどこまで識別できるか、2023〜2026 年の通報の変化を「熊側の変化」と「人側・通報の過程の変化」に分けられるかを調べる。

新しい予測変数を探す研究ではない。中心は、潜在状態と観測過程の分離と、その識別可能性 (identifiability)。実データに当てる前に、同じ構造の合成データで識別できるかを確かめる。

- 概念モデル: [CONCEPT.md](CONCEPT.md)
- 関連する研究 (Web で確かめた範囲と未確認): [RELATED_WORK.md](RELATED_WORK.md)
- 計画 (結果を見る前に固定): [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)
- 実行の記録: [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)
- 報告: report.md (最後に書く)

```
scripts/     コードとテスト (pytest)
outputs/     報告が引く小さな結果 (JSON) と図 (PNG)
artifacts/_bear/akita-bear-latent-observation-model/
  mesh/      5 km メッシュの入力の表 (派生物)
  sim/       合成データと事後分布の要約 (合成で、観測ではない)
  fit/       実データの事後分布 (派生物)
```

再現のコマンドは各段のスクリプトができたら足す。
