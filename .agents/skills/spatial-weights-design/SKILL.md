---
name: spatial-weights-design
description: 空間統計 (Moran's I、局所の指標、空間回帰) を使う前に、誰を誰の近傍とし、どの重みで結ぶか (空間の重み W) を設計して確かめる。面の Queen と Rook、点の k 近傍、距離の帯、距離で減る重みの候補を作り、近傍の数、島、つながりの成分、近傍までの距離、非対称な組を数え、0/1 と行の標準化で統計量が変わるか、候補どうしで近傍がどれだけ重なるか、統計量がどれだけ動くかを並べる。選んだ W と理由を書き出す。
---

# spatial-weights-design

空間の重み W は、データから決まるものではなく、分析者が選ぶ仮定。「近い単位は似る」の「近い」を決める。同じ値でも、W を変えると Moran's I は大きく動く (国の平均寿命で 0.33〜0.76、[sensitivity](references/sensitivity.md))。W は、統計量を計算する前に、現象の届く範囲と、データの単位の並び方から決めて書く。

このスキルが答えるのは、「この問いとこのデータで、どの W がもっともらしく、その選び方で結論が変わるか」まで。W を使って自己相関や空間回帰を測ること自体は、このスキルの外。

| reference | 中身 |
|---|---|
| [contiguity](references/contiguity.md) | 面の隣接 (Queen と Rook)、境界の隙間と重なり、島、つながりの成分 (`scripts/contiguity.py`) |
| [distance-and-knn](references/distance-and-knn.md) | k 近傍と距離の帯と距離で減る重み、距離の単位と CRS、密度の違う場所での近傍の数と距離の偏り |
| [standardization](references/standardization.md) | 0/1、行の標準化、対称にした重み。統計量の意味がどう変わるか |
| [sensitivity](references/sensitivity.md) | W を変えたときの近傍の重なりと統計量の動き。並べ方 |

## 手順

1. 何が何に届くかを書く。現象が隣へ届く仕組み (通勤、感染、価格の参照、地形の連続) と、その距離の目安。届く仕組みが境界の共有なら隣接、距離なら距離の帯か減る重み、数なら k 近傍がもっともらしい。仕組みが分からないなら、そう書き、候補を広めに取る。
2. 距離の測り方を決める。経緯度の度を距離にしない。経緯度なら球面の距離 (`--lon --lat`、km)、投影なら CRS の長さの単位を確かめて渡す (`--x --y --crs-units m`)。面なら、代表点 (面の中の点) の距離か、境界の共有か。
3. 候補を 2〜3 個以上作る (`scripts/weights.py`)。k や距離の帯に固定の値を置かない。k は「隣と呼べる数」、帯は現象の届く距離と、近傍までの距離の分布 (最も近い単位までの距離の最大は、島を作らない最小の帯) から決める。
4. 各候補を数える。近傍の数の最小、中央値、最大、島、つながりの成分、非対称な組の割合、近傍までの距離の中央値と最大。島と小さな成分の単位は、統計量から実質的に抜ける。密な所と疎な所で近傍の数や距離が大きく違うなら、その偏りを書く ([distance-and-knn](references/distance-and-knn.md))。
5. 標準化を決める。0/1 (近傍の値の合計)、行の標準化 (近傍の値の平均)、対称にした 0/1。行の標準化を既定にしない。近傍の数が単位で違うとき、行の標準化は近傍の少ない単位の 1 つの近傍を重くする ([standardization](references/standardization.md))。`--value` で、0/1 と行の標準化の Moran's I を並べる。
6. 感度を見る。候補どうしの近傍の重なり (Jaccard) と、統計量の動きを並べる。結論 (符号、大きさ、局所の有意な単位) が候補で変わるなら、結論は W の選び方に依存すると書く ([sensitivity](references/sensitivity.md))。
7. 書き出す (下の節)。選んだ W は、`--out` で (候補、id、近傍、重み) の Parquet に書ける。

```sh
uvx --with numpy --with scipy --with duckdb --with pyarrow python scripts/weights.py tmp/units.parquet id \
    --lon lon --lat lat --knn 4 8 --band 1000 2000 --value y --out tmp/w.parquet
uvx --from 'duckdb>=1.5.5' --with shapely --with numpy --with pyarrow python scripts/contiguity.py \
    tmp/polygons.parquet id --rule queen --out tmp/queen.parquet
```

テストは `uvx --with numpy --with scipy --with shapely --with duckdb --with pyarrow --with pytest pytest scripts/test_weights.py`。直線の上の点で k 近傍と非対称な組の割合、距離の帯の島と成分と島を作らない最小の帯、北緯 60 度での球面の距離、距離で減る重み、3 つの標準化、近傍の数の違う星形の配置で 0/1 と行の標準化の Moran's I が違うこと、Jaccard、コマンドの出力を確かめている。k 近傍に自分を含める、非対称を数えない、行で割らない、最近傍の距離に自分を含める、のそれぞれで落ちる。libpysal (KNN、DistanceBand) と esda (Moran) との照合は `uvx --with numpy --with scipy --with duckdb --with pyarrow --with libpysal --with esda --with pytest pytest scripts/test_weights_crosscheck.py`。`contiguity.py` のテストは `uvx --from 'duckdb>=1.5.5' --with shapely --with numpy --with pyarrow --with pytest pytest scripts/test_contiguity.py`。

## まだできないこと

- 距離の行列を全て持つので、単位は 20,000 まで。
- ネットワークの距離 (道のり) での近傍。
- 隣接の次数 (隣の隣) を重ねる重み。
- 選んだ W を、ほかのスクリプトが読む形にそろえること (今は Parquet に書くだけ)。

## 書き出すもの

- 届く仕組みの仮定と、それに合う W の型
- 距離の測り方 (球面、投影と CRS の単位、代表点)
- 候補ごとの近傍の数、島、成分、非対称な組、近傍までの距離
- 標準化と理由、0/1 と行の標準化での統計量の違い
- 候補どうしの近傍の重なりと、統計量の動き。結論が W に依存するか
- 選んだ W と理由
