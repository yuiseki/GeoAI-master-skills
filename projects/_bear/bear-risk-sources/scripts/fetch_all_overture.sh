#!/usr/bin/env bash
# Fetch Overture roads, water and buildings for each region box in BOXES (lines: name minlon minlat maxlon maxlat).
set -uo pipefail
BOXES=$1
O=artifacts/_bear/bear-risk-sources/overture
while read -r name x0 y0 x1 y1; do
  for tt in "transportation segment" "base water" "buildings building"; do
    set -- $tt
    out=$O/${name}_$2.parquet
    [ -s "$out" ] && { echo "skip $out"; continue; }
    uvx --from 'duckdb>=1.5.5' python -u projects/_bear/bear-risk-sources/scripts/fetch_overture.py $1 $2 $x0 $y0 $x1 $y1 $out 2>&1 | grep -v '▕' || echo "FAILED $name $2"
  done
done < "$BOXES"
echo ALL_DONE
