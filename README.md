# GeoAI-master-skills

地理空間データの分析 (GeoAI、地理空間の機械学習) を、データを選ぶところから、評価を疑うところまで、人や AI エージェントが自力で進めるための手順書の集まり。教科書のように読め、そのままエージェントのスキルとしても使える。

## 最初の 1 時間

1. [docs/setup.md](docs/setup.md) で `uv` を入れる (または Docker で一式を用意する)。
2. [docs/tutorial/README.md](docs/tutorial/README.md) の最初のコードを、そのまま写して流す。
3. 分からない言葉が出たら、[docs/glossary.md](docs/glossary.md) を引く。

## 前提: QGIS ではなく Python を使う

このリポジトリの手順は、QGIS の画面操作では再現できない。QGIS をやめて、Python (と SQL) でコードを書く覚悟を決めてから読む。

理由は 3 つ。評価の分け方を 1 回だけ作ってファイルに残し、基準もモデルも同じ分割で採点するには、コードが要る。結合や集計で入力の行がどうなったかを数え、合わなければ止めるには、コードが要る。単位の大きさや分け方を変えて、同じ分析を何十回も流し直すには、コードが要る。QGIS を地図を眺めるために併用するのは構わないが、分析そのものは Python で書く。

## どこから読むか

1. [docs/setup.md](docs/setup.md): 環境の準備。`uv` を入れ、QGIS でやっていたことを SQL でどう書くかを知る。
2. [docs/tutorial/README.md](docs/tutorial/README.md): 座標の基礎から、国の平均寿命の予測を最初から最後まで通す入門。実際に流して、画面の出力を載せてある。手を動かして読む。続きの [入門 2](docs/tutorial/points.md) は、点のデータから、投影、格子、空間を考えた評価までを通す。
3. [docs/glossary.md](docs/glossary.md): CRS、Moran's I、リーク、交差検証などの用語集。分からない言葉が出たら引く。
4. [AGENTS.md](AGENTS.md) (このリポジトリの直下): 分析の流れ全体。どの問いにどのスキルを使うかが分かる。
5. `.agents/skills/<スキル>/SKILL.md`: 問いごとの手順。必要なものだけ読めばよい。どのスキルも、それだけで最後まで進められるように書いてある。

進み具合の表 [.agents/skills/TODO.md](.agents/skills/TODO.md) は、リポジトリ直下でなく `.agents/skills/` の中にある。`.agents/skills/AGENTS.md` は、スキルを書く人向けの決まりで、使う人が読む必要はない。

## テーマから使うスキルを選ぶ

知りたいことが、予測 (どこで、どれだけ起こるか) か、関連や構造 (どこで高いか、似ているか) か、因果 (何かを変えたら結果が変わるか) かで、読むスキルが変わる。因果なら、表のどの行より先に causal-design を読む。

