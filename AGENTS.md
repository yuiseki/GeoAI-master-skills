# GeoAI-skills: 分析の流れ

地理空間データの分析を頼まれたら、この流れで進める。各段階の手順は `.agents/skills/<スキル>/SKILL.md` にある。問いに合うスキルだけを読み、全部を読まなくてよい。知らない用語は [docs/glossary.md](docs/glossary.md) で引く。スキルを書く、直すときの決まりは `.agents/skills/AGENTS.md`。

## 進め方の原則

- 結論から逆算して、動く最小のものを先に作る。変数を 1 つずつ変える。
- 数字は自分で測る。測った日、データの版、ツールの版を書く。確かめていないことは「未確認」と書く。
- 失敗は失敗の顔をさせる。エラーを既定値で埋めない。結合や集計で、入力の行がどうなったかを数える。
- 評価は、基準と同じ分割、同じ指標で並べる。点数が良すぎるときは、まず疑う。
- 大きなデータの処理は、自分の環境のメモリと CPU に収まるようにする。
- 知らない用語に出会ったら、先に [docs/glossary.md](docs/glossary.md) を読む。
- 結論は、頑健性 (単位、分け方、標本、設定を変えても保たれるか) を確かめてから書く。確かめていなければ、そう書く。

## 流れ

1. 問いと使い道を 1 行で書く。「何を、どの単位で、何のために予測する (または知る) か」。使い道は評価の分け方を決める。
2. データを知る。使うデータセットを選び、列、粒度、範囲、注意点を実データで測る (`dataset-discovery`)。変数が問いの言葉と同じものを指すかを、定義と実データで照合する (`data-variable-semantics`)。
3. 単位を決める (`analysis-unit-design`)。標本の数、0 の割合、位置の精度、単位の選び方による結論の変化 (MAUP) を数える。
4. データをそろえる。複数のデータを単位に結合し、全ての行を数える (`spatial-data-integration`)。ラスタ (人口、標高、土地被覆のクラスなど) の値を単位に集めるなら、画素の意味 (量か水準かクラスか、NoData は何か) を先に決め、NoData と範囲外を分けて数え、量なら総量を照合する (`raster-data-integration`)。ある区域で集計された値を、境界の違う別の区域へ移すなら、値の種類 (量、比、水準) と置いた仮定を書き、覆われ方と総量を数え、できれば細かい真値で誤差を測る (`areal-interpolation`)。特徴量を作る (`spatial-feature-engineering`)。
5. 予測が問いなら:
   1. 分布、欠損、相関を見て、基準の点数を出す (`eda-and-baseline`)。
   2. 使い道から評価の分け方を決め、分割表を 1 つ作る (`cross-validation-design`)。
   3. モデルを足して、同じ分割表で比べる (`spatial-data-modeling`)。時間の順がある系列を先まで当てるなら `time-series-forecasting`。自分のコードで予測する場合も、先に `time-series-forecasting/scripts/series_breaks.py` で系列ごとの水準の跳ねを探し、出力を報告書に貼る。
   4. 点数を疑う。特徴量のリーク (`leakage-audit`)、測定の雑音の天井 (`noise-ceiling-analysis`)、不確かさ (`uncertainty-estimation`)、特徴量の効き方 (`model-explanation`)。
6. 構造が問いなら、問いごとに選ぶ。
   - 近い単位どうしで似ているか、どこに集まっているか: `spatial-autocorrelation`
   - 群があるか: `clustering-analysis`。軸に要約できるか: `dimensionality-reduction`
   - 外れがあるか: `anomaly-detection`
   - 点が集まっているか: `point-pattern-analysis`
7. 距離が道のりで決まる問い、置き場所を選ぶ問いは `spatial-network-analysis`、`spatial-optimization`。
8. 結論を式で書き、条件を変えて保たれるかを確かめる (`robustness-analysis`)。地理的な単位 (市区町村、国、格子) の間の相関や回帰が結論なら、書く前に 2 つを実行して数字を報告書に貼る。変数それぞれの Moran's I (`spatial-autocorrelation/scripts/spatial_autocorrelation.py`、回帰なら残差の I) と、大きさをそろえた格子 3 段以上での同じ相関 (`analysis-unit-design` の MAUP の節)。行政区の階層を変えただけでは、単位の大きさの効果と境界の効果が混ざる。
9. 書き出す。仮説、データ (版)、方法、評価 (分け方ごと)、反証、限界、結論。成果物にまとめるスキル (`analysis-reporting`) は未着手。

## 道具

- スクリプトは `uvx --with ... python scripts/<name>.py`。引数はスクリプトの先頭の説明にある。
- データセットの事実 (列、粒度、注意点) は `.agents/skills/dataset-discovery/references/`。
- 初めての人には [docs/tutorial/README.md](docs/tutorial/README.md) と [docs/glossary.md](docs/glossary.md)。
