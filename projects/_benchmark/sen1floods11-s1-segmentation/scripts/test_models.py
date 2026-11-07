"""uv run --no-project --python 3.12 --with numpy --with rasterio --with torch==2.14.1 --with torchvision --with segmentation-models-pytorch --with pytest pytest -q test_models.py"""

import pytest
import torch

from run import build


@pytest.mark.parametrize("model", ["fcn", "unet"])
def test_models_take_two_bands_give_two_classes_and_have_no_batchnorm(model):
    net, head = build(model)
    out = head(net(torch.randn(2, 2, 256, 256)))
    assert out.shape == (2, 2, 256, 256)
    assert not any(isinstance(m, torch.nn.BatchNorm2d) for m in net.modules())
    assert any(isinstance(m, torch.nn.GroupNorm) for m in net.modules())


def test_summed_loss_over_the_batch_weight_equals_the_weighted_mean():
    torch.manual_seed(0)
    w = torch.tensor([1.0, 8.0])
    logits = torch.randn(16, 2, 8, 8)
    y = torch.randint(0, 2, (16, 8, 8))
    y[0, :2] = 255
    mean = torch.nn.CrossEntropyLoss(weight=w, ignore_index=255)(logits, y)
    crit = torch.nn.CrossEntropyLoss(weight=w, ignore_index=255, reduction="sum")
    denom = float((y == 0).sum() * 1.0 + (y == 1).sum() * 8.0)
    parts = sum(crit(logits[k:k + 8], y[k:k + 8]) / denom for k in (0, 8))
    assert parts.item() == pytest.approx(mean.item(), rel=1e-5)
