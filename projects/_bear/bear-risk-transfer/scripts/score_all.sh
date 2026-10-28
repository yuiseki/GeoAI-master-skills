#!/usr/bin/env bash
# Score every region's table with the grid-risk-mapping skill's score_risk_map.py.
# Usage: score_all.sh REGION [REGION ...]
set -euo pipefail
S=.agents/skills/grid-risk-mapping/scripts/score_risk_map.py
A=artifacts/_bear/bear-risk-transfer
O=projects/_bear/bear-risk-transfer/outputs
for r in "$@"; do
  uvx --with numpy --with pandas --with pyarrow python $S $A/${r}_table.parquet --label label --scores AK B_pop LOCAL \
    --second B_pop=B_pop2 --block block --ks 0.01 0.05 0.10 --compare AK:B_pop AK:LOCAL LOCAL:B_pop --boot 1000 --seed 0 \
    --grid ix iy --factors 10 --prob AK LOCAL --out $O/${r}_scores.json > /dev/null
  echo "scored $r"
done
