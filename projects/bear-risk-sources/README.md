# bear-risk-sources

100 m セルのクマ出没通報のリスクのモデルを、学習に使っていない県へ当てはめるとき、建物、道路、川のデータの出どころ (OSM、Overture、国土数値情報、無し)、気候の平年値、学習の地域の数 (1〜3) で当たりがどう変わるかを比べる。

- 報告: [report.md](report.md)、計画: [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)、記録: [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)
- 前提: `projects/akita-bear-risk-grid-100m/` と `projects/bear-risk-transfer/` の格子、特徴量、通報の数 (`artifacts/` の下)

## 再現

```sh
cd <リポジトリの直下>
P=projects/bear-risk-sources/scripts; S=artifacts/bear-risk-sources
# 1. 取得 (Overture は S3、国土数値情報は配布元。1 ファイルずつ間を空ける)
$P/fetch_all_overture.sh $S/boxes.txt
python3 $P/fetch_ksj.py $S/ksj_files_shp.csv $S/ksj
# 2. 差し替えの特徴量と平年値
$P/build_alt_all.sh
for r in akita gifu kyoto ishikawa; do uvx --with numpy --with pandas --with pyarrow python $P/g02_features.py $S/ksj <その地域の artifacts> $S/$r/g02.npz; done
# 3. 行列 (設定ごとに 14 の学習の組。全セルで学習するので、1 設定 30 分ほど)
uvx --with numpy --with scipy --with scikit-learn --with pandas python $P/run_matrix.py projects/bear-risk-sources/outputs/matrix_a.csv base bldg_none
# (同じように matrix_b〜f。設定の名前は run_matrix.py の VARIANTS)
uvx --with pandas --with matplotlib python $P/summarize.py projects/bear-risk-sources/outputs projects/bear-risk-sources/outputs/matrix_*.csv
# 地図 (岐阜と京都。予測は artifacts の map_scores.npz に残し、2 回目からは学習しない)
for t in gifu kyoto; do uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with scikit-learn --with pandas --with pyarrow --with matplotlib --with shapely --with pyproj python $P/map_compare.py $t projects/bear-risk-sources/outputs/map-$t-base-vs-clim.png; done
# テスト
uvx --with numpy --with scipy --with scikit-learn --with pandas --with pytest python -m pytest -q $P
```

この母艦では、anaconda の GDAL と PROJ の環境変数を外し、重い実行にメモリと CPU の上限を付けた。国土数値情報の W05 と G02 は再配布が不可なので、原本は `artifacts/` に置き、ここには集計した結果だけを置く。
