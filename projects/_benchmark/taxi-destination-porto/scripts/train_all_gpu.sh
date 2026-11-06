#!/bin/sh
# The same fixed budget as train_all.sh (EXPERIMENT_TRACKER.md R003), on one GPU: GPU=<index> scripts/train_all_gpu.sh
set -e
cd "$(dirname "$0")/.."
RUN="systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- env CUDA_VISIBLE_DEVICES=${GPU:?set GPU} nice -n 10 uvx -q --python 3.12 --with numpy --with pandas --with scikit-learn --with torch==2.12.0 python -u scripts/run.py"
$RUN train --variant rand --model mlp --steps 300000 --every 10000 --seed 1 --device cuda
$RUN train --variant rand --model noemb --steps 300000 --every 10000 --seed 1 --device cuda
$RUN cluster --variant late
$RUN train --variant late --model mlp --steps 300000 --every 10000 --seed 1 --device cuda
echo ALL DONE
