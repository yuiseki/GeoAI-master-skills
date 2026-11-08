#!/bin/sh
# R005 and R008 of EXPERIMENT_TRACKER.md: DCRNN (K = 2), then the no-graph model (K = 0), 60 epochs, one GPU.
# SEED picks the seed (default 1). One run takes 2.5-3 GB of GPU memory; two side by side ran out of memory
# on a GPU with 5.6 GB free, so they run one after the other.
cd "$(dirname "$0")/.."
S=${SEED:-1}
RUN="systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- env CUDA_VISIBLE_DEVICES=${GPU:?set GPU} nice -n 10 uvx -q --python 3.12 --with numpy --with h5py --with torch==2.14.1 python -u scripts/run.py"
$RUN train --k 2 --seed $S --epochs 60 > ~/logs/pems_k2_s$S.log 2>&1
$RUN train --k 0 --seed $S --epochs 60 > ~/logs/pems_k0_s$S.log 2>&1
echo ALL DONE
