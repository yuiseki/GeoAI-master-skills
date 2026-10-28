# beech-masting-triggers

東北 5 県のブナの結実の豊凶 (1989〜2026 年度) を、前の年までの気象と衛星の値で先に言い当てられるか、どの手がかりが引き金かを調べる。計画は [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)、実行の記録は [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)。

## 置き場所

- `scripts/`: コードとテスト。
- `outputs/`: 報告が引く小さな表。`tohoku_beech_index.csv` は東北森林管理局のプレスリリースの表を読み取ったもの (出典: 東北森林管理局ウェブサイト https://www.rinya.maff.go.jp/tohoku/sidou/buna.html を加工して作成。PDL1.0)。
- `artifacts/_bear/beech-masting-triggers/`: 取った PDF、気象と衛星の地点の値。

## 再現

リポジトリの直下から。

```sh
# 1. 豊凶指数の表 (PDF を取り、読み取り、2 つのリリースと箇所数で照合する)
uvx --with pdfplumber python projects/_bear/beech-masting-triggers/scripts/tohoku_index.py \
  artifacts/_bear/beech-masting-triggers/raw projects/_bear/beech-masting-triggers/outputs

# 2. Dryad の地点と、作り直した指数の照合
uvx --from 'duckdb>=1.5.5' --with numpy python projects/_bear/beech-masting-triggers/scripts/dryad_sites.py \
  projects/_bear/beech-masting-triggers/outputs

# 3. 気象の手がかり (AgERA5 を地点のセルで取る)
uvx --from 'duckdb>=1.5.5' --with pandas --with pyarrow python projects/_bear/beech-masting-triggers/scripts/weather.py \
  projects/_bear/beech-masting-triggers/outputs artifacts/_bear/beech-masting-triggers

# 4. B1: 開発期間で選んで凍結 (出力が既にあれば止まる)
uvx --with pandas python projects/_bear/beech-masting-triggers/scripts/select_b1.py projects/_bear/beech-masting-triggers/outputs

# 5. B2、B3: 確認期間で 1 回。B4: 花ができる段階
uvx --with pandas --with scipy python projects/_bear/beech-masting-triggers/scripts/confirm_b2.py projects/_bear/beech-masting-triggers/outputs
uvx --with pandas --with scipy python projects/_bear/beech-masting-triggers/scripts/stage_b4.py projects/_bear/beech-masting-triggers/outputs

# 6. 衛星 (MODIS、Planetary Computer。数千の COG を読むので 10 分ほど) と B5
env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
  uvx --with rasterio --with pystac-client --with planetary-computer --with pandas --with pyarrow python \
  projects/_bear/beech-masting-triggers/scripts/satellite.py projects/_bear/beech-masting-triggers/outputs artifacts/_bear/beech-masting-triggers
uvx --with pandas --with scipy python projects/_bear/beech-masting-triggers/scripts/satellite_b5.py projects/_bear/beech-masting-triggers/outputs

# 7. 図
uvx --with matplotlib --with pandas python projects/_bear/beech-masting-triggers/scripts/plot.py projects/_bear/beech-masting-triggers/outputs

# テスト
cd projects/_bear/beech-masting-triggers/scripts && uvx --with pdfplumber --with pandas --with scipy --with matplotlib --with pytest python -m pytest -q
```

確認の段 (4〜6 の B2〜B5) は、計画どおり 1 回だけ流す。スクリプトは出力が既にあると止まる。やり直すときは、出力を消す理由を記録に書いてから消す。

- MODIS の 2025 年 7〜8 月の地表面温度は、2026-10-28 の時点で Planetary Computer に無い。
- MODIS の item には同じ区画と年の再処理の版が複数あり、最後の版だけを使う。`platform` の欠けた item があるので、Terra は ID の頭 `MOD` で選ぶ。
