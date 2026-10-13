# Natural Earth

全世界の小縮尺ベクター。国、州・省、都市、海岸線、陸地、海、湖、川、道路、鉄道、空港、港、時間帯など。
分析では、国や州を単位にした集計、点を国や州に割り当てる空間結合、陸と海の判定、地図の下地に使う。

## どこから読むか

Hugging Face の `yuiseki/natural-earth` を使う。1 レイヤーが 1 つの GeoParquet で、認証なしに DuckDB から直接読める。

```
hf://datasets/yuiseki/natural-earth/parquet/v5.1.2/<scale>_<category>/<layer>.parquet
```

- `<scale>` は `10m`、`50m`、`110m`。`<category>` は `cultural` か `physical`。
- 例: `hf://datasets/yuiseki/natural-earth/parquet/v5.1.2/10m_cultural/ne_10m_admin_0_countries.parquet`
- 全レイヤーの一覧 (地物数、列数、ジオメトリ型、無効ジオメトリ数、版) はデータセットカードの Layers の表にある: <https://huggingface.co/datasets/yuiseki/natural-earth>
- ラスタ (陰影起伏など) は入っていない。

```sql
load spatial;
select NAME, ADM0_A3, ST_Area(geometry)
from 'hf://datasets/yuiseki/natural-earth/parquet/v5.1.2/110m_cultural/ne_110m_admin_0_countries.parquet';
```

## 粒度と範囲

| 項目 | 値 |
|---|---|
| 空間範囲 | 全世界 |
| 座標系 | EPSG:4326 (経度、緯度)。面積や距離は投影してから測る |
| 縮尺 | 1:10m (細かい)、1:50m、1:110m (粗い) の 3 段 |
| 時点 | 2022-05 の v5.1.2 で止まっている。以後の境界変更、改名、合併は入っていない |
| ライセンス | public domain。表示も不要 |

## 主なレイヤー

分析でよく使うもの。地物数は 10m のもの。

| レイヤー | 中身 | 地物数 | 単位として使うときの注意 |
|---|---|---:|---|
| `ne_10m_admin_0_countries` | 国と地域 | 258 | 結合キーは `ADM0_A3`。下の「ISO_A3 の -99」を参照 |
| `ne_10m_admin_1_states_provinces` | 州・省・県 | 4,596 | 日本は 47 都道府県が揃い、`name_ja` と `wikidataid` も 47 件すべて入っている |
| `ne_10m_admin_2_counties` | 郡 | 3,224 | 米国だけ。他国の第 2 階層は無い |
| `ne_10m_populated_places` | 都市の点 | 7,342 | `POP_MAX` は 10 件が 0 以下 (最小 -99)。`WIKIDATAID` は 7,192 件にある |
| `ne_10m_land` / `ne_10m_ocean` | 陸と海 | 11 / 1 | 点の陸海判定に使える。`ne_10m_ocean` の 1 件は無効ジオメトリ |
| `ne_10m_coastline` | 海岸線 | 4,133 | 海岸からの距離の特徴量に使える |
| `ne_10m_urban_areas` | 市街地の面 | 11,878 | 版は 4.1.0 で古い |

縮尺を下げると地物が減る。国は 10m で 258、50m で 242、110m で 177 で、小さな島嶼国が消える。点を国に結合するなら 10m を使う。

## 気をつけること

ISO_A3 の -99。 `ne_10m_admin_0_countries` の 258 件中 22 件で `ISO_A3` が `-99`。France と Norway もそう。`ADM0_A3` は 258 件すべてに入っていて重複も無いので、結合キーにはこちらを使う。ISO コードが要るなら `ISO_A3_EH` のほうが埋まっている (France は `FRA`、Norway は `NOR`) が、Kosovo、Somaliland、N. Cyprus などは `ISO_A3_EH` でも `-99`。

人口と GDP の年が揃っていない。 国の `POP_EST` の年 (`POP_YEAR`) は 258 件中 232 件が 2019 年で、残りは 2009〜2020 年。`GDP_MD` の年 (`GDP_YEAR`) は 193 件が 2019 年で、残りは 1999〜2018 年に散らばる。国の間で比べる特徴量にするなら `POP_YEAR` と `GDP_YEAR` を確かめる。最新の値が要るなら World Bank などの統計と結合する。

国境は de facto。 既定は実効支配の線。`ne_10m_admin_0_countries_<iso>` の 33 レイヤーが国ごとの見方の変種。たとえば `NAME_JA` は Taiwan が `中華民国`、Kosovo が `コソボ共和国`。どの見方を使ったかを報告に書く。

無効ジオメトリ。 `ne_10m_admin_0_countries` では Egypt の 1 件が `ST_IsValid` で偽になる。`ne_10m_urban_areas_landscan` は 6,018 件中 2,238 件が無効。面積や交差を計算する前に `ST_MakeValid` するか、件数を数えて報告する。

ジオメトリの無いレイヤーがある。 `ne_10m_admin_0_names` は geometry 列を持つが 505 件すべて NULL。国名の別表記の表として使う。

## 確かめた日

2026-10-10 に `hf://` から DuckDB 1.5.5 以上で読んで実測した。データセットの取得日は 2026-10-06 (カードの記載)。
