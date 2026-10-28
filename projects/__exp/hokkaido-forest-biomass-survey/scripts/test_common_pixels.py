import numpy as np

from common_pixels import common_block


def test_common_block_excludes_year_specific_nodata():
    old = np.array([[100, 200], [-9999, 300]], dtype=np.int16)
    new = np.array([[80, -9999], [100, 250]], dtype=np.int16)
    result = common_block(old, new)
    assert result["common_pixels"] == 2
    assert result["old_mean"] == 20.0
    assert result["new_mean"] == 16.5
    assert result["drop"] == 3.5
    assert result["mask_mismatch_pixels"] == 2


def test_common_block_with_no_common_pixels_does_not_make_zero():
    old = np.array([[-9999, 10]], dtype=np.int16)
    new = np.array([[10, -9999]], dtype=np.int16)
    result = common_block(old, new)
    assert result["common_pixels"] == 0
    assert result["drop"] is None
