# 外側の予測のファイル

`uncertainty.py` は、交差検証の外側の予測を書いた Parquet を読む。列は repeat、model、id、target、prediction。id は、結合する表の行の id。

外側の予測とは、各行を、その行を学習に使わなかったモデルで予測した値。学習に使った行の予測では、誤差が小さく見え、較正も区間も楽観的になる。

どのモデルでも書ける。分割 (repeat 1 つ、分割表なし) の例:

```python
import duckdb, numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import KFold, cross_val_predict

t = duckdb.sql("select id, y, x1, x2 from 'tmp/table.parquet'").df().dropna()
pred = cross_val_predict(HistGradientBoostingRegressor(random_state=0), t[["x1", "x2"]], t["y"],
                         cv=KFold(5, shuffle=True, random_state=0))
out = t.assign(repeat=0, model="hgb", target=t["y"], prediction=pred)[
    ["repeat", "model", "id", "target", "prediction"]]
duckdb.sql("copy out to 'tmp/oof.parquet' (format parquet)")
```

本番の使い道が「観測済みでない単位を予測する」なら、`KFold` を `GroupKFold` にするなど、使い道に合った分け方にする。分け方が甘いと、区間は実際より狭くなる。

## 保証の付く区間のための分割 (role の列)

交差検証の外側の予測は、fold ごとに違うモデルが出す。共形予測の保証 (references/intervals.md) が欲しいなら、行を学習用、較正用、試験用の 3 つに分け、学習用の行だけで 1 つのモデルを当て、較正用と試験用の行を予測する。`role` の列に `calibration` か `test` を書くと、`uncertainty.py intervals` は較正用の行の残差で区間を作り、試験用の行で被覆率を測る。学習用の行は書かない。

```python
import duckdb, numpy as np
from sklearn.linear_model import LinearRegression

t = duckdb.sql("select id, y, x1, x2 from 'tmp/table.parquet'").df().dropna()
x = ["x1", "x2"]
# Rows split by row here; split by group (region, block, period) when the use is an unseen group.
part = np.random.default_rng(0).permutation(len(t)) % 3  # 0 learn, 1 calibration, 2 test
model = LinearRegression().fit(t.loc[part == 0, x], t.loc[part == 0, "y"])
held = t[part > 0]
out = held.assign(repeat=0, model="linear", target=held["y"], prediction=model.predict(held[x]),
                  role=np.where(part[part > 0] == 1, "calibration", "test"))[
    ["repeat", "model", "id", "target", "prediction", "role"]]
duckdb.sql("copy out to 'tmp/split.parquet' (format parquet)")
```

WDI の 2022 年の平均寿命 (209 か国) で、行を 3 分割した線形回帰は、試験用の 69 か国の 92.8% を覆い、サブサハラ・アフリカの 15 か国では 73.3% だった (2026-10-16)。行の数が 3 分の 1 になるので、較正用の行が少ないと区間は広く、被覆率の揺れは大きい。
