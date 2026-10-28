# akita-bear-mast-exposure

年に 1 つの秋田県のブナの豊凶 (mast_scarcity) と、100 m セルごとのブナ・ナラ類の植生の exposure の積を、既存の B_env (akita-bear-risk-grid-100m) のスコアに 1 つの係数で足すと、クマ出没の通報のセルの順位が良くなるかを確かめる。B_env は作り直さない。

- 計画 (確認の前に固定): [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)
- 実行の記録: [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)

```
scripts/     コードとテスト (pytest)
outputs/     報告が引く小さな結果 (CSV、JSON、PNG)
artifacts/akita-bear-mast-exposure/   セルごとの exposure などの大きな中間物 (commit しない)
```

- 報告: [report.md](report.md)

## 再現

リポジトリの直下から。版: Python 3.12、numpy、scipy、scikit-learn、DuckDB 2.0.0、rasterio、shapely、pyproj (uvx が取る版)。入力は `artifacts/akita-bear-risk-grid-100m/` (既存のクマのプロジェクトの格子、通報、保存済みの B_env) と、固定した版の Hugging Face の植生と森林資源メッシュ。この母艦では、重い実行にメモリと CPU の上限を付け、anaconda の GDAL と PROJ の環境変数を外す。

```sh
P=projects/akita-bear-mast-exposure; S=$P/scripts; A=artifacts/akita-bear-mast-exposure; B=artifacts/akita-bear-risk-grid-100m
M=projects/beech-masting-triggers/outputs/tohoku_beech_index.csv
E="env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK"
L="systemd-run --user --scope -q -p MemoryMax=16G -p MemorySwapMax=0 -p CPUQuota=800% --"
export PYTHONPATH=projects/akita-bear-risk-grid-100m/scripts:$S   # metrics.py は既存のクマのプロジェクトのものを使う
U="uvx --with numpy --with pandas --with pyarrow --with scikit-learn python"
# 1. 凡例の分類 (legend_akita.tsv は植生の版 b3b36a0 の docs/ から取る)
mkdir -p $A/raw && curl -sfL https://huggingface.co/datasets/yuiseki/akita-vegetation-2024/resolve/b3b36a0fb6ff027fb1f483be3288df2df76c0cf3/docs/legend_akita.tsv -o $A/raw/legend_akita.tsv
python3 $S/mapping.py $A/raw/legend_akita.tsv $P/outputs/vegetation_mapping.csv
# 2. exposure と QA
$E $L uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with shapely --with pyproj --with rasterio --with affine python $S/exposure.py $B $P/outputs/vegetation_mapping.csv $A $P/outputs/exposure_build.json
$E $L uvx --from 'duckdb>=1.5.5' --with numpy --with scipy python $S/qa_exposure.py $B $A $P/outputs/exposure_qa.json
# 3. 整列、開発と凍結、確認、反証、診断 (run_dev、run_confirm、falsify は出力があると止まる)
$U $S/align.py $B $A $M $P/outputs/b0_alignment.json
$L $U $S/run_dev.py $B $A $M $P/outputs
$L $U $S/run_confirm.py $B $A $M $P/outputs     # 約 30 分 (ブロックの復元抽出)
$L $U $S/falsify.py $B $A $M $P/outputs         # 約 15 分
$U $S/diagnose.py $B $A $M $P/outputs
# 4. 図
uvx --with matplotlib --with numpy python $S/plot.py $B $A $P/outputs
# テスト
uvx --with pytest --with numpy --with scipy --with scikit-learn --with shapely --with rasterio --with affine --with matplotlib python -m pytest -q $S
```

`exposure.npz` と `mesh_cells.npz`、確認のセルごとのスコア (`b3_confirm_scores.npz`) は artifacts に置き、commit しない。
