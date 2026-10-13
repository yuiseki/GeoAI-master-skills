# ディリクレ過程の混合正規分布 (DPMM)

単位が、いくつかの正規分布の混合から出たと考え、群の数をデータに合わせて決める。上限 (`max_components`) を大きめに与えると、使われない成分の重みが 0 に近づく。

- `cluster_units.py` は scikit-learn の `BayesianGaussianMixture(weight_concentration_prior_type="dirichlet_process")` を使い、各単位を最も確からしい成分に入れる。実際に使われた成分だけを 0 から番号を振り直す。
- 群の数が決まる、といっても、事前分布の強さ (`weight_concentration_prior`、既定のまま) と上限に左右される。上限を変えて群の数が変わらないかを見る。
- 楕円の群を取れるが、行が少ないと共分散の推定が不安定になる。SKILL.md の例 (207 か国、4 特徴量、上限 10) では 6 つの群ができ、1 か国と 2 か国だけの群を含み、安定性の ARI は 0.512 で、k-means の k=3 (0.954) より大きく低かった。
- 各単位がどの群にどれだけの確率で入るかも出せる (`predict_proba`)。境界にいる単位を見つけるのに使える (`cluster_units.py` には未実装)。
