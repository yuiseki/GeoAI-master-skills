"""uvx --python 3.12 --with pyflwdir --with numpy --with rasterio --with pyproj --with scipy --with 'duckdb>=1.5.5' --with openpyxl --with pytest pytest -q -p no:cacheprovider test_run_wide.py"""

# widened of run_wide.py; rows_of and lists of designation.py (downloads and the PDF readers replaced by stand-ins).
import os

for _k in ("GDAL_DATA", "PROJ_LIB", "PROJ_DATA"):    # an anaconda proj.db breaks rasterio's CRS (see the scripts' env -u)
    os.environ.pop(_k, None)

import designation as dg  # noqa: E402
import run_wide as rw  # noqa: E402


def test_widened_pads_every_side():
    assert rw.widened((133.78, 34.13, 133.94, 34.27)) == (133.74, 34.09, 133.98, 34.31)
    assert rw.widened((0.0, 0.0, 1.0, 1.0), pad=0.5) == (-0.5, -0.5, 1.5, 1.5)
    assert rw.widened(rw.BOXES["awaji"]) == (134.74, 34.36, 134.98, 34.58)


def test_rows_of():
    assert dg.rows_of("12|7|") == {7, 12} and dg.rows_of("") == set()


def test_lists_reads_every_kagawa_file_and_the_whole_other_lists(tmp_path, monkeypatch):
    def get(url):
        p = tmp_path / url.rsplit("/", 1)[1]
        p.write_bytes(url.encode())
        return p

    monkeypatch.setattr(dg, "get", get)
    monkeypatch.setattr(dg, "kagawa", lambda path, m: [dict(box="kagawa", municipality=m, no=1)])
    seen = {}

    def hiro(path, munis):
        seen["hiroshima"] = munis
        return [dict(box="fukuyama", municipality="三原市", no="340000001")]

    def hyo(path, munis):
        seen["hyogo"] = munis
        return [dict(box="awaji", municipality="南あわじ市", no="A1")]

    monkeypatch.setattr(dg, "hiroshima", hiro)
    monkeypatch.setattr(dg, "hyogo", hyo)
    sources = []
    rows = dg.lists(sources)
    assert len(rows) == len(dg.KAGAWA_ALL) + 2 and len(sources) == len(dg.KAGAWA_ALL) + 2
    assert {r["pref"] for r in rows if r["box"] == "kagawa"} == {"香川県"}
    assert [r["pref"] for r in rows[-2:]] == ["広島県", "兵庫県"]
    assert seen == {"hiroshima": None, "hyogo": None}           # the whole prefecture lists, not only the boxes
    assert all(len(s["sha256"]) == 64 for s in sources)
