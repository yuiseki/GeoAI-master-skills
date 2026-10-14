# GeoAI-skills

地理空間データの分析 (GeoAI、地理空間の機械学習) を、データを選ぶところから、評価を疑うところまで、人や AI エージェントが自力で進めるための手順書の集まり。教科書のように読め、そのままエージェントのスキルとしても使える。

## 最初の 1 時間

1. [docs/setup.md](docs/setup.md) で `uv` を入れる (または Docker で一式を用意する)。
2. [docs/tutorial/README.md](docs/tutorial/README.md) の最初のコードを、そのまま写して流す。
3. 分からない言葉が出たら、[docs/glossary.md](docs/glossary.md) を引く。

## 前提: QGIS ではなく Python を使う

このリポジトリの手順は、QGIS の画面操作では再現できない。QGIS をやめて、Python (と SQL) でコードを書く覚悟を決めてから読む。

理由は 3 つ。評価の分け方を 1 回だけ作ってファイルに残し、基準もモデルも同じ分割で採点するには、コードが要る。結合や集計で入力の行がどうなったかを数え、合わなければ止めるには、コードが要る。単位の大きさや分け方を変えて、同じ分析を何十回も流し直すには、コードが要る。QGIS を地図を眺めるために併用するのは構わないが、分析そのものは Python で書く。

最初は、[docs/setup.md](docs/setup.md) で環境を用意し (入れるのは `uv` だけ。Docker で一式を用意する手順と、QGIS の操作との対応表もある)、[docs/tutorial/README.md](docs/tutorial/README.md) のコードを、そのまま写して流すところから始めればよい。

## どこから読むか

1. [docs/setup.md](docs/setup.md): 環境の準備。`uv` を入れ、QGIS でやっていたことを SQL でどう書くかを知る。
2. [docs/tutorial/README.md](docs/tutorial/README.md): 座標の基礎から、国の平均寿命の予測を最初から最後まで通す入門。実際に流して、画面の出力を載せてある。手を動かして読む。続きの [入門 2](docs/tutorial/points.md) は、点のデータから、投影、格子、空間を考えた評価までを通す。
3. [docs/glossary.md](docs/glossary.md): CRS、Moran's I、リーク、交差検証などの用語集。分からない言葉が出たら引く。
4. [AGENTS.md](AGENTS.md) (このリポジトリの直下): 分析の流れ全体。どの問いにどのスキルを使うかが分かる。
5. `.agents/skills/<スキル>/SKILL.md`: 問いごとの手順。必要なものだけ読めばよい。どのスキルも、それだけで最後まで進められるように書いてある。

進み具合の表 [.agents/skills/TODO.md](.agents/skills/TODO.md) は、リポジトリ直下でなく `.agents/skills/` の中にある。`.agents/skills/AGENTS.md` は、スキルを書く人向けの決まりで、使う人が読む必要はない。

## テーマから使うスキルを選ぶ

