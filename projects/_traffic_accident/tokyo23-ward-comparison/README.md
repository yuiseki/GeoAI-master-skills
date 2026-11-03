# tokyo23-ward-comparison

東京 23 区の 2019〜2025 年の人身事故を、区ごとに同じ式で数え直して比べた記述の分析です。量 (人口、道路、面積あたり)、推移、構成、場所の集まり方を並べ、区の型と区ごとの特徴を言葉にしました。結論は [report.md](report.md)、計画は [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)、記録は [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md) にあります。区ごとの詳しい報告は `../<区>-accident-trends-by-role/` です。

事故の区分 (生活道路、歩行者、自転車など) と地点の選び方は、台東区の型 (`../taito-accident-trends-by-role/scripts/analyze.py`) の関数を読み込んで使います。そのため、区ごとの分析と同じ型の版で作った区の数字は、区ごとの報告と一致します。大きな中間ファイルは `artifacts/_traffic_accident/tokyo23-ward-comparison/` に置き、Git に入れません。

```sh
env -u PYTHONPATH uvx --from 'duckdb>=1.5.5' python projects/_traffic_accident/tokyo23-ward-comparison/scripts/prepare.py
env -u PYTHONPATH uvx --from 'duckdb>=1.5.5' --with numpy python projects/_traffic_accident/tokyo23-ward-comparison/scripts/analyze.py
F="share_ped share_bike share_old_ped share_young_pb share_strict share_night share_intersection share_bike_single share_business_car_A share_truck_A share_weekend share_expressway"
A=artifacts/_traffic_accident/tokyo23-ward-comparison
O=projects/_traffic_accident/tokyo23-ward-comparison/outputs
C=.agents/skills/clustering-analysis/scripts/cluster_units.py
for m in kmeans ward; do
  env -u PYTHONPATH uvx --with duckdb --with scikit-learn --with pyarrow --with scipy python $C $A/features.parquet code $F \
    --method $m --k 2,3,4,5,6 --compare-with known_division --lon lon --lat lat --neighbors 4 --runs 50 \
    --labels-out $A/labels-$m.parquet > $O/clusters-$m.txt
done
env -u PYTHONPATH uvx --with duckdb --with scikit-learn --with pyarrow --with scipy python $C $A/features.parquet code $F \
  --method dpmm --max-components 10 --covariance-scale 0.3,1,3,10,30 > $O/clusters-dpmm.txt
env -u PYTHONPATH uvx --with duckdb --with scikit-learn --with numpy python projects/_traffic_accident/tokyo23-ward-comparison/scripts/clusters.py
python3 projects/_traffic_accident/tokyo23-ward-comparison/scripts/summarize.py
python3 projects/_traffic_accident/tokyo23-ward-comparison/scripts/ward_table.py
env -u PYTHONPATH uvx --with numpy --with matplotlib python projects/_traffic_accident/tokyo23-ward-comparison/scripts/plot.py
env -u PYTHONPATH uvx --from 'duckdb>=1.5.5' --with numpy --with shapely --with matplotlib python projects/_traffic_accident/tokyo23-ward-comparison/scripts/maps.py
```

`env -u PYTHONPATH` は、環境の PYTHONPATH (anaconda) の numpy や pandas が uvx の環境に混ざらないようにするため。

テストは `env -u PYTHONPATH uvx --from pytest --with 'duckdb>=1.5.5' --with numpy --with scikit-learn pytest -p no:cacheprovider projects/_traffic_accident/tokyo23-ward-comparison/scripts/test_analyze.py`。
