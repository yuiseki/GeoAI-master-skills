# japan-bear-sighting-forecast

秋田県の市町村ごとの、週ごとのツキノワグマ出没通報件数を、1〜8 週先まで予測する。使い道は、パトロールと注意喚起の重点の参考。岐阜県の月次で、手順の再現と基準の比較もした。日本全体のモデルは立てていない (理由は `report.md` のデータの節)。

- 報告: [report.md](report.md)
- 計画 (流す前に固定): [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)
- 実行の記録: [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)
- 状態: 秋田の予測を 2026-10-26 に凍結した。2026-10 以降の通報が配布されたら、下の手順で採点する (未実施)。

```
scripts/        自分で書いたコードとテスト (73 件)
outputs/        報告が引く小さな表と図 (CSV、JSON、PNG)
artifacts/japan-bear-sighting-forecast/   大きな生成物 (週と月の表、隣接、全ての予測、凍結した予測と来歴)
```

## 再現

版は、Python 3.12.2、numpy 2.5.4、pandas 3.1.0、scikit-learn 1.9.1、DuckDB 2.0.0。入力は Hugging Face の版を固定して読む (`scripts/build_table.py`、`build_table_gifu.py`)。この母艦では、重い実行にメモリと CPU の上限を付ける (下の `systemd-run`)。

```sh
cd <リポジトリの直下>
P=projects/japan-bear-sighting-forecast; A=artifacts/japan-bear-sighting-forecast
# 1. 表を作る。行数の保存を出力する
uvx --from 'duckdb>=1.5.5' python $P/scripts/build_table.py $A/akita_week.parquet
uvx --from 'duckdb>=1.5.5' python $P/scripts/build_table_gifu.py $A/gifu_month.parquet
uvx --from 'duckdb>=1.5.5' python $P/scripts/build_adjacency.py 05 $A/akita_adjacency.parquet
# 2. ローリング起点の評価 (秋田、候補の比較)
R="systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=800% -- uvx --with numpy --with pandas --with scikit-learn --with pyarrow --with scipy python"
$R $P/scripts/evaluate.py $A/akita_week.parquet $A/eval_b2 --adjacency $A/akita_adjacency.parquet \
   --models naive mean_short seasonal_3y glm hgb glm_nb hgb_nb hier_hgb
# 3. 岐阜の確認 (基準だけ。月次)
$R $P/scripts/evaluate.py $A/gifu_month.parquet $A/gifu_b4 --period monthly --horizons 1 2 3 --origin-from 24 \
   --models naive mean_short muni_mean seasonal_naive seasonal3
uvx --with numpy --with pandas --with pyarrow --with scipy --with scikit-learn python $P/scripts/analyze_c1.py $A/gifu_b4_predictions.parquet $P/outputs/c1_gifu_b4.json
# 4. テスト
uvx --with 'duckdb>=1.5.5' --with numpy --with pandas --with scikit-learn --with pyarrow --with scipy --with matplotlib --with pytest python -m pytest -q $P/scripts
```

`evaluate.py` は、起点 o までの週だけをモデルに渡し、特徴量は起点までの値だけから作る (テストで、起点より後を壊しても予測が変わらないことを確かめている)。

## 凍結した予測の採点 (2026-10 以降)

凍結した予測の週に、配布元の新しい版が通報を出したら、取り直した版で採点する。配布元は毎月上書きするので、版の取得日を記録に書く。最後の完全な週を `--last` に渡す。

```sh
uvx --from 'duckdb>=1.5.5' python $P/scripts/build_table.py $A/akita_week_later.parquet --sighting <新しい版の Parquet か URL> --last <最後の完全な週の月曜>
sha256sum $A/frozen/akita_frozen_2026-10-26.parquet   # 来歴 JSON のハッシュと一致するか、採点の前に確かめる
uvx --with numpy --with pandas --with pyarrow --with scipy --with scikit-learn python $P/scripts/score_frozen.py \
    $A/frozen/akita_frozen_2026-10-26.parquet $A/akita_week_later.parquet $P/outputs/score_frozen.json
```

規則は `EXPERIMENT_PLAN.md` の B5。凍結した候補、特徴量、市町村の単位は、結果が悪くても変えない。変えるなら探索として別に残す。

## 派生物

`artifacts/japan-bear-sighting-forecast/frozen/` の予測は派生物で、観測ではない。後段で観測の件数や学習の行として使わない。作ったスクリプトとハッシュ、入力の版、設定、確かめていないことは、同じ場所の `*.provenance.json` にある。このリポジトリでは `projects/` と `artifacts/` は git に入れない (`.gitignore`)。
