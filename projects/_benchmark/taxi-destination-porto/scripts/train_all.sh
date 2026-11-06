#!/bin/sh
# The fixed budget of EXPERIMENT_TRACKER.md R003, one run after another on 4 cores.
set -e
cd "$(dirname "$0")/.."
RUN="systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- nice -n 10 uvx -q --python 3.12 --with numpy --with pandas --with scikit-learn --with torch==2.12.0 --index https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match python -u scripts/run.py"
$RUN train --variant rand --model mlp --steps 300000 --every 10000 --seed 1
$RUN train --variant rand --model noemb --steps 300000 --every 10000 --seed 1
$RUN cluster --variant late
$RUN train --variant late --model mlp --steps 300000 --every 10000 --seed 1
echo ALL DONE
