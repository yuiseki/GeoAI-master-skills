# bear-synthesis

`projects/_bear/` の 9 プロジェクトの総括。何が予測でき、何ができなかったかを [report.md](report.md) にまとめた。新しくデータは読まず、各プロジェクトの出力を並べ直している。

図 2 (B_env に足したものの差) は各プロジェクトの JSON から差と区間を読んで描いた。図 8 と図 10 (試行錯誤の地図) は、保存済みの B_env と固定版の通報から描いた。コマンドはリポジトリの直下から流す。

```sh
uvx --with matplotlib --with pandas python projects/_bear/bear-synthesis/scripts/added_predictors.py \
  projects/_bear projects/_bear/bear-synthesis/outputs
env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK \
  uvx --from 'duckdb>=1.5.5' --with numpy==2.5.4 --with scipy --with pandas --with pyarrow --with shapely \
  --with matplotlib --with pyproj python projects/_bear/bear-synthesis/scripts/trial_maps.py \
  artifacts/_bear/akita-bear-risk-grid-100m projects/_bear/bear-synthesis/outputs
uvx --with pytest --with pandas python -m pytest -q projects/_bear/bear-synthesis/scripts
```
