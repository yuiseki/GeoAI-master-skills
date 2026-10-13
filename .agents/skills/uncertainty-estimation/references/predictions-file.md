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
