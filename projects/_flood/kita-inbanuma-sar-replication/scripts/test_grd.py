"""uvx --python 3.12 --with rasterio --with numpy --with scipy --with pyproj --with pytest pytest -q -p no:cacheprovider test_grd.py"""

# The Sentinel-1 annotation readers of 09_grd.py (floats, calibration_vectors, noise_vectors) on hand-written XML.
import importlib

import numpy as np

grd = importlib.import_module("09_grd")

CAL = """<calibration><calibrationVectorList count="2">
<calibrationVector><azimuthTime>t</azimuthTime><line>0</line><pixel count="3">0 40 80</pixel>
<sigmaNought count="3">5.0e+02 5.1e+02 5.2e+02</sigmaNought><betaNought count="3">1 1 1</betaNought></calibrationVector>
<calibrationVector><azimuthTime>t</azimuthTime><line>350</line><pixel count="2">0 80</pixel>
<sigmaNought count="2">4.9e+02 5.0e+02</sigmaNought></calibrationVector>
</calibrationVectorList></calibration>"""

NOISE = """<noise><noiseRangeVectorList count="1">
<noiseRangeVector><azimuthTime>t</azimuthTime><line>12</line><pixel count="2">0 100</pixel>
<noiseRangeLut count="2">1.5 2.5</noiseRangeLut></noiseRangeVector></noiseRangeVectorList>
<noiseAzimuthVectorList count="1"><noiseAzimuthVector><swath>IW1</swath>
<firstAzimuthLine>0</firstAzimuthLine><firstRangeSample>0</firstRangeSample>
<lastAzimuthLine>999</lastAzimuthLine><lastRangeSample>499</lastRangeSample>
<line count="2">0 999</line><noiseAzimuthLut count="2">1.0 0.9</noiseAzimuthLut></noiseAzimuthVector>
</noiseAzimuthVectorList></noise>"""


def test_floats():
    assert grd.floats("1 2.5  -3e2\n4").tolist() == [1.0, 2.5, -300.0, 4.0]


def test_calibration_vectors_reads_lines_pixels_and_sigma_nought():
    lines, pixels, sig = grd.calibration_vectors(CAL)
    assert lines == [0, 350]
    assert pixels[0].tolist() == [0, 40, 80] and sig[0].tolist() == [500.0, 510.0, 520.0]
    assert pixels[1].tolist() == [0, 80] and sig[1].tolist() == [490.0, 500.0]   # betaNought is not read


def test_noise_vectors_reads_range_and_azimuth_blocks():
    lines, pixels, lut, blocks = grd.noise_vectors(NOISE)
    assert lines == [12] and pixels[0].tolist() == [0, 100] and lut[0].tolist() == [1.5, 2.5]
    (fa, la, fr, lr, bl, blut), = blocks
    assert (fa, la, fr, lr) == (0, 999, 0, 499)
    assert np.array_equal(bl, [0, 999]) and np.array_equal(blut, [1.0, 0.9])