| やりたいこと | 読むスキル |
|---|---|
| 国や地域ごとの指標を、他の指標から予測したい | eda-and-baseline、cross-validation-design、spatial-data-modeling |
| 紛争や事故の起きやすい場所を、格子ごとに予測したい | analysis-unit-design、spatial-feature-engineering、cross-validation-design |
| 時間とともに変わる値の先を当てたい | time-series-forecasting |
| 観測した地点の値から、観測していない地点の値を推定したい | spatial-interpolation |
| 自分のモデルの点数が高すぎる気がする | leakage-audit、cross-validation-design、noise-ceiling-analysis |
| 予測にどれだけ自信を持てるか示したい | uncertainty-estimation |
| どの特徴量がどう効いているか説明したい | model-explanation |
| 値が近い場所で似ているか、どこに集まっているか知りたい | spatial-autocorrelation |
| 国や地点を似たものどうしに分けたい | clustering-analysis、dimensionality-reduction |
| おかしな値、突出した場所を見つけたい | anomaly-detection |
| 点 (施設、事件) が集まっているか知りたい | point-pattern-analysis |
| 歩いて何分か、道のりで測りたい | spatial-network-analysis |
| 施設をどこに置くか決めたい | spatial-optimization |
| 人口や標高、土地被覆のラスタを、区や格子や地点に集計したい | raster-data-integration、analysis-unit-design |
| 旧市町村の人口を新市町村へ、メッシュの統計を行政区へ、境界の違う区域へ移したい | areal-interpolation、analysis-unit-design |
| 結論が単位の取り方に左右されないか確かめたい | robustness-analysis、analysis-unit-design |
| どのデータを使えるか探したい | dataset-discovery、data-variable-semantics |
| 記録が多い場所は、本当に現象が多いのか、観測されやすいだけなのか確かめたい | observation-bias-audit |
| このデータの品質 (位置の正確さ、欠け、新しさ) で、結論を支えられるか確かめたい | data-quality-audit |
| これから観測する地点を、どこに、何地点、どう選ぶか決めたい | spatial-sampling-design |
| 人や世帯の位置を含むデータを、使い、共有し、公開してよいか判断したい | location-privacy |

## 何が入っているか

分析の流れは 5 つの段階に分かれている。

| 段階 | 答える問い | スキル |
|---|---|---|
| データを知る | どのデータで答えられるか。変数は問いの言葉と同じものを指すか。その品質で結論を支えられるか。記録の多さは現象の多さか、観測のされやすさか。これから観測するならどこを測るか。位置を使い、共有し、公開してよいか | dataset-discovery、data-variable-semantics、data-quality-audit、observation-bias-audit、spatial-sampling-design、location-privacy |
| 単位を決めて、データをそろえる | 1 行は何か。複数のデータをどう結ぶか。ラスタの値をどう単位に集めるか。境界の違う区域の値をどう移すか。どんな特徴量を作るか | analysis-unit-design、spatial-data-integration、raster-data-integration、areal-interpolation、spatial-feature-engineering |
| 予測して、評価を疑う | 基準は。評価の分け方は。点数は信じてよいか。どこまで良くなりうるか。結論は頑健か | eda-and-baseline、cross-validation-design、spatial-data-modeling、time-series-forecasting、spatial-interpolation、leakage-audit、noise-ceiling-analysis、uncertainty-estimation、model-explanation、robustness-analysis |
| 構造を探す | 近い単位どうしで似ているか。群はあるか。外れはあるか。点は集まっているか | spatial-autocorrelation、clustering-analysis、dimensionality-reduction、anomaly-detection、point-pattern-analysis |
| ネットワークと最適化 | 実際に歩いて何分か。施設をどこに置くか | spatial-network-analysis、spatial-optimization |

まだ無いもの: 分析を成果物にまとめる `analysis-reporting`、最適化の発展的な内容。進み具合は [.agents/skills/TODO.md](.agents/skills/TODO.md)。

## 動かすために

- Python の道具は `uv` を使う。スクリプトは `uvx --with ... python scripts/<name>.py` で、環境を作らずに動く。
- Python の道具は `uv` だけで動く。大きなデータを流すときは、自分の環境のメモリと CPU に合わせて、並列の数やデータの量を考える。
- スキルを書く人向けの決まり (作者の環境の話を含む) は `.agents/skills/AGENTS.md` にある。独立の検査は `python3 .agents/skills/check_skills.py` (PyYAML が要る。Docker の環境には入っている)。

## 数字について

スキルや reference に書いた数字は、日付と版を付けて実データで測ったもの。「以前の分析」「以前の調査」と書いた数字は、このリポジトリでは測り直していない。

## 関連するスキル集

大きなジョブを流す技術 (分割、再開、事前の検査) は、外のスキル集が詳しい。違いと注意は [docs/related-work.md](docs/related-work.md)。
