# tokyo23-fatal-share-road-anomaly

[課題 hard-49 の報告](report.md)。2019〜2025 年の東京 23 区の人身事故で、道路形状、車道幅員、中央分離帯が同じ事故から期待されるより死亡事故の多い 500 m メッシュを探し、事故の総件数の順位と比べる。データに重傷の区分が無いので、重大事故は 24 時間以内の死亡事故。計画は [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)、実行の記録は [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)。

課題が指定した 4 つの固定版のデータセットだけを、Hugging Face から読む。大きな生成物は `artifacts/_traffic_accident/tokyo23-fatal-share-road-anomaly/` に置き、Git に入れない。

リポジトリの根から、順に流す。実データを読むので、メモリと CPU に上限を掛ける。

```sh
L="systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% --"
W="uvx --from duckdb>=1.5.5 --with numpy --with scipy --with pandas --with pyarrow --with shapely --with matplotlib --with scikit-learn python -u"
cd projects/_traffic_accident/tokyo23-fatal-share-road-anomaly
$L $W scripts/01_extract.py   # 23 区の事故を取り出す (outputs/extract.json)
$L $W scripts/02_anomaly.py   # B2〜B6 (summary.json、meshes_main.csv、variants.csv など)
$L $W scripts/03_explore.py   # 探索: 層を足した検定、1 km の持続、人口、OSM の道路の名前
$L $W scripts/04_map.py       # 地図 (outputs/map_anomaly.png)
$L $W scripts/05_moran.py     # 残差の Moran's I (outputs/moran.txt)
```

テスト:

```sh
cd projects/_traffic_accident/tokyo23-fatal-share-road-anomaly/scripts
uvx --with numpy --with scipy --with pytest pytest -q test_fatalshare.py
```

| スクリプト | 中身 |
|---|---|
| `fatalshare.py` | Poisson 二項分布の上側確率、メッシュのコード、層のまとめ、自分を除いた割合、BH、ばらつきの統計量、層の中の並べ替え |
| `01_extract.py` | 本票 7 ファイルから 23 区の事故を取り出し、行を数える |
| `02_anomaly.py` | 計画の B2〜B6 |
| `03_explore.py` | 結果を見た後の探索 (記録の D2) |
| `04_map.py` | analysis-visualize の classify_map.py で地図を描く |
| `05_moran.py` | spatial-autocorrelation の spatial_autocorrelation.py で残差の Moran's I |
