# japan-climate-analysis

日本の月別気候データから地域差、異常月、予測と予測区間を検討し、気候適応計画に使う際の限界を整理した既存事例です。

- [整理したレポート](report.md)
- [全国の気候型と基準期間を論じた論文](paper.md)
- 移植元: [`study-geoai-algo-py/case-studies/006-japan-climate`](https://github.com/yuiseki/study-geoai-algo-py/tree/6880b32c097a7c65a6bd72a38682ce1dce1c9a2b/case-studies/006-japan-climate)
- 状態: 全国のPCAと気候型分析は固定した元コードで2026-10-25に再実行しました。東京・関東の予測分析は再実行していません。入力COGのファイルハッシュは未保存です。

全国分析の再実行ログは `outputs/national-pca.log` と `outputs/national-types.log`、図は `outputs/pc-maps.png` と `outputs/types.png` です。`scripts/reproduce_national.py` は元コードのcommitを検査し、図とログをこのproject内に保存します。元コードを指定場所に置くか、`--source` で固定commitのcloneを指定してください。

```sh
uvx --with duckdb --with numpy --with pandas --with pyarrow --with rasterio \
  --with scikit-learn --with scipy --with matplotlib \
  python projects/japan-climate-analysis/scripts/reproduce_national.py
```

図は `outputs/source-values.csv` の値から再生成できます。

```sh
uv run --with matplotlib python scripts/plot.py
```
