"""uvx --with numpy --with scipy --with jax==0.12.0.1 --with numpyro==0.22.0 --with pyproj --with pytest pytest test_hsgp_numpyro.py

The basis of hsgp.py against NumPyro's own (numpyro.contrib.hsgp), and the model with inferred parameters on a
surface drawn from a known Matern 5/2 process: the parameters' intervals cover the truth and the 90% predictive
intervals at held-out points hold about 90% of them, with three times the rule's m; with the rule's m, the noise is
overestimated. JAX on the CPU only. About 4 minutes.
"""

import os

os.environ.setdefault("JAX_PLATFORMS", "cpu")
os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")

import numpy as np
import pytest

from hsgp import Box, approx_cov, kernel, rule
from hsgp_numpyro import ell_min, fit, predict


@pytest.mark.parametrize("kind,nu", [("matern52", 2.5), ("matern32", 1.5), ("se", None)])
def test_the_basis_matches_numpyro_contrib_hsgp(kind, nu):
    """Same box, same m: the approximate covariance Phi diag(S) Phi^T (which does not depend on the order of the
    basis functions) agrees with NumPyro's eigenfunctions and spectral densities to 1e-5 (NumPyro computes in float32).
    NumPyro's `alpha` is the variance sigma^2, not sigma: passing sigma gives a covariance sigma times too small."""
    from numpyro.contrib.hsgp.laplacian import eigenfunctions
    from numpyro.contrib.hsgp.spectral_densities import (diag_spectral_density_matern,
                                                         diag_spectral_density_squared_exponential)
    xy = np.random.default_rng(0).uniform(0, 10, (80, 2))
    box, m = Box.around(xy, c=1.6), 9
    ours = approx_cov(xy, xy, box, m, kind, 1.3, 2.0)
    L = [float(x) for x in box.L]
    phi = np.asarray(eigenfunctions(xy - box.center, ell=L, m=[m, m]))
    if nu is None:
        s = diag_spectral_density_squared_exponential(1.3 ** 2, 2.0, ell=L, m=[m, m], dim=2)
    else:
        s = diag_spectral_density_matern(nu, 1.3 ** 2, 2.0, ell=L, m=[m, m], dim=2)
    theirs = (phi * np.asarray(s)) @ phi.T
    assert np.abs(ours - theirs).max() < 1e-5


TRUTH = dict(a=50.0, sigma=4.0, ell=2.0, noise=0.5)


def _surface():
    rng = np.random.default_rng(3)
    xy = rng.uniform(0, 10, (1300, 2))
    K = kernel(xy, xy, "matern52", TRUTH["sigma"], TRUTH["ell"]) + 1e-8 * np.eye(len(xy))
    f = TRUTH["a"] + np.linalg.cholesky(K) @ rng.normal(size=len(xy))
    v = f + TRUTH["noise"] * rng.normal(size=len(xy))
    obs = slice(0, 1000)
    half = Box.around(xy[obs]).half.max()
    c, m = rule("matern52", 1.5, half)      # a guess shorter than the truth
    return xy, f, v, max(c, 2.0), m, half


def test_the_rule_s_m_pushes_the_fine_variation_into_the_noise():
    """With the rule's m (11 per axis), the variation the basis cannot draw is taken as noise: 0.68 for 0.5."""
    xy, f, v, c, m, half = _surface()
    post = fit(xy[:1000], v[:1000], Box.around(xy[:1000], c=c), m, draws=400, warmup=400, chains=2, seed=0)
    assert np.quantile(post["noise"], 0.05) > 0.6


def test_three_times_the_rule_recovers_a_known_surface_and_its_intervals_hold():
    xy, f, v, c, m, half = _surface()
    m = 3 * m
    box = Box.around(xy[:1000], c=c)
    post = fit(xy[:1000], v[:1000], box, m, draws=400, warmup=400, chains=2, seed=0)
    assert post["diverging"] == 0
    for k, t in TRUTH.items():
        lo, hi = np.quantile(post[k], [0.05, 0.95])
        assert lo < t < hi, (k, lo, hi)
    assert np.median(post["ell"]) > ell_min("matern52", c, m, half)
    _, y = predict(post, xy[1000:], box, m)
    lo, hi = np.quantile(y, [0.05, 0.95], axis=0)
    cover = np.mean((v[1000:] > lo) & (v[1000:] < hi))
    assert 0.84 < cover < 0.96, cover


