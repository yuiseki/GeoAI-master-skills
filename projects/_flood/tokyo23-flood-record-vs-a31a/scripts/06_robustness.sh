#!/usr/bin/env bash
# Robustness runs of B1 and B2 (EXPERIMENT_PLAN.md, 頑健性). Each writes outputs/rob_<name>.json.
set -euo pipefail
cd "$(dirname "$0")/.."
run() { name=$1; shift
  systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
    uvx --from 'duckdb>=1.5.5' --with numpy --with scikit-learn --with pyarrow python -u scripts/03_static.py "$@" --out outputs/rob_$name.json > outputs/rob_$name.log 2>&1
  echo "done $name"; }
run label_centre --label centre
run a31a_planned --a31a planned
run a31a_max_0.5m --a31a maximum_0.5
run block_5km --block 5000
run naisui --reason naisui
run issui --reason issui
run split_1990 --train 1974 1989 --test 1990 2004
run grid_250 --grid grid_250
run grid_500 --grid grid_500
run grid_250_off125 --grid grid_250_off125
echo ALL ROBUSTNESS DONE
