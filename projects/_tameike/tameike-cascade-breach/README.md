# tameike-cascade-breach: 上のため池の決壊が、下のため池の決壊を次々に起こしうる連鎖

`tameike-cascade-pairs` の 3 つの範囲 (香川、福山、淡路) で、ある池の決壊の流量 (Froehlich の式) と、下の池の余水吐の能力 (設計洪水流量を合理式で)、下の池にたまる水の水位の上がりを比べて、2 つ以上の池が次々にあふれる連鎖と、その流れの近くの人口を数える。

- 計画: [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md) (流す前にコミット、変更は末尾)
- 記録: [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)
- 報告: [report.md](report.md)

## 再実行

```sh
cd projects/_tameike/tameike-cascade-breach
systemd-run --user --scope -q -p MemoryMax=2G -p MemorySwapMax=0 -- uvx --python 3.12 --with numpy --with pytest pytest -q scripts/test_breach.py
python3 scripts/fetch_rain.py      # 気象庁の 6 観測所 (artifacts/ に CSV を保存。サービスは更新されうる)
env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  uvx --python 3.12 --with pyflwdir --with numpy --with rasterio --with pyproj --with scipy --with duckdb --with matplotlib \
  python scripts/run_breach.py     # 約 4.5 分、最大メモリ約 1.1 GB。DEM5A のタイルは tameike-cascade-pairs のものを使う
python3 scripts/chain_stats.py
python3 ../../../.agents/skills/analysis-reporting/scripts/check_project.py .
```

出典: 気象庁ホームページ「過去の気象データ・ダウンロード」を加工して作成。国土地理院 DEM5A を加工して作成。WorldPop (CC BY 4.0)。