| やりたいこと | 読むスキル |
|---|---|
| 国や地域ごとの指標を、他の指標から予測したい | eda-and-baseline、cross-validation-design、spatial-data-modeling |
| 紛争や事故の起きやすい場所を、格子ごとに予測したい | analysis-unit-design、spatial-feature-engineering、cross-validation-design |
| 時間とともに変わる値の先を当てたい | time-series-forecasting |
| 地点ごとに繰り返し観測した値を、観測の無い地点や先の時刻へ予測したい | spatiotemporal-modeling |
| 観測した地点の値から、観測していない地点の値を推定したい | spatial-interpolation |
| 自分のモデルの点数が高すぎる気がする | leakage-audit、cross-validation-design、noise-ceiling-analysis |
| 予測にどれだけ自信を持てるか示したい | uncertainty-estimation |
| どの特徴量がどう効いているか説明したい | model-explanation |
| 値が近い場所で似ているか、どこに集まっているか知りたい | spatial-autocorrelation |
| 国や地点を似たものどうしに分けたい | clustering-analysis、dimensionality-reduction |
| おかしな値、突出した場所を見つけたい | anomaly-detection |
| 点 (施設、事件) が集まっているか知りたい | point-pattern-analysis |
| 点のパターンが、どんな過程 (説明変数で変わる強度、観測していない環境、引き合い) から生まれたかをモデル化したい | spatial-process-modeling |
| 歩いて何分か、道のりで測りたい | spatial-network-analysis |
| 道路に限定せず、面上の移動コストから最寄りの目的地までの最小到達コストを求めたい | raster-cost-distance |
| 土地被覆の分類図から、クラスごとのコストを決めて cost raster を作りたい | land-cover-cost |
| 人口や需要に対して、施設やサービスへのアクセスが足りているか、足りない場所はどこかを知りたい | spatial-accessibility-analysis |
| 施設をどこに置くか決めたい | spatial-optimization |
| 人口や標高、土地被覆のラスタを、区や格子や地点に集計したい | raster-data-integration、analysis-unit-design |
| 旧市町村の人口を新市町村へ、メッシュの統計を行政区へ、境界の違う区域へ移したい | areal-interpolation、analysis-unit-design |
| 結論が単位の取り方に左右されないか確かめたい | robustness-analysis、analysis-unit-design |
| どのデータを使えるか探したい | dataset-discovery、data-variable-semantics |
| 記録が多い場所は、本当に現象が多いのか、観測されやすいだけなのか確かめたい | observation-bias-audit |
| このデータの品質 (位置の正確さ、欠け、新しさ) で、結論を支えられるか確かめたい | data-quality-audit |
| これから観測する地点を、どこに、何地点、どう選ぶか決めたい | spatial-sampling-design |
| 人や世帯の位置を含むデータを、使い、共有し、公開してよいか判断したい | location-privacy |
| 施設や規制の効果 (因果) を、このデータから言えるか判断したい | causal-design |
| 識別できると判定した効果の大きさを推定したい | causal-estimation |

## 何が入っているか

スキルは、どの問いでも通る準備と、問いの種類で分かれる分析と、結論を疑って残す仕上げに分かれる。最初に問いの種類を決める。「来年どこで事故が起こるか」は予測、「駅の近くで地価が高いか」は関連や構造、「道路整備が事故を減らしたか」「駅を新設すると地価が上がるか」は因果。因果の問いだけは、データに手を付ける前に「因果を問う」(causal-design) で、識別できるかを設計する。設計の表 (処置の時点、推定の対象、調整する変数としてはいけない変数、支え、波及) は、その後の準備と分析の選び方を縛る。

| 区分 | 段階 | 答える問い | スキル |
|---|---|---|---|
| 問いを決める | 因果を問う (因果の問いのときだけ、準備の前に) | この因果効果を、このデータと仮定から識別できるか。処置、結果、推定の対象、調整する変数、してはいけない変数、識別の仮定は何か | causal-design |
| 共通の準備 | データを知る | どのデータで答えられるか。変数は問いの言葉と同じものを指すか。その品質で結論を支えられるか。記録の多さは現象の多さか、観測のされやすさか。これから観測するならどこを測るか。位置を使い、共有し、公開してよいか | dataset-discovery、data-variable-semantics、data-quality-audit、observation-bias-audit、spatial-sampling-design、location-privacy |
| 共通の準備 | 単位を決めて、データをそろえる | 1 行は何か。複数のデータをどう結ぶか。ラスタの値をどう単位に集めるか。境界の違う区域の値をどう移すか。どんな特徴量を作るか | analysis-unit-design、spatial-data-integration、raster-data-integration、areal-interpolation、spatial-feature-engineering |
| 問いに応じた分析 | 予測して、評価を疑う | 基準は。評価の分け方は。点数は信じてよいか。どこまで良くなりうるか | eda-and-baseline、cross-validation-design、spatial-data-modeling、time-series-forecasting、spatiotemporal-modeling、spatial-interpolation、leakage-audit、noise-ceiling-analysis、uncertainty-estimation、model-explanation |
| 問いに応じた分析 | 構造を探す | 近い単位どうしで似ているか。群はあるか。外れはあるか。点は集まっているか。点はどんな過程から生まれたか | spatial-autocorrelation、clustering-analysis、dimensionality-reduction、anomaly-detection、point-pattern-analysis、spatial-process-modeling |
| 問いに応じた分析 | ネットワークと最適化 | 実際に歩いて何分か。道の無い面を進むと何分か。施設をどこに置くか | spatial-network-analysis、land-cover-cost、raster-cost-distance、spatial-accessibility-analysis、spatial-optimization |
| 問いに応じた分析 | 因果の効果を推定する | 識別できると判定した効果は、どれだけか、どれだけ確かか。重なりと重みとバランスは足りているか | causal-estimation (調整の集合で識別する型だけ。因果を問う の後に来る) |
| 結論を疑う、残す | 頑健性と報告 | 結論は、単位、分け方、標本、設定を変えても保たれるか。どう成果物に残すか | robustness-analysis、analysis-reporting (未着手) |

