#!/bin/bash
# bbox covers all 23 wards (checked in 01_regions.py output); points outside wards are dropped later in the join.
P=/work/.agents/skills/poi-insights/scripts
A=/work/artifacts/tokyo23-convenience-stores
./scripts/run.sh --from 'duckdb>=1.5.5' python $P/poi_extract.py \
 's3://overturemaps-us-west-2/release/2026-10-21.0/theme=places/type=place/*.parquet' $A/cvs_all.parquet \
 --bbox 139.55 35.50 139.93 35.84 --category convenience_store
