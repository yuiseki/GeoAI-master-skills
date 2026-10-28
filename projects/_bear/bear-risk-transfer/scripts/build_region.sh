#!/usr/bin/env bash
# Build the 100 m grid and the static features of one region, with the same definitions as for Akita.
# Usage: build_region.sh NAME PREF CRS [CODE5]
set -euo pipefail
NAME=$1; PREF=$2; CRS=$3; CODE5=${4:-}
T=projects/_bear/bear-risk-transfer/scripts
OUT=artifacts/_bear/bear-risk-transfer/$NAME
mkdir -p "$OUT"
E="env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK"
L="systemd-run --user --scope -q -p MemoryMax=20G -p MemorySwapMax=0 -p CPUQuota=400% --"
EXTRA=""; [ -n "$CODE5" ] && EXTRA="--code5 $CODE5"
echo "== $NAME grid"; $E uvx --from 'duckdb>=1.5.5' --with numpy --with shapely --with pyproj --with pandas --with pyarrow python -u $T/build_grid.py "$OUT" --pref "$PREF" --crs "$CRS" $EXTRA
echo "== $NAME worldcover"; $E $L uvx --with rasterio --with numpy --with pyproj python -u $T/feat_worldcover.py "$OUT"
echo "== $NAME dem"; $E $L uvx --with numpy --with pyproj python -u $T/feat_dem.py "$OUT" "$OUT/raw/gsi_dem12"
echo "== $NAME worldpop"; $E uvx --from 'duckdb>=1.5.5' --with rasterio --with numpy --with pyproj python -u $T/feat_worldpop.py "$OUT" "$PREF"
echo "== $NAME osm"; $E $L uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with shapely --with pyproj python -u $T/feat_osm.py "$OUT"
echo "== $NAME done"
