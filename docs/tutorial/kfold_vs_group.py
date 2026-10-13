"""Ordinary K-fold vs holding out whole groups, with plain scikit-learn.

    uvx --with duckdb --with scikit-learn python docs/tutorial/kfold_vs_group.py tmp/wdi_2022_complete.parquet
"""

import sys

import duckdb
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GroupKFold, KFold, cross_val_predict
from sklearn.metrics import r2_score

t = duckdb.sql(f"select * from '{sys.argv[1]}'").df()
X = t[["log_gdp_pc", "log_pop", "urban_pct"]]
y = t["life_exp"]
region = t["region"]

splits = {
    "KFold (行を無作為に)": lambda: dict(cv=KFold(5, shuffle=True, random_state=0)),
    "GroupKFold (地域ごと伏せる)": lambda: dict(cv=GroupKFold(5), groups=region),
}
for name, args in splits.items():
    for model_name, model in (("linear", LinearRegression()),
                              ("hgb", HistGradientBoostingRegressor(random_state=0))):
        pred = cross_val_predict(model, X, y, **args())
        print(f"{name:<24} {model_name:<7} R2 {r2_score(y, pred):.3f}")
