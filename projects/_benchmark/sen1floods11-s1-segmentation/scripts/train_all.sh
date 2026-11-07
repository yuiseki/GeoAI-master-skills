#!/bin/sh
# B1 and B2 of EXPERIMENT_PLAN.md: FCN and U-Net, seeds 1-3, on one GPU: GPU=<index> [ACCUM=1] scripts/train_all.sh
set -e
cd "$(dirname "$0")/.."
RUN="systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- env CUDA_VISIBLE_DEVICES=${GPU:?set GPU} nice -n 10 uvx -q --python 3.12 --with numpy --with rasterio --with torch==2.12.0 --with torchvision --with segmentation-models-pytorch python -u scripts/run.py"
for seed in 1 2 3; do
  for model in fcn unet; do
    $RUN train --model $model --seed $seed --accum ${ACCUM:-1} --device cuda
  done
done
echo ALL DONE
