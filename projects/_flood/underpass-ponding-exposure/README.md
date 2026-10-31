# underpass-ponding-exposure

全国のアンダーパス 3,841 か所で、公開の標高タイルと OSM の道路から冠水の溜まりやすさ (道路の縦断の窪みの深さと集水の面積) を測り、その順位が標高タイルの捉え方と設定でどれだけ変わるか、東京都の浸水実績と地方整備局の箇所表の冠水実績とどの程度合うかを調べる。

- 計画 (流す前に固定): [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)
- 実行の記録: [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)
- 問いの出どころ: [proposal](../../../evals/curriculum/proposals/2026-10-30-underpass-ponding-exposure.md)、[dry-run](../../../evals/curriculum/dry-runs/2026-10-30-underpass-risk.md)

```
scripts/     コードとテスト (dem.py、roadprofile.py が規則、test_*.py がそのテスト)
outputs/     報告が引く結果 (JSON) と図 (PNG)
  tokyo23_underpass_a31a_osm_dem.png  東京23区の登録地点・推定候補・洪水想定・道路・標高の探索図
artifacts/_flood/underpass-ponding-exposure/
  raw/          版を固定した入力。planet_osm_line.parquet は手で落とす (下)、roads.parquet はその切り出し
  dem/          標高タイル (dem5a/15、dem/14)。404 は .404 の空のファイル。fetch_log.json
  measures.parquet   箇所ごとの対応、深さ、集水の面積 (派生物、観測ではない)
  profiles.parquet   縦断の標本と、選んだ道路の形
```

得点は標高から測った物理的な溜まりやすさの順位で、冠水の確率や事故の起こりやすさではない。

## 再現

版: Python 3.12、DuckDB 1.5.5 以上、numpy、shapely、pandas、pyarrow、matplotlib (uvx が取る版)。

```sh
cd projects/_flood/underpass-ponding-exposure
L="systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% --"
U="uvx --from duckdb>=1.5.5 --with numpy --with shapely --with pandas --with pyarrow --with matplotlib"
$U pytest -q scripts                     # 規則のテスト (pytest は --with pytest で足す)
$U python scripts/01_fetch.py             # 小さな入力 (版を固定)
# OSM の線 (1.85 GB、sha256 e13a37e049ecb3590657e8170b7246a00863809946d4672cd9733bfbc86ee003)
curl -L -o ../../../artifacts/_flood/underpass-ponding-exposure/raw/planet_osm_line.parquet \
  https://huggingface.co/datasets/yuiseki/osm-japan-src-2026-08/resolve/9a9b4a77e89e28a66bf15781644a16b63501f622/parquet/planet_osm_line.parquet
$L $U python scripts/03_roads.py          # 点から 400 m の道路の切り出し (約 1 分)
$U python -u scripts/02_dem.py            # 標高タイル (約 2 時間、1 枚ずつ 0.3 秒おき。取れた分は飛ばす)
$L $U python scripts/04_profile.py        # 対応、縦断、深さ、集水
$U python scripts/06_check_fig.py         # 東京都の 10 か所の目視用の図
$U python scripts/05_blocks.py            # B1〜B4 と頑健性 → outputs/blocks.json
# A31a・凍結OSM・DEM10Bを重ねた探索図 (別途 rasterio、pyproj が必要)
uvx --from 'duckdb>=1.5.5' --with numpy --with matplotlib --with shapely --with pyproj --with rasterio \
  python scripts/08_map_tokyo23_flood_context.py
```

この図では、A31a の想定最大規模を25 m格子に描き、河川間で重なる箇所は公表ランクの最大値を表示用に採用する。OSMの橋タグ付き道路と下位レイヤーの道路が交差し、その交差部が両側アプローチよりDEM5Aで2 m以上低い地点を、未検証の推定候補としてひし形で示す。東京都の浸水実績図の点は道路冠水記録ではなく、DEMはアンダーパスの路面高を保証しない。推定候補は公式台帳や現地で確認しておらず、この重ね合わせは危険度の検証結果ではない。

標高タイルには版の番号が無い。取得した日は dem/fetch_log.json にある。

## 出典

OpenStreetMap (ODbL 1.0)、国土地理院の標高タイル (加工して作成)、国土交通省のアンダーパス箇所マップと地方整備局の道路防災情報Webマップ (加工して作成)、東京都の浸水実績図、気象庁の過去の気象データ (加工して作成)。各データの版はスクリプトの冒頭にある。
