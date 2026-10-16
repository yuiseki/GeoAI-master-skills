---
name: land-cover-cost
description: 分類済みの土地被覆の raster と、明示的な class から cost への対応表 (CSV) から、1 m 進むコストの cost raster を作る。対応表に無いクラス、重なったクラス、正でないコストで止まり、通れない class (barrier) と NoData を別の値で残し、クラスごとの cell の数と対応表の hash を audit に書く。対応表の値そのもの (どの土地被覆で何秒/m か) は決めない。
---

# land-cover-cost

土地被覆のクラスを移動のコストに直すと、答えは対応表で決まる。対応表をコードに埋めず、ファイルとして渡し、その hash と、どのクラスが何 cell あったかを残す。対応表に無いクラスを、黙って 0 や既定のコストにしない。

このスキルが答えるのは、「この分類図とこの対応表から、どの cell がどのコストになったか」まで。対応表の値を決めること (歩く速さの文献、地域の事情)、傾斜や道路や川との組み合わせ、最小累積コストの計算は、このスキルの外。

## 対応表

CSV。必須の列は `class`、`status`、`cost_per_m`。ほかの列 (`source`、`note` など) は audit にそのまま残る。

```csv
class,status,cost_per_m,source,note
1,passable,0.5,example,grass
2,passable,0.8,example,forest
3,barrier,,example,water
```

| 列 | 中身 |
|---|---|
| `class` | raster のクラスの番号 (整数) |
| `status` | `passable` (通れる) か `barrier` (通れない) |
| `cost_per_m` | passable なら 1 m 進むコスト (正の有限の数、単位は `--cost-unit`)。barrier なら空 |

止まる条件 (何も書かずに止まる): raster にあって対応表に無いクラス、同じクラスが 2 行、passable なのにコストが 0、負、NaN、無限大、空、数でない、barrier にコストがある、`status` が 2 つ以外、クラスが整数でない、対応表のクラスが raster の NoData の値と同じ。対応表にあって raster に無いクラスは、0 cell として数える。

`source` には、値の出どころ (文献、仮定、試しの値) を書く。試しの値のまま結論を書かない。

## 出力

float64 の GeoTIFF。格子 (CRS、transform、幅、高さ、画素の大きさ) は入力と同じ。

| cell | 値 |
|---|---|
| passable のクラス | そのクラスの `cost_per_m` |
| barrier のクラス | `--barrier-value` (既定 -1。0 以下か inf だけ許す。コストと読まれない値) |
| 入力の NoData | NaN (GeoTIFF の NoData も NaN) |

barrier と NoData は別の値で残る。最小累積コストを解く側には、「1 m あたりのコスト、単位は `--cost-unit`、barrier は -1、NoData は NaN」と伝える。

audit (JSON、既定は出力の名前に `.audit.json`): 入力の raster と band、対応表のパスと SHA-256、コストの単位、barrier の値、NoData の表し方、クラスごとの対応表の行と cell の数、passable、barrier、NoData の cell の数と合計、格子、出力のパス。

## 手順

1. 分類図の中身を数える。整数の型か、NoData の値は何か、どのクラスが何 cell あるか、CRS と画素の大きさ。クラスの番号の意味は、データの説明で確かめる。
2. 対応表を書く。全てのクラスに行を作る。通れないクラス (水域、崖など) を `barrier` にするか、高いコストにするかを決めて書く。値の出どころを `source` に書く。NoData を通れるとするかは、ここでは決めない (NoData のまま渡す)。
3. 変換する。`--cost-unit` に単位を書く (既定値は無い。/m で終わる)。
4. audit を読む。クラスごとの cell の数、passable、barrier、NoData の数と合計。cell の多いクラスのコストが、結論を左右する。
5. 距離をメートルで測るなら、分類図はメートルの投影の格子であること。このスクリプトは格子を変えないので、経緯度の分類図からは経緯度の cost raster ができる。分類図を投影し直すなら、最近傍か最頻値で行い (平均や双一次は存在しないクラスを作る)、変換の前に行う。
6. 書き出す (下の節)。

```sh
uvx --with numpy --with rasterio python scripts/land_cover_cost.py tmp/landcover.tif tmp/mapping.csv \
    --cost-unit s/m --out tmp/cost.tif
```

出力の場所に同じ名前のファイルがあると止まる (上書きしない)。

テストは `uvx --with numpy --with rasterio --with pytest pytest scripts/test_land_cover_cost.py`。クラスからコストへの変換、barrier の値 (既定と inf、コストと読まれる値の拒否)、NoData が NaN のまま残ること、NoData の無い raster、対応表に無いクラスで何も書かずに止まること、重なったクラス、0、負、NaN、inf、空、数でないコスト、barrier のコスト、`status` の誤り、整数でないクラス、列の欠け、浮動小数の raster、NoData の値と同じクラス、格子が変わらないこと (非正方形の画素)、ブロックに分けて読んだときのクラスごとと状態ごとの数、audit の hash、上書きの拒否、単位の検査を確かめている。対応表に無いクラスの検査を外す、NoData を有効とする、重なりの検査を外す、コストの検査を外す、barrier を NaN にする、NoData を数えない、のそれぞれで落ちることを確かめてある。

## まだできないこと

- 1 つの band の、整数のクラスの分類図だけ。クラスの確率の raster (確率で重みを付けたコスト) は扱わない。
- 再投影はしない (手順 5)。
- 傾斜、道路、川などを重ねたコストは作らない。

## 書き出すもの

- 分類図 (版、時点、クラスの定義の出どころ)、CRS と画素の大きさ
- 対応表のパスと SHA-256、各クラスの status、cost_per_m、source
- コストの単位と barrier の値、NoData の表し方 (NaN)
- クラスごとの cell の数、passable、barrier、NoData の数と合計
- 値の出どころが試しの値や仮定なら、そう書く
