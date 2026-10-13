# Autonomous-GeoAI

地理空間データの分析 (GeoAI、地理空間の機械学習) を、データを選ぶところから、評価を疑うところまで、人や AI エージェントが自力で進めるための手順書の集まり。教科書のように読め、そのままエージェントのスキルとしても使える。

## どこから読むか

1. [docs/tutorial/README.md](docs/tutorial/README.md): 座標の基礎から、国の平均寿命の予測を最初から最後まで通す入門。実際に流して、画面の出力を載せてある。まずこれを手を動かして読む。
2. [docs/glossary.md](docs/glossary.md): CRS、Moran's I、リーク、交差検証などの用語集。分からない言葉が出たら引く。
3. [AGENTS.md](AGENTS.md) (このリポジトリの直下): 分析の流れ全体。どの問いにどのスキルを使うかが分かる。
4. `.agents/skills/<スキル>/SKILL.md`: 問いごとの手順。必要なものだけ読めばよい。どのスキルも、それだけで最後まで進められるように書いてある。

進み具合の表 [.agents/skills/TODO.md](.agents/skills/TODO.md) は、リポジトリ直下でなく `.agents/skills/` の中にある。`.agents/skills/AGENTS.md` は、スキルを書く人向けの決まりで、使う人が読む必要はない。

## 何が入っているか

分析の流れは 5 つの段階に分かれている。

| 段階 | 答える問い | スキル |
|---|---|---|
| データを知る | どのデータで答えられるか。変数は問いの言葉と同じものを指すか | dataset-discovery、data-variable-semantics |
| 単位を決めて、データをそろえる | 1 行は何か。複数のデータをどう結ぶか。どんな特徴量を作るか | analysis-unit-design、spatial-data-integration、spatial-feature-engineering |
| 予測して、評価を疑う | 基準は。評価の分け方は。点数は信じてよいか。どこまで良くなりうるか。結論は頑健か | eda-and-baseline、cross-validation-design、spatial-data-modeling、time-series-forecasting、leakage-audit、noise-ceiling-analysis、uncertainty-estimation、model-explanation、robustness-analysis |
| 構造を探す | 近い単位どうしで似ているか。群はあるか。外れはあるか。点は集まっているか | spatial-autocorrelation、clustering-analysis、dimensionality-reduction、anomaly-detection、point-pattern-analysis |
| ネットワークと最適化 | 実際に歩いて何分か。施設をどこに置くか | spatial-network-analysis、spatial-optimization |

まだ無いもの: 分析を成果物にまとめる `analysis-reporting`、最適化の発展的な内容。進み具合は [.agents/skills/TODO.md](.agents/skills/TODO.md)。

## 動かすために

- Python の道具は `uv` を使う。スクリプトは `uvx --with ... python scripts/<name>.py` で、環境を作らずに動く。
- 自分の PC では、`uv` だけで動く。メモリと CPU の上限 (`systemd-run`) は、このリポジトリを作った Linux の機械 (swap が無く、メモリが尽きると機械ごと止まる) の事情で付けている。Windows や macOS では使えず、付けなくてもよい。大きなデータを流すときは、自分の環境に合わせて上限を考える。
- スキルの書き方と、独立させる決まりは同じファイル。`python3 .agents/skills/check_skills.py` で確かめる。

## 数字について

スキルや reference に書いた数字は、日付と版を付けて実データで測ったもの。「以前の分析」「以前の調査」と書いた数字は、このリポジトリでは測り直していない。
