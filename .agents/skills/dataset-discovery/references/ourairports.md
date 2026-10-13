# OurAirports

全世界の空港、ヘリポート、飛行場の点と、IATA / ICAO コード、定期便の有無、滑走路、無線施設。
分析では、点データの密度や最近傍距離の特徴量、施設配置の候補地、空港を結ぶネットワークの節点に使う。

## どこから読むか

Hugging Face の `yuiseki/ourairports-2026-08`。2026-08-31 の `davidmegginson/ourairports-data` のコミットを凍結したもの。配布元は毎晩同じ URL で上書きするので、配布元を直接読むと再現できない。

```
hf://datasets/yuiseki/ourairports-2026-08/parquet/<table>.parquet
```

- カード: <https://huggingface.co/datasets/yuiseki/ourairports-2026-08>

| テーブル | 行数 | 1 行 |
|---|---:|---|
| `airports` | 86,002 | 1 か所。点の `geometry` を持つ |
| `runways` | 48,203 | 1 本の滑走路。両端の座標 |
| `navaids` | 11,008 | 1 つの無線施設。点の `geometry` |
| `countries` | 249 | 国 |
| `regions` | 3,987 | 第 1 階層の地域。ISO 3166-2 風のコード |
| `airport_frequencies` | 30,343 | 周波数 |
| `airport_comments` | 16,406 | 利用者のコメント |

## 粒度と範囲

| 項目 | 値 |
|---|---|
| 単位 | 1 か所 (点)。面は無い |
| 空間範囲 | 全世界。米国が 32,643 件で 38% |
| 時点 | 2026-08-31。各行がいつ更新されたかは分からない |
| CRS | `geometry` の CRS 名は `OGC:CRS84` (経度、緯度) |
| ライセンス | public domain。表示は任意 |

## Natural Earth との結合

CRS の名前が違うので、そのままでは空間結合できない。 Natural Earth は `EPSG:4326`、こちらは `OGC:CRS84`。DuckDB 1.5 は `ST_Intersects` を拒んでエラーにする。どちらも経度、緯度の順の WGS 84 なので、名前だけ揃えればよい。

```sql
select * replace (ST_SetCRS(geometry, 'EPSG:4326') as geometry) from airports
```

コードで結ぶなら `iso_country` (2 文字) を Natural Earth の `ISO_A2_EH` と結ぶ。247 種のうち 237 種が一致する (2026-10-10 実測)。一致しないのは:

- フランスの海外県 (`GF`、`RE`、`GP`、`MQ`、`YT`)。Natural Earth の国の面ではフランスに含まれる
- `BQ`、`CC`、`CX`
- `XP`: 南シナ海の西沙諸島の施設。係争地
- `ZZ`: `Non-Existent Airport` のような架空の行

点を Natural Earth の 10m の国の面に入れ、入らなければ 5 km 以内の最寄りの国に割り当てた結果 (spatial-data-integration の `assign_points.py`、2026-10-10):

| 区分 | 件数 | `iso_country` と一致 |
|---|---:|---:|
| 国の面に入った | 82,847 | 82,433 (99.5%) |
| 2 つ以上の面に入った | 0 | |
| 5 km 以内の最寄りの国 | 2,327 | 2,295 (98.6%) |
| 割り当たらない | 828 | |

最寄りに割り当てた距離は中央値 0.64 km、90% 点 2.72 km。面から外れた点には海岸の大空港 (ジェノバ、ポートサイド、トロムソなど) が入る。10m の海岸線では埋立地が海になるため。割り当たらない 828 件のうち 540 件はヘリポート。点を国に割り当てるなら、面への包含だけでなく `iso_country` も使い、食い違いを数えて報告する。

## 気をつけること

ほとんどが空港ではない。 `type` は small_airport 42,707、heliport 23,196、closed 13,482、medium_airport 4,109、seaplane_base 1,273、large_airport 1,172、balloonport 63。旅客の空港を数えるなら `type in ('large_airport', 'medium_airport') and scheduled_service = 'yes'` で絞る。この条件で 3,268 件。日本は 3,747 件のうち 3,040 件がヘリポート。

コードは目安。 IATA コードは 9,057 件、ICAO コードは 10,473 件にあるが、利用者が入力したもので、IATA の登録簿と照合されていない。

型は列名で決めてある。 `regions.local_code` の `02` は文字列のまま。自分で CSV を読み直すと数値の 2 になる。
