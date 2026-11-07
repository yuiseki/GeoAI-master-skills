"""uvx --python 3.12 --with numpy --with rasterio --with torch --with torchvision --with segmentation-models-pytorch --with pytest pytest -q test_models.py"""

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
