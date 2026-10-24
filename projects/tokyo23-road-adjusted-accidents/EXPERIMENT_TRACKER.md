# 課題31 実行記録

| 日時 | 区画 | 状態 | 結果 | 計画からの変更・注記 |
|---|---|---|---|---|
| 2026-10-24 | sanity | passed | `scripts/test_analyze.py` 5件成功。区内事故20,948件のうち20,603件が中心点区内人口メッシュに対応、345件が対象外。道路の選択224,747線、対象メッシュで計17,207.86km。 | なし。 |
| 2026-10-24 | B1 | completed (exploratory) | `outputs/analysis.json`、`outputs/mesh-results.csv`。NB2上側確率の首位 `53394536`。件数上位10との共通4、人口のみ上位10との共通5。 | 道路下限1.0kmへの変更は最小延長3.16kmのため対象変化なし。 |
| 2026-10-24 | robustness | completed (exploratory) | `service`・`motorway`除外でも首位同じ、上位10共通8。Poissonでも首位同じ。 `outputs/accident-surprise-equal-map.png` と分位図を出力。階級変更で79.8%のメッシュの色が変化。 | 残差Moran診断を追加。8近傍I=0.484（999回並べ替えp=0.001）と強い空間依存が残るため、NB2上側確率・BH値の確証的解釈を退けた。 |
