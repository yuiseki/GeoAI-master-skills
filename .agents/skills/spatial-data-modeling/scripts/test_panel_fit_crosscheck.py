"""uvx --with numpy --with pandas --with pyfixest --with pytest pytest test_panel_fit_crosscheck.py

panel_fit against pyfixest (the Python port of R's fixest), which counts in the small-sample factor only the
fixed effects that are not nested in the clusters. An unbalanced synthetic panel; set GEOAI_REALDATA=1 to also
run the WDI country-year panel (needs network access to Hugging Face and duckdb).
"""

import os

import numpy as np
import pandas as pd
import pytest

from panel_fit import fit

pf = pytest.importorskip("pyfixest")


def _panel(seed=0, units=60, years=12):
    rng = np.random.default_rng(seed)
    rows = [(u, t) for u in range(units) for t in range(years) if rng.random() > 0.1]
    df = pd.DataFrame(rows, columns=["unit", "year"])
    df["region"] = df["unit"] % 7
    a = rng.normal(0, 1, units)[df["unit"]]
    df["x1"] = a + rng.normal(0, 1, len(df))
    df["x2"] = rng.normal(0, 1, len(df)) + 0.1 * df["year"]
    df["y"] = 0.5 * df["x1"] - 0.3 * df["x2"] + 2 * a + 0.05 * df["year"] + rng.normal(0, 1, len(df))
    return df


FORMULAS = {"unit": "| unit", "time": "| year", "twoway": "| unit + year"}


def _compare(df, y, xs, effects, cluster):
    ours = fit(df[y].to_numpy(), df[xs].to_numpy(), df["unit"].to_numpy(), df["year"].to_numpy(), effects,
               cluster=df[cluster].to_numpy(), names=xs)
    m = pf.feols(f"{y} ~ {' + '.join(xs)} {FORMULAS[effects]}", data=df, vcov={"CRV1": cluster})
    return ours, m.coef()[xs].to_numpy(), m.se()[xs].to_numpy()


@pytest.mark.parametrize("effects", ["unit", "time", "twoway"])
@pytest.mark.parametrize("cluster", ["unit", "region"])
def test_coefficients_and_clustered_errors_match_fixest(effects, cluster):
    df = _panel()
    ours, coef, se = _compare(df, "y", ["x1", "x2"], effects, cluster)
    assert ours["coef"] == pytest.approx(coef, rel=1e-9)
    assert ours["se_cluster"] == pytest.approx(se, rel=1e-6)


@pytest.mark.skipif(os.environ.get("GEOAI_REALDATA") != "1", reason="real data: set GEOAI_REALDATA=1")
@pytest.mark.parametrize("effects", ["unit", "time", "twoway"])
def test_wdi_country_year_panel(effects):
    duckdb = pytest.importorskip("duckdb")
    w = "hf://datasets/yuiseki/worldbank-wdi/parquet/2026-10-01/"
    df = duckdb.sql(f"""
        select k."Country Code" as unit, d.year as year,
          max(value) filter (where indicator_code = 'SP.DYN.LE00.IN') as le,
          ln(max(value) filter (where indicator_code = 'NY.GDP.PCAP.KD')) as lgdp,
          max(value) filter (where indicator_code = 'SP.URB.TOTL.IN.ZS') as urban
        from '{w}data.parquet' d join '{w}countries.parquet' k on d.country_code = k."Country Code"
        where k."Region" <> '' and d.year between 2000 and 2019
          and indicator_code in ('SP.DYN.LE00.IN', 'NY.GDP.PCAP.KD', 'SP.URB.TOTL.IN.ZS')
        group by all""").df().dropna()
    ours, coef, se = _compare(df, "le", ["lgdp", "urban"], effects, "unit")
    assert ours["coef"] == pytest.approx(coef, rel=1e-9)
    assert ours["se_cluster"] == pytest.approx(se, rel=1e-6)