予測の精度、回帰の係数、パネルの固定効果、階層モデルのランダム効果、特徴量の重要度は、どれも因果の識別を保証しない。因果を言うなら、識別の設計と、そこで置いた仮定を添える。

## 扱う範囲と扱わない範囲

扱うもの:
- 表とベクタの地理空間データ (点、線、面、格子) と、値の意味が決まったラスタ (人口、標高、土地被覆のクラスなど) の分析。
- データを選び、変数の意味と品質を確かめ、単位を決めてそろえるところから、結論を疑って書き出すところまで。
- 予測と、その評価の分け方、リーク、雑音の天井、不確かさ。
- 構造の探索: 空間の自己相関、群、外れ、点のパターン。
- モデル: 線形、木、ブースティング、事前学習モデル、パネルの固定効果、階層モデル、共役な事前分布のベイズ、測定の誤差、時空間の分解、Poisson 過程の尤度。
- 因果の問いの、識別の設計 (DAG、支え、波及、感度) と、調整の集合で識別できる効果の推定 (回帰による調整、IPW、AIPW)。
- 道のりの距離、cost raster の上の最小累積コスト、需要に対する施設のアクセス (2SFCA)、施設の配置の最適化。

扱わないもの (意図して外している):
- 衛星画像や空中写真そのものの解析。画像の分類、セグメンテーション、物体検出、画像の基盤モデル、変化検出など。
- 大きなジョブを壊さずに流す技術 (分割、再開、配布)。外のスキル集が詳しい ([docs/related-work.md](docs/related-work.md))。

まだ無いもの (いずれ足す候補):
- 因果の効果の推定のうち、マッチング、差の差、操作変数、回帰不連続、合成対照、波及の効果。
- MCMC。ベイズは解析的に解けるモデルだけ。
- 空間ラグと空間誤差のモデル、GWR の実装 (選び方の説明はある)。時空間のクリギング、ガウス過程、SPDE。Cox 過程、点どうしの相互作用、Hawkes 過程。
- 分析を成果物にまとめる `analysis-reporting`。最適化の発展的な内容。

スクリプトは小さく、答えの分かる例と確立した実装で確かめてあるが、上の手法をすべて覆うものではない。エージェントがスキルを使って分析をやり遂げられるかの評価も、一部のスキルだけ。進み具合は [.agents/skills/TODO.md](.agents/skills/TODO.md)、評価は [docs/eval-status.md](docs/eval-status.md)。

## 動かすために

- Python の道具は `uv` だけで動く。スクリプトは `uvx --with ... python scripts/<name>.py` で、環境を作らずに動く。大きなデータを流すときは、自分の環境のメモリと CPU に合わせて、並列の数やデータの量を考える。
- スキルを書く人向けの決まり (作者の環境の話を含む) は `.agents/skills/AGENTS.md` にある。独立の検査は `python3 .agents/skills/check_skills.py` (PyYAML が要る。Docker の環境には入っている)。

## 数字について

スキルや reference に書いた数字は、日付と版を付けて実データで測ったもの。「以前の分析」「以前の調査」と書いた数字は、このリポジトリでは測り直していない。

主なモデルのスクリプト (パネルの固定効果、階層モデル、DAG の調整の集合、時空間の分解、点過程の尤度、共役なベイズ) は、確立した実装 (pyfixest、statsmodels、networkx、pgmpy、PySAL、scipy) と数値を突き合わせてある。DAG は無作為なグラフで、それ以外は合成データと実データで照合した。各スクリプトの `test_*_crosscheck.py` と、reference の「外部の実装との照合」の節にある。

スクリプトが正しく動くことと、エージェントがスキルを使って分析をやり遂げられることは別の話。後者をどこまで評価したかは [docs/eval-status.md](docs/eval-status.md) にある。独立に評価したスキルは、まだ一部だけ。

## 関連するスキル集

大きなジョブを流す技術 (分割、再開、事前の検査) は、外のスキル集が詳しい。違いと注意は [docs/related-work.md](docs/related-work.md)。
