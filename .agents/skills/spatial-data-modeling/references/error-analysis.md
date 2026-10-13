# 誤差の分析

全体の点数は、どこで外れているかを隠す。交差検証の外側の予測 (`compare_models.py --predictions-out`) を、グループや数値の分位ごとに分けて、偏り (予測 − 目的変数の平均)、MAE、RMSE を見る。`scripts/error_breakdown.py`。

```sh
uvx --with numpy --with duckdb python scripts/error_breakdown.py \
  tmp/predictions.parquet tmp/table.parquet ID region --model linear
uvx --with numpy --with duckdb python scripts/error_breakdown.py \
  tmp/predictions.parquet tmp/table.parquet ID n_measurements --bins 5
```

- 文字列の列はそのままグループに、数値の列は分位で `--bins` 個に分ける。
- repeat が複数あるときは、行ごとに予測を平均してから分ける。
- `--weight` で、グループの中の点数を重み付きにする。

## 何で分けるか

| 分ける列 | 見えること |
|---|---|
| 地域、行政区 | 特徴量に無い地域の違い (偏りの符号が地域で揃う) |
| 測定の回数、人口 | 目的変数の雑音 (回数の少ない行ほど MAE が大きい) |
| 時期 | 時期によるずれ。前の期間で学習して次の期間を当てると、符号まで変わることがある (以前の分析、携帯の通信速度のタイル) |
| 範囲の端からの距離 | 端の効果 (spatial-feature-engineering) |
| 予測の値 | 予測が大きい所、小さい所での偏り (平均の方へ縮む癖) |

## 例

WDI の 2022 年の平均寿命、線形、行を無作為に 5 分割 (repeat 3 の平均、2026-10-10)。

| 地域 | 国 | 偏り | MAE |
|---|---:|---:|---:|
| サブサハラ・アフリカ | 46 | +2.94 | 4.80 |
| 南アジア | 6 | -5.18 | 5.18 |
| 中東・北アフリカ | 22 | -2.47 | 3.51 |
| 欧州・中央アジア | 55 | -0.65 | 2.22 |
| 中南米・カリブ | 39 | -0.30 | 2.20 |
| 東アジア・太平洋 | 36 | -0.29 | 2.69 |

- サブサハラ・アフリカは平均で 2.9 歳高く、南アジアは 5.2 歳、中東・北アフリカは 2.5 歳低く予測される。1 人あたり GDP などの 3 つの特徴量に無い、地域の違いが残っている (spatial-autocorrelation で残差に自己相関が残ったことと合う)。
- サブサハラ・アフリカの RMSE (7.99) は MAE より大きく離れる。中央アフリカ共和国 (平均寿命 18.8 歳、dataset-discovery の references/worldbank-wdi.md) が引き上げている。
- 人口の大きさの分位では、偏りは ±0.1 歳以内で、人口による偏りは無い。