def _yamanashi_dem(n, seed=42):
    """n random pixels of 4 x 4 GSI elevation tiles (zoom 14, x 14493-14496, y 6449-6452), UTM 54N in km."""
    import urllib.request

    from pyproj import Transformer
    grid = np.empty((1024, 1024))
    for i, y in enumerate(range(6449, 6453)):
        for j, x in enumerate(range(14493, 14497)):
            url = f"https://cyberjapandata.gsi.go.jp/xyz/dem/14/{x}/{y}.txt"
            text = urllib.request.urlopen(url, timeout=30).read().decode()
            grid[i * 256:(i + 1) * 256, j * 256:(j + 1) * 256] = [[float(s) for s in r.split(",")] for r in text.split()]
    k = np.random.default_rng(seed).choice(1024 * 1024, n, replace=False)
    py, px = np.divmod(k, 1024)
    size = 2 ** 14 * 256
    lon = (14493 * 256 + px + 0.5) / size * 360 - 180
    lat = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * (6449 * 256 + py + 0.5) / size))))
    e, nn = Transformer.from_crs(4326, 32654, always_xy=True).transform(lon, lat)
    return np.c_[e, nn] / 1000.0, grid[py, px]


@pytest.mark.skipif(os.environ.get("GEOAI_REALDATA") != "1", reason="real data: set GEOAI_REALDATA=1")
def test_yamanashi_elevation_against_kriging():
    """500 observed pixels, 300 held out. HSGP (Matern 5/2, c = 1.5, the rule's m for ell = 1 km, doubled) passes
    the length-scale diagnostic and holds about 90% in its intervals; it beats the nearest neighbour but not local
    ordinary kriging, whose intervals are too wide."""
    from interpolate_points import Obs
    from interpolate_points import predict as kpredict
    xy, v = _yamanashi_dem(800)
    o, h = slice(0, 500), slice(500, None)
    nearest = np.abs(kpredict(Obs(xy[o] * 1000, v[o]), xy[h] * 1000, "nearest")["prediction"] - v[h]).mean()
    kr = kpredict(Obs(xy[o] * 1000, v[o]), xy[h] * 1000, "kriging", k=12)
    kerr = kr["prediction"] - v[h]
    half = Box.around(xy[o]).half.max()
    _, m = rule("matern52", 1.0, half)
    c, m = 1.5, 2 * m
    box = Box.around(xy[o], c=c)
    post = fit(xy[o], v[o], box, m, draws=500, warmup=500, chains=2, seed=0)
    f, y = predict(post, xy[h], box, m)
    lo, hi = np.quantile(y, [0.05, 0.95], axis=0)
    mae, cover = np.abs(f.mean(0) - v[h]).mean(), np.mean((v[h] > lo) & (v[h] < hi))
    kcover = np.mean(np.abs(kerr) < 1.645 * kr["kriging_sd"])
    print(f"nearest {nearest:.2f} kriging {np.abs(kerr).mean():.2f} ({kcover:.3f}) hsgp m {m} {mae:.2f} ({cover:.3f}) "
          f"ell {np.median(post['ell']):.3f} ell_min {ell_min('matern52', c, m, half):.3f} "
          f"noise {np.median(post['noise']):.2f}")
    assert np.median(post["ell"]) > ell_min("matern52", c, m, half)
    assert 0.85 < cover < 0.95
    assert np.abs(kerr).mean() < mae < nearest
    assert kcover > 0.95


_JMA = "https://www.data.jma.go.jp/risk/obsdl"
_PREFS = [*range(31, 37), *range(40, 47), *range(48, 58), *range(60, 67)]   # obsdl pd: Aomori to Okayama-side Hyogo


def _jma_post(path, data):
    import urllib.parse
    import urllib.request
    req = urllib.request.Request(f"{_JMA}/{path}", urllib.parse.urlencode(data).encode(), headers={
        "Origin": "https://www.data.jma.go.jp", "Referer": f"{_JMA}/index.php"})
    return urllib.request.urlopen(req, timeout=120).read()


