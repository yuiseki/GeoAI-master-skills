"""Models and the loss for binary segmentation of image chips, tested in test_seg_models.py.

  build(arch, in_channels, classes)   fcn_resnet50 (torchvision) or unet_resnet34 (segmentation-models-pytorch), no
                                      pretrained weights, first layer for in_channels, every BatchNorm as GroupNorm(16).
                                      Returns (net, head): head(net(x)) is the logits (batch, classes, H, W)
  to_groupnorm(module, groups)        BatchNorm2d -> GroupNorm in place. With a batch of 16 small crops, the batch
                                      statistics are noisy, and GroupNorm makes the result independent of how the
                                      batch is split across micro-batches
  batch_loss(logits, y, w, y_all)     weighted cross entropy of one micro-batch, divided by the total weight of the
                                      whole batch y_all: summing it over the micro-batches gives the weighted mean of
                                      the whole batch at once (gradient accumulation without changing the loss)

GPU note: with torch 2.12.0 (bundled cuDNN 9.20) on a machine with a system cuDNN 9.27, cuDNN loaded a sublibrary it
lacks (libcudnn_engines_tensor_ir) from the system and the first convolution failed with
CUDNN_STATUS_SUBLIBRARY_VERSION_MISMATCH. torch 2.14.1 (bundled cuDNN 9.24) has every sublibrary.
"""

import torch
from torch import nn

IGNORE = 255


def to_groupnorm(module, groups=16):
    for name, child in module.named_children():
        if isinstance(child, nn.BatchNorm2d):
            setattr(module, name, nn.GroupNorm(groups, child.num_features, eps=child.eps, affine=child.affine))
        else:
            to_groupnorm(child, groups)
    return module


def build(arch, in_channels=2, classes=2):
    if arch == "fcn_resnet50":
        from torchvision.models.segmentation import fcn_resnet50
        net = fcn_resnet50(weights=None, weights_backbone=None, num_classes=classes)
        net.backbone.conv1 = nn.Conv2d(in_channels, 64, kernel_size=7, stride=2, padding=3, bias=False)
        return to_groupnorm(net), lambda o: o["out"]
    if arch == "unet_resnet34":
        import segmentation_models_pytorch as smp
        net = smp.Unet("resnet34", encoder_weights=None, in_channels=in_channels, classes=classes)
        return to_groupnorm(net), lambda o: o
    raise ValueError(arch)


def batch_loss(logits, y, w, y_all):
    denom = sum(float((y_all == k).sum()) * float(w[k]) for k in range(len(w)))
    return nn.functional.cross_entropy(logits, y, weight=w, ignore_index=IGNORE, reduction="sum") / denom
