#!/usr/bin/env bash
# Build every alternative feature file that is not there yet and whose source data are present.
set -uo pipefail
E="env -u GDAL_DATA -u GDAL_DRIVER_PATH -u PROJ_DATA -u PROJ_NETWORK"
P=projects/_bear/bear-risk-sources/scripts; S=artifacts/_bear/bear-risk-sources; O=$S/overture
declare -A ART=([akita]=artifacts/_bear/akita-bear-risk-grid-100m [gifu]=artifacts/_bear/bear-risk-transfer/gifu [kyoto]=artifacts/_bear/bear-risk-transfer/kyoto [ishikawa]=artifacts/_bear/bear-risk-transfer/ishikawa)
run() { $E systemd-run --user --scope -q -p MemoryMax=20G -p MemorySwapMax=0 -p CPUQuota=400% -- uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with shapely --with pyproj --with pandas python $P/alt_features.py "$@" 2>&1 | grep -v "▕\|Installed"; }
for r in akita gifu kyoto ishikawa; do
  [ -s $S/$r/river_ksj.npz ] || run river ksj $r ${ART[$r]} $S/ksj $S/$r/river_ksj.npz
  [ -s $S/$r/road_ksj.npz ] || run road ksj $r ${ART[$r]} $S/ksj $S/$r/road_ksj.npz
  [ -s $S/$r/road_ovt.npz ] || { [ -s $O/${r}_segment.parquet ] && run road ovt $r ${ART[$r]} $O $S/$r/road_ovt.npz; }
  [ -s $S/$r/river_ovt.npz ] || { [ -s $O/${r}_water.parquet ] && run river ovt $r ${ART[$r]} $O $S/$r/river_ovt.npz; }
  [ -s $S/$r/bldg_ovt.npz ] || { [ -s $O/${r}_building.parquet ] && run bldg ovt $r ${ART[$r]} $O $S/$r/bldg_ovt.npz; }
done
ls $S/{akita,gifu,kyoto,ishikawa}/*.npz
