# tameike-cascade-wide: 範囲の端で止まった連鎖を先まで追い、指定されていない候補を空中写真で確かめる

`tameike-cascade-breach` の連鎖の判定を、流れの計算の範囲を四方に 0.04 度広げて流し直す (初めの池は元の範囲の池だけ)。`tameike-cascade-designation` の照合をし直し、指定されていない連鎖の初めの池のうち人口の多い 9 つを、地理院の空中写真と標準地図で見る。

- 計画: [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md) (流す前にコミット、変更は末尾)
- 記録: [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)
- 報告: [report.md](report.md)
- 候補の一覧: [outputs/candidates.csv](outputs/candidates.csv)

`outputs/visual_verdicts.csv` は、図を見て手で書いた判定である (計算の出力ではない)。

## 再実行

```sh
cd projects/_tameike/tameike-cascade-wide
env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --python 3.12 --with pyflwdir --with numpy --with rasterio --with pyproj --with scipy --with duckdb --with matplotlib \
  python -u scripts/run_wide.py    # 約 8 分。足りない DEM5A のタイルを地理院から取る
python3 scripts/compare.py
systemd-run --user --scope -q -p MemoryMax=6G -p MemorySwapMax=0 -p CPUQuota=200% -- \
  uvx --python 3.12 --with duckdb==1.5.5 --with openpyxl python scripts/designation.py
systemd-run --user --scope -q -p MemoryMax=4G -p MemorySwapMax=0 -p CPUQuota=200% -- uvx --python 3.12 \
  --with duckdb==1.5.5 --with numpy --with pillow --with matplotlib --with pyproj --with shapely python scripts/visual.py
python3 ../../../.agents/skills/analysis-reporting/scripts/check_project.py .
```

`designation.py` は `tameike-cascade-designation` の読み取りと照合の関数を使い、県の一覧の原本を同じ artifacts の場所に置く (pdftotext が要る)。地理院のタイルは `artifacts/_tameike/tameike-cascade-wide/gsi/` にためる。

出典: 国土地理院 (DEM5A、空中写真、標準地図) を加工して作成。WorldPop (CC BY 4.0)。「農業用ため池一覧(令和8年3月末時点)」(農林水産省) を加工して作成。香川県、広島県、兵庫県の防災重点農業用ため池の一覧を加工して作成。気象庁ホームページ「過去の気象データ・ダウンロード」を加工して作成。
