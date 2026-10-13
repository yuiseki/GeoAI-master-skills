# WorldPop 日本の凍結版 (worldpop-jp-2026-01)

WorldPop の日本の人口の格子 (2015〜2030 年、版 R2025A) の凍結版。100 m と 1 km の総人口、1 km の性別と 5 歳階級ごとの人口、都市化度。WorldPop が出した元の GeoTIFF と、値を変えずに作った COG (範囲だけを読める) を、1,024 ファイルで持つ。
`README.md` の目録 (STAC) では、配布元がファイルを丸ごとしか返さないので、日本だけを使うならこちらを読む。

## どこから読むか

Hugging Face の `yuiseki/worldpop-jp-2026-01`。

- カード: <https://huggingface.co/datasets/yuiseki/worldpop-jp-2026-01>
- `parquet/files.parquet` が 1,024 ファイルの一覧 (2026-10-13 に 1,024 行を実測)。製品、年、解像度、性別、年齢、パス、大きさ、sha256、有効な画素の数、画素の合計 (`sum`) を持つ。ラスタを開かずに、年ごとの人口が引ける。
- 元のファイルは `raw/GIS/...`、COG は `cog/GIS/...` (同じパス)。Hub が Range 要求に答えるので、`/vsicurl/` や rasterio で窓だけを読める。

```sql
-- 年ごとの 80 歳以上の人口 (性別が total の行だけ)
select year, round(sum("sum")) as people
from 'hf://datasets/yuiseki/worldpop-jp-2026-01/parquet/files.parquet'
where project = 'Age and Sex Structures' and sex = 'total' and age_from >= 80
group by year order by year;
```

## 中身

2026-10-13 に実測した (`files.parquet`)。

| 製品 (`project`) | 解像度 | ファイル数 | 1 年あたり |
|---|---|---:|---|
| `Population` (総人口) | 100 m と 1 km | 32 | 各 1 |
| `Age and Sex Structures` | 1 km | 960 | 60 (女、男、total の 3 通り × 20 階級) |
| `Degree of Urbanisation` | (1 km の格子) | 32 | 2 (レベル 1 と 2) |

年齢の階級は、0 (1 歳未満)、1 (1〜4 歳)、5、10、……、85、90 (90 歳以上) (カードによる)。2020 年の 100 m の COG は 37,258 × 25,773 画素、約 131 MB。

| 項目 | 値 |
|---|---|
| CRS | EPSG:4326 (経度、緯度。WorldPop の GeoTIFF のとおり) |
| 時点 | 2015〜2025 は推計、2026〜2030 は予測。版 R2025A の v1。ファイルは 2026-09-28 に取得して sha256 を記録してある |
| ライセンス | CC BY 4.0。製品ごとに DOI を挙げて引用する (カードの `LICENSE` に 4 つある) |

## 気をつけること

- 合計が重なる。`files.parquet` の `sum` を年で足すとき、解像度と性別で絞らないと、同じ人を重ねて数える。2020 年の `Population` を絞らずに足すと、100 m と 1 km で 2 倍の 253,149,706 になる。100 m だけなら 126,574,853。`Age and Sex Structures` は、`sex = 'total'` に絞って 126,475,186 で、絞らないと 252,950,372 (2 倍)。
- 総人口と年齢性別の合計は一致しない。2020 年で、60 枚の年齢性別の合計が 126,475,186、1 km の総人口が 126,574,853 で、0.08% 違う。別のモデルなので、どちらかに揃えてから使う。
- 令和 2 年国勢調査の 126,146,099 人 (`jp-admin-2026-09`) とも、約 0.3% 違う。WorldPop は推計で、公式の人口ではない。
- 画素は度で切ってあるので、高緯度ほど画素の面積が小さい。密度にするなら、画素の面積で割る。
- 都市化度は階級のコード。拡大縮小の概観 (オーバービュー) は最近傍で作ってあるが、自分で再標本化するときは、平均を取らない。
- rasterio で読むときは、anaconda の `GDAL_DRIVER_PATH`、`GDAL_DATA`、`PROJ_DATA` を外す (`README.md` と同じ落とし穴)。

## ほかのデータとの結合

- 画素の合計を市区町村に集める (ゾーナル統計) なら、面は `jp-admin-2026-09` を使う。面の座標系は `EPSG:4612` で、ラスタの `EPSG:4326` と名前が違うが、日本では差は画素の大きさ (100 m) より小さい。
