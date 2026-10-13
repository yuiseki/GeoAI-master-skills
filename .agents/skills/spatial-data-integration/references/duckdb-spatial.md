# DuckDB spatial の落とし穴

DuckDB 1.5.6 の spatial 拡張で 2026-10-10 に確かめたこと。版が変われば挙動も変わりうるので、版を上げたら確かめ直す。

## CRS の名前が違うと空間関数が拒む

`geometry` 列は CRS の名前を型に持つ (`GEOMETRY('EPSG:4326')`、`GEOMETRY('OGC:CRS84')`)。名前が違う 2 つを `ST_Intersects` などに渡すとエラーになる。

```
Binder Error: Cannot call function 'ST_Intersects' with geometries of different coordinate reference systems (CRS).
```

`EPSG:4326` と `OGC:CRS84` はどちらも WGS 84 の経度緯度で、GeoParquet の中の座標はどちらも経度、緯度の順。中身を変えずに名前だけ揃える。

```sql
ST_SetCRS(geometry, 'EPSG:4326')
```

`ST_SetCRS` は名前を付け替えるだけで、座標は変えない。本当に別の座標系 (UTM など) のデータなら `ST_Transform` で変換する。

## 球面距離は緯度、経度の順で受け取る

`ST_Distance_Sphere` と `ST_Distance_Spheroid` は、点の x を緯度、y を経度として読む。GeoParquet の点 (x が経度) をそのまま渡すと間違える。東京 (139.767, 35.681) と大阪 (135.500, 34.733) で確かめた。

| 呼び方 | 結果 |
|---|---|
| `ST_Distance_Sphere(東京, 大阪)` (経度、緯度のまま) | 480,808 m。黙って 2 割違う |
| `ST_Distance_Sphere(ST_FlipCoordinates(東京), ST_FlipCoordinates(大阪))` | 401,713 m |
| `ST_Distance_Spheroid` (経度、緯度のまま) | NaN |
| `ST_Distance_Spheroid` (入れ替えたもの) | 402,487 m |

- CRS の名前を `OGC:CRS84` にしても `EPSG:4326` にしても、`ST_Distance_Sphere` は同じ 480,808 m を返す。名前では軸の順は変わらない。
- `ST_Distance_Spheroid` は CRS の名前が付いた geometry を受け付けない (Binder Error)。名前の無い geometry にしてから渡す。
- 赤道付近では経度 1 度と緯度 1 度がほぼ同じ長さなので、入れ替えを忘れても距離がほとんど変わらない。確かめるときは高緯度の点を使う。

## ST_Transform は軸の順を EPSG の定義に従う

`ST_Transform(geometry, 'EPSG:4326', 'EPSG:3857')` は、EPSG:4326 の定義どおり緯度、経度の順だと解釈する。経度、緯度の点を渡すと、エラーにならずに無限大の座標を返す。`always_xy := true` を付ける。

```sql
ST_Transform(geometry, 'EPSG:4326', 'EPSG:3857', always_xy := true)
```

EPSG:3857 (Web メルカトル) での距離は実際の距離ではない。北緯 35 度で東京から大阪が 492 km になる (球面では 402 km)。距離や面積は、球面の関数か、対象地域に合った投影 (UTM、正積図法) で測る。

## ST_Distance は度を返す

経度緯度の geometry に `ST_Distance` や `ST_DWithin` を使うと、単位は度。経度 1 度の長さは緯度で変わる (赤道で約 111 km、北緯 60 度で約 56 km) ので、度のしきい値は候補を絞るのにだけ使い、最後の判定はメートルで行う。