def _jma_temperature(year=2025, month=10):
    """Monthly mean temperature (element 201) of the open JMA stations that observe temperature in eastern and
    central Honshu (obsdl, cited as 気象庁ホームページ), quality 8 only, latitude >= 33.3 (no Hachijojima or
    Ogasawara). Returns km coordinates (azimuthal equidistant at 37 N 138.5 E), elevation (m) and temperature."""
    import csv
    import io
    import json
    import re

    from pyproj import Transformer
    st = {}
    for pd in _PREFS:
        for x in json.loads(_jma_post("top/station", {"pd": pd}))["markers"]:
            if x["kind"] == "station" and not x["ended"] and x["kansoku"][1] == "1":
                la = re.search(r"北緯：(\d+)度([\d.]+)分", x["title"])
                lo = re.search(r"東経：(\d+)度([\d.]+)分", x["title"])
                el = re.search(r"標高：(-?[\d.]+)m", x["title"])
                st[x["stid"]] = (x["stname"], int(la[1]) + float(la[2]) / 60, int(lo[1]) + float(lo[2]) / 60,
                                 float(el[1]))
    ids, out = sorted(st), []
    for i in range(0, len(ids), 40):
        batch = ids[i:i + 40]
        raw = _jma_post("show/table", {
            "stationNumList": json.dumps(batch), "aggrgPeriod": 5, "elementNumList": '[["201",""]]',
            "ymdList": json.dumps([str(year), str(year), str(month), str(month), "1", "31"]),
            "option": '{"list":["obs"],"nyear":0}', "downloadFlag": "true", "csvFlag": 1, "rmkFlag": 1,
            "disconnectFlag": 1, "ymdLiteral": 1, "interAnnualType": 1, "youbiFlag": 0, "fukenFlag": 0,
            "kijiFlag": 0, "jikantaiFlag": 0, "jikantaiList": "[]"})
        rows = list(csv.reader(io.StringIO(raw.decode("cp932"))))
        for k, sid in enumerate(batch):          # columns in triples (value, quality, homogeneity), request order
            assert rows[2][1 + 3 * k] == st[sid][0]
            v, q = rows[-1][1 + 3 * k], rows[-1][2 + 3 * k]
            if q == "8" and st[sid][1] >= 33.3:
                out.append((st[sid][1], st[sid][2], st[sid][3], float(v)))
    lat, lon, elev, t = np.array(out).T
    tr = Transformer.from_crs("EPSG:4326", "+proj=aeqd +lat_0=37 +lon_0=138.5 +datum=WGS84 +units=m", always_xy=True)
    return np.c_[tr.transform(lon, lat)] / 1000.0, elev, t


@pytest.mark.skipif(os.environ.get("GEOAI_REALDATA") != "1", reason="real data: set GEOAI_REALDATA=1")
def test_jma_monthly_temperature_hsgp_matches_kriging_after_the_lapse_rate():
    """October 2025, 440 stations, 100 held out (seed 42). The elevation trend (lapse rate, least squares on the
    observed stations) is taken out and both methods interpolate the residual. HSGP (Matern 5/2, c = 1.5, three
    times the rule's m for ell = 100 km) passes the length-scale diagnostic, holds about 90%, and its error is
    within 10% of local ordinary kriging's; both beat the nearest station."""
    from interpolate_points import Obs
    from interpolate_points import predict as kpredict
    xy, elev, t = _jma_temperature()
    k = np.random.default_rng(42).permutation(len(t))
    h, o = k[:100], k[100:]
    b = np.linalg.lstsq(np.c_[np.ones(len(o)), elev[o]], t[o], rcond=None)[0]
    v = t - (b[0] + b[1] * elev)
    assert -7 < b[1] * 1000 < -4                       # deg C per km
    nearest = np.abs(kpredict(Obs(xy[o] * 1000, v[o]), xy[h] * 1000, "nearest")["prediction"] - v[h]).mean()
    kr = kpredict(Obs(xy[o] * 1000, v[o]), xy[h] * 1000, "kriging", k=12)
    kmae = np.abs(kr["prediction"] - v[h]).mean()
    half = Box.around(xy[o]).half.max()
    _, m = rule("matern52", 100.0, half)
    c, m = 1.5, 3 * m
    box = Box.around(xy[o], c=c)
    post = fit(xy[o], v[o], box, m, draws=500, warmup=500, chains=2, seed=0, target_accept=0.95)
    f, y = predict(post, xy[h], box, m)
    lo, hi = np.quantile(y, [0.05, 0.95], axis=0)
    mae, cover = np.abs(f.mean(0) - v[h]).mean(), np.mean((v[h] > lo) & (v[h] < hi))
    print(f"lapse {b[1] * 1000:.2f} nearest {nearest:.3f} kriging {kmae:.3f} hsgp m {m} {mae:.3f} ({cover:.3f}) "
          f"ell {np.median(post['ell']):.1f} ell_min {ell_min('matern52', c, m, half):.1f} "
          f"noise {np.median(post['noise']):.3f} div {post['diverging']}")
    assert np.median(post["ell"]) > ell_min("matern52", c, m, half)
    assert 0.85 <= cover <= 0.95
    assert mae < 1.1 * kmae and max(mae, kmae) < nearest
