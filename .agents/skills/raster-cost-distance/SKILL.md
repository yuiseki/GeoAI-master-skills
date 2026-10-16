---
name: raster-cost-distance
description: 値の意味が決まった cost raster (1 m 進むコスト、たとえば秒/m) と 1 つ以上の destination から、各 cell から最もコストの小さい destination までの最小累積コストと、その destination を求める。面の上をどの cell にも動けて、cell ごとに進みにくさが違うときに使う。道路などのグラフに移動を拘束するなら、このスキルではない。cost raster を作ること (土地被覆や傾斜からの換算、道路や川の焼き込み) も扱わない。
---

# raster-cost-distance

直線距離は、森や沼や山の進みにくさを知らない。面の上を自由に動けるが、場所ごとに 1 m 進む時間が違うなら、cost raster の上の最小累積コストで測る。答えは、cost raster の値の意味と単位、格子の距離の測り方、通れない cell の扱いで決まる。この 3 つを先に決めて書く。

このスキルが答えるのは、「この cost raster の上で、各 cell から最寄りの destination まで、最小でどれだけのコストか、それはどの destination か」まで。cost raster は、すでに意味の決まったものを受け取る。土地被覆の分類から速さへの換算、標高から傾斜の補正、道路や川の焼き込み、人口との重ね合わせは、このスキルの外。

| reference | 中身 |
|---|---|
| [cost-definition](references/cost-definition.md) | 値の意味と単位 (1 m あたりのコスト)、隣の cell への移動のコスト (2 cell の平均 × 移動の長さ) を選んだ理由、8 近傍の距離、非正方形の画素、CRS の確かめ方 |
| [barriers-and-nodata](references/barriers-and-nodata.md) | 通れる cell、barrier、NoData、範囲外、届かない cell の区別。対角の移動で角を抜ける規則 |
| [validation](references/validation.md) | 答えの分かる合成の例、仮定を崩した例、GRASS GIS `r.cost` と scikit-image と scipy との照合、速さ |

## 手順

1. cost raster の値の意味と単位を書く。1 cell の値は、その cell の中を 1 m 進むコスト (秒/m なら、速さ m/秒 の逆数)。cell を 1 つ通り抜けるコストや、速さそのもの (km/h) なら、先に 1 m あたりのコストに直す。`--cost-unit` に `s/m` のように書く (既定値は無い)。累積コストの単位は、そこから /m を除いたもの (s/m なら秒)。0、負、無限大のコストの cell があると止まる。
2. CRS と画素の大きさを確かめる。`scripts/cost_distance.py` は、CRS の無いラスタ、経緯度のラスタ、回転した格子を止め、CRS の長さの単位をメートルに直し、ラスタの 9 点で投影の尺度 (地上の 1 m が格子で何 m か) を測って、1 から `--max-scale-error` (既定 0.01) より離れると止める。止まったら、地域に合った投影 (UTM の帯、各国の平面直角座標) に事前に変換する。画素の幅と高さは別々に読み、等しいとは仮定しない。
3. barrier と NoData の意味を決める。barrier (通れない cell) は値で宣言する (`--barrier-value`)。NoData は、通れない cell として扱い、barrier とは別に数える (`--nodata barrier`、既定)。NoData があってはいけないなら `--nodata stop`。NoData を 0 や平均で埋めて通れるようにするかは、cost raster を作る側で決めて書く。ラスタの外へは出られないので、destination の周りは問いの範囲より広く切る。
4. destination を確かめる。id と、ラスタの CRS の x と y の表 (CSV)。それぞれ、点を含む cell の中心に置く (ずらした最大の距離を出す)。ラスタの外、barrier や NoData の上、同じ cell に 2 つある destination は止まる。
5. 解く。8 近傍の多始点 Dijkstra。対角の移動は、共有する 2 つの隣が両方とも通れないとき取らない (`--corner-rule both`、既定)。1 cell 幅の斜めの壁 (川や柵の線を焼いたもの) を対角で抜けないため。
6. 数える。全ての cell を、届いた、届かない (通れるが閉じ込められた)、barrier、NoData に分けて数え、合計が cell の数に合うことを確かめる。届かない cell を大きな数で埋めない。出力では NaN にし、状態の band に理由を残す。destination ごとに、最寄りとした cell の数を見る。
7. 書き出す (下の節)。累積コストは、8 近傍の格子の上の値で、直線の移動より長い (一様なコストで、正方形の画素なら最大 8.2%)。

```sh
uvx --with numpy --with rasterio --with pyproj python scripts/cost_distance.py tmp/cost.tif tmp/destinations.csv \
    --cost-unit s/m --out tmp/cost_distance.tif --barrier-value -1
```

出力は 3 band の GeoTIFF (float64、NoData は NaN): 1 累積コスト、2 最寄りの destination の番号 (表の順、0 から。無ければ -1)、3 状態 (1 届いた、2 届かない、3 barrier、4 NoData)。番号と id の対応と、destination ごとの cell の数は `OUT.destinations.csv`。

テストは `uvx --with numpy --with rasterio --with pyproj --with pytest pytest scripts/test_cost_distance.py`。一様なコストで東西、南北、対角の値、移動のコストが 2 cell の平均と長さの積であること、非正方形の画素、複数の destination と同点のときの規則、コストの低い遠回りを選ぶこと、壁の迂回と 1 cell の隙間、閉じ込められた cell、NoData、角を抜ける規則 3 通り、1 cell 幅の斜めの壁、総当たりの緩和 (Bellman-Ford) との一致、CRS の検査 (経緯度、北緯 35 度の Web メルカトル、UTM、米国測量フィート、回転、CRS 無し)、コマンドの出力を確かめている。出発側の cell の値だけを使う、対角の長さに画素の高さを使わない、角の規則を外す、NoData を通れるようにする、最寄りの destination を伝えない、のそれぞれで落ちることを確かめてある。

外部の実装との照合は `uvx --with numpy --with rasterio --with pyproj --with scipy --with scikit-image --with pytest pytest scripts/test_cost_distance_crosscheck.py` (GRASS GIS の `grass` があれば、その照合も流れる。結果は [validation](references/validation.md))。

## まだできないこと

- 8 近傍だけ。16 近傍 (ナイトの移動) は無い。
- 向きで変わるコスト (上りと下り) は無い。コストは cell の値だけで決まる。
- 経緯度のラスタと、尺度の大きくずれる投影は扱わず、止まる。再投影はしない。
- 道路や鉄道のネットワークと面の移動を組み合わせる経路は無い。
- 全ての cell を Python のループで解く。100 万 cell で約 6 秒 (validation)。

## 書き出すもの

- cost raster (版、作り方)、値の意味と単位 (`--cost-unit`)、累積コストの単位
- CRS、画素の幅と高さ (m)、投影の尺度の最大のずれ
- barrier の値、NoData の扱い、角を抜ける規則
- destination の数、cell の中心にずらした最大の距離、destination ごとの最寄りの cell の数
- 状態ごとの cell の数 (届いた、届かない、barrier、NoData) と、届かない cell の場所
- 累積コストの範囲。8 近傍の格子で測ったこと、ラスタの外へ出られないこと
