#!/bin/sh
# B1 and B2 of EXPERIMENT_PLAN.md: FCN and U-Net, seeds 1-3, on one GPU: GPU=<index> [ACCUM=1] scripts/train_all.sh
set -e
cd "$(dirname "$0")/.."
# torch 2.14.1: its bundled cuDNN 9.24 has every sublibrary. With 2.12.0 (cuDNN 9.20) the missing
# libcudnn_engines_tensor_ir was taken from the system cuDNN 9.27 and the first convolution failed
# (CUDNN_STATUS_SUBLIBRARY_VERSION_MISMATCH).
RUN="systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- env CUDA_VISIBLE_DEVICES=${GPU:?set GPU} nice -n 10 uv run -q --no-project --python 3.12 --with numpy --with rasterio --with torch==2.14.1 --with torchvision --with segmentation-models-pytorch python -u scripts/run.py"
for seed in 1 2 3; do
  for model in fcn unet; do
    # FCN at 16 x 256 x 256 peaks at 4.9 GB: two micro-batches of 8 (the loss is the same, see run.py)
    if [ $model = fcn ]; then acc=2; else acc=1; fi
    $RUN train --model $model --seed $seed --accum $acc --device cuda
  done
done
echo ALL DONE
