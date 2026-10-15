"""uvx --from 'duckdb>=1.5.5' --with pyproj --with numpy --with pandas --with patsy --with libpysal --with esda --with pytest pytest test_st_model_crosscheck.py

st_model against least squares on an explicit dummy design (location and time dummies, and location-by-time
slopes; patsy builds it, numpy's lstsq solves it) and PySAL's esda (Moran's I with the same k-nearest-neighbour
graph, binary and symmetrised). statsmodels' OLS is not used as the reference: on the rank-deficient WDI design
(441 columns, rank 438) version 0.15.0 returned fitted values whose residual sum of squares was 0.2 above the
least-squares minimum. An unbalanced synthetic panel; set
GEOAI_REALDATA=1 to also run WDI life expectancy at country label points (needs duckdb, pyproj and network).
"""

import os

import numpy as np
import pandas as pd
import pytest
import patsy

from st_model import fit, knn_weights, moran, predict, simulate


def _ols_fitted(df, formula):
    y, X = patsy.dmatrices(formula, df, return_type="matrix")
    X = np.asarray(X, float)
    return X @ np.linalg.lstsq(X, np.asarray(y, float).ravel(), rcond=None)[0]


def _check_models(df, coords):
    loc, t, y = df["loc"].to_numpy(), df["t"].to_numpy(float), df["y"].to_numpy(float)
    for model, formula in (("space", "y ~ C(loc)"), ("time", "y ~ C(t)"), ("additive", "y ~ C(loc) + C(t)"),
                           ("interaction", "y ~ C(loc) + C(t) + C(loc):tc")):
        d = df.assign(tc=df["t"] - df["t"].mean())
        ours = predict(fit(model, loc, t, y, coords), loc, t, coords)
        assert ours == pytest.approx(_ols_fitted(d, formula), abs=1e-6), model


def _check_moran(values, points, k=4):
    from esda.moran import Moran
    from libpysal.weights import KNN, W

    knn = KNN.from_array(np.asarray(points, float), k=k)
    sym = {i: sorted(set(knn.neighbors[i]) | {j for j in knn.neighbors if i in knn.neighbors[j]}) for i in knn.neighbors}
    w = W(sym, silence_warnings=True)
    w.transform = "B"
    theirs = Moran(np.asarray(values, float), w, transformation="B", permutations=0).I  # esda defaults to "r"
    assert moran(values, knn_weights(points, k)) == pytest.approx(theirs, abs=1e-10)


def test_decompositions_equal_dummy_regressions_with_missing_cells():
    d = simulate("interaction", seed=0, n_loc=25, n_t=12, missing=0.15)
    df = pd.DataFrame({"loc": d["loc"], "t": d["t"], "y": d["y"]})
    _check_models(df, d["coords"])


def test_moran_equals_esda_on_residuals_at_each_time():
    d = simulate("separable", seed=1, n_loc=40, n_t=5)
    for tt in np.unique(d["t"]):
        m = d["t"] == tt
        _check_moran(d["y"][m], [d["coords"][s] for s in d["loc"][m]])


@pytest.mark.skipif(os.environ.get("GEOAI_REALDATA") != "1", reason="real data: set GEOAI_REALDATA=1")
def test_wdi_life_expectancy_at_country_points():
    duckdb = pytest.importorskip("duckdb")
    from pyproj import Transformer

    w = "hf://datasets/yuiseki/worldbank-wdi/parquet/2026-10-01/"
    ne = "hf://datasets/yuiseki/natural-earth/parquet/v5.1.2/10m_cultural/ne_10m_admin_0_countries.parquet"
    df = duckdb.sql(f"""
        with ne as (select ISO_A3_EH as iso, LABEL_X as lon, LABEL_Y as lat from '{ne}' where ISO_A3_EH <> '-99'
                    qualify row_number() over (partition by ISO_A3_EH order by (ADM0_A3 = ISO_A3_EH) desc) = 1)
        select d.country_code as loc, d.year::double as t, d.value::double as y, ne.lon, ne.lat
        from '{w}data.parquet' d join '{w}countries.parquet' k on d.country_code = k."Country Code"
        join ne on ne.iso = d.country_code
        where k."Region" <> '' and d.indicator_code = 'SP.DYN.LE00.IN' and d.year between 2000 and 2019""").df()
    to_m = Transformer.from_crs("EPSG:4326", "ESRI:54009", always_xy=True)  # Mollweide, equal area
    pts = df.drop_duplicates("loc")
    x, yy = to_m.transform(pts["lon"].to_numpy(), pts["lat"].to_numpy())
    coords = {c: (a / 1e6, b / 1e6) for c, a, b in zip(pts["loc"], x, yy)}
    _check_models(df, coords)
    p = fit("additive", df["loc"].to_numpy(), df["t"].to_numpy(), df["y"].to_numpy(), coords)
    r = df["y"].to_numpy() - predict(p, df["loc"].to_numpy(), df["t"].to_numpy(), coords)
    m = df["t"].to_numpy() == 2019
    _check_moran(r[m], [coords[c] for c in df["loc"].to_numpy()[m]])
