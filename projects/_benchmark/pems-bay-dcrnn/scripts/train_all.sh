#!/bin/sh
# R003 of EXPERIMENT_TRACKER.md: DCRNN (K = 2) and the no-graph model (K = 0), seed 1, 60 epochs, side by side on one GPU.
cd "$(dirname "$0")/.."
RUN="systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=200% -- env CUDA_VISIBLE_DEVICES=${GPU:?set GPU} nice -n 10 uvx -q --python 3.12 --with numpy --with h5py --with torch==2.14.1 python -u scripts/run.py"
$RUN train --k 2 --seed 1 --epochs 60 > ~/logs/pems_k2.log 2>&1 &
$RUN train --k 0 --seed 1 --epochs 60 > ~/logs/pems_k0.log 2>&1 &
wait
echo ALL DONE
