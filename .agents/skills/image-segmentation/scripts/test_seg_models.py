"""uvx --python 3.12 --with numpy --with torch==2.14.1 --with torchvision --with segmentation-models-pytorch --with pytest pytest -q test_seg_models.py"""

import numpy as np
import pytest
import torch

from seg_models import batch_loss, build, to_groupnorm


@pytest.mark.parametrize("arch", ["fcn_resnet50", "unet_resnet34"])
def test_models_take_the_bands_give_the_classes_and_have_no_batchnorm(arch):
    net, head = build(arch, in_channels=2, classes=2)
    assert head(net(torch.randn(2, 2, 64, 64))).shape == (2, 2, 64, 64)
    assert not any(isinstance(m, torch.nn.BatchNorm2d) for m in net.modules())


def test_to_groupnorm_replaces_every_batchnorm():
    net = torch.nn.Sequential(torch.nn.Conv2d(2, 32, 3), torch.nn.BatchNorm2d(32), torch.nn.Sequential(torch.nn.BatchNorm2d(32)))
    to_groupnorm(net, 16)
    assert sum(isinstance(m, torch.nn.GroupNorm) for m in net.modules()) == 2


def test_batch_loss_in_micro_batches_equals_the_weighted_mean_of_the_whole_batch():
    torch.manual_seed(0)
    w = torch.tensor([1.0, 8.0])
    logits = torch.randn(16, 2, 8, 8)
    y = torch.randint(0, 2, (16, 8, 8))
    y[0, :2] = 255
    mean = torch.nn.CrossEntropyLoss(weight=w, ignore_index=255)(logits, y)
    parts = sum(batch_loss(logits[k:k + 8], y[k:k + 8], w, y) for k in (0, 8))
    assert parts.item() == pytest.approx(mean.item(), rel=1e-5)
