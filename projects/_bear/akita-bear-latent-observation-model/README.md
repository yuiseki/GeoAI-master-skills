# akita-bear-latent-observation-model

人が持つ熊の分布の記録は、全て何かの観測過程を通した記録で、熊の真の生息域や利用の強さの正解 (golden data) は無い。観測の偏りの違う 2 つの熊の観測系 (環境省の分布メッシュ、クマダスの通報) と人側の空間利用の proxy を同時にモデル化したとき、共通する潜在の bear space use と human space use をどこまで識別できるか、2023〜2026 年の通報の変化を「熊側の変化」と「人側・通報の過程の変化」に分けられるかを調べる。

新しい予測変数を探す研究ではない。中心は、潜在状態と観測過程の分離と、その識別可能性 (identifiability)。実データに当てる前に、同じ構造の合成データで識別できるかを確かめる。

- 概念モデル: [CONCEPT.md](CONCEPT.md)
- 関連する研究 (Web で確かめた範囲と未確認): [RELATED_WORK.md](RELATED_WORK.md)
- 計画 (結果を見る前に固定): [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)
- 実行の記録: [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)
- 報告: [report.md](report.md)
- 熊の観測データの棚卸し (観測の過程で並べ、次に取るデータを決める): [BEAR_OBSERVATION_INVENTORY.md](BEAR_OBSERVATION_INVENTORY.md)
- V1〜V3 の存在の確認 (公開資料の一次確認): [BEAR_DATA_AVAILABILITY_AUDIT.md](BEAR_DATA_AVAILABILITY_AUDIT.md)

```
scripts/     コードとテスト (pytest)
outputs/     報告が引く小さな結果 (JSON) と図 (PNG)
artifacts/_bear/akita-bear-latent-observation-model/
  mesh/      5 km メッシュの入力の表 (派生物)
  sim/       合成データと事後分布の要約 (合成で、観測ではない)
  fit/       実データの事後分布 (派生物)
```

## 再現

リポジトリの根から流す。前提は [akita-bear-risk-grid-100m](../akita-bear-risk-grid-100m/) と [akita-bear-human-interface](../akita-bear-human-interface/) の artifacts。JAX は CPU で、合成の当てはめ 1 本に 1〜3 分かかる。メモリの無いマシンでは `systemd-run --user --scope -p MemoryMax=6G -p MemorySwapMax=0` で 1 本ずつ上限を付け、4 本ずつ並べて流した。

```sh
P=projects/_bear/akita-bear-latent-observation-model
W=artifacts/_bear/akita-bear-latent-observation-model
NP="uvx --with numpyro==0.22.0 --with jax==0.12.0.1 --with numpy==2.5.4 --with scipy --with pandas --with pyarrow"

# 1. 入力の整列 (5 km メッシュの表、outputs/inputs_summary.json)
PYTHONPATH=projects/_bear/akita-bear-risk-grid-100m/scripts:projects/_bear/akita-bear-human-interface/scripts \
  env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK uvx --from 'duckdb>=1.5.5' --with numpy==2.5.4 \
  --with scipy --with pandas --with pyarrow --with pyproj --with shapely --with scikit-learn==1.9.1 python \
  $P/scripts/align_inputs.py artifacts/_bear/akita-bear-risk-grid-100m artifacts/_bear/akita-bear-human-interface \
  $W/mesh $P/outputs/inputs_summary.json

# 2. 合成データの関門 (S は S1〜S5、prior は default と wide)
#    段階 2a: --stage 2a (既定)、出力 base_<prior>_<S>.jsonl、seed 0 20
#    段階 1: --stage 1 --scenario S5、出力 stage1_<prior>_S5.jsonl
#    段階 2、3: --stage 2 / 3、出力 stage2_<prior>_<S>.jsonl / stage3_<prior>_<S>.jsonl
#    追加のデータの価値: --extra V1〜V6 --seeds 0 10 --prior default、S1、S2、S3、S5、出力 voi_<V>_<S>.jsonl
PYTHONPATH=$P/scripts $NP python $P/scripts/identifiability.py artifacts/_bear/akita-bear-risk-grid-100m $W \
  --scenario S1 --seeds 0 20 --prior default --stage 3 --out $W/sim/stage3_default_S1.jsonl

# 3. 関門の判定
python3 $P/scripts/gate.py $W/sim base $P/outputs/identifiability_gate_L3.json --stage 2a
python3 $P/scripts/gate.py $W/sim stage1 $P/outputs/identifiability_gate_stage1.json --stage 1
python3 $P/scripts/gate.py $W/sim stage2 $P/outputs/identifiability_gate_stage2.json --stage 2
python3 $P/scripts/gate.py $W/sim stage3 $P/outputs/identifiability_gate_stage3.json --stage 3

# 4. 実データ (full、cv、f1)
PYTHONPATH=$P/scripts $NP python $P/scripts/real_models.py full artifacts/_bear/akita-bear-risk-grid-100m $W \
  $P/outputs/real_full_default.json --prior default
PYTHONPATH=$P/scripts $NP python $P/scripts/real_models.py full artifacts/_bear/akita-bear-risk-grid-100m $W \
  $P/outputs/real_full_wide.json --prior wide --models L0H L2
PYTHONPATH=$P/scripts $NP python $P/scripts/real_models.py cv artifacts/_bear/akita-bear-risk-grid-100m $W \
  $P/outputs/real_cv_default.json --models L0 L0H L1 L2
PYTHONPATH=$P/scripts $NP python $P/scripts/real_models.py cv artifacts/_bear/akita-bear-risk-grid-100m $W \
  $P/outputs/real_cv_wide.json --prior wide --models L0H L2
PYTHONPATH=$P/scripts $NP python $P/scripts/real_models.py cv artifacts/_bear/akita-bear-risk-grid-100m $W \
  $P/outputs/real_cv_allmesh.json --models L0H L2 --all-meshes
PYTHONPATH=$P/scripts $NP python $P/scripts/real_models.py f1 artifacts/_bear/akita-bear-risk-grid-100m $W \
  $P/outputs/real_f1_shuffle.json

# 5. 要約と図
python3 $P/scripts/summarise.py $P/outputs $W/sim --voi
uvx --with numpy==2.5.4 --with matplotlib python $P/scripts/figures.py $P/outputs $W

# テスト
PYTHONPATH=$P/scripts $NP --with pytest python -m pytest -q -p no:cacheprovider $P/scripts
```
