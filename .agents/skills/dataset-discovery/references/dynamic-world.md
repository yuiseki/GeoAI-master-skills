---
kind: dataset
id: google-wri/dynamic-world-v1
description: Sentinel-2 の 1 シーンごとに、10 m の画素が 9 つの土地被覆のどれにあたるかの確率とラベルを付けた、全世界の分類済みの土地被覆。Google と World Resources Institute が作り、ほぼ実時間で増える。Google Earth Engine の中でしか配られていない。このカードは配布元の説明から書き、中身は実測していない。
url: https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_DYNAMICWORLD_V1
license: CC-BY-4.0。表示は Dynamic World Project (Google、National Geographic Society、World Resources Institute) と、「Contains modified Copernicus Sentinel data [2015-present]」。データのライセンスとは別に、Earth Engine の利用条件が要る (非商用は無料、商用は有料)
formats:
- Earth Engine の ImageCollection (GOOGLE/DYNAMICWORLD/V1)。GeoTIFF などへは Earth Engine から書き出す
crs: シーンごとの UTM (Sentinel-2 の格子)。未確認
spatial_coverage: 全世界の陸域のうち、Sentinel-2 L1C の雲が 35% 以下のシーン。雲と雲の影の画素は無い
temporal_coverage: 2015-06-27 から、ほぼ実時間で増える (2026-10-16 に読んだカタログでは 2026-10-15 まで)。同じ場所に 2〜5 日おき (緯度による)
as_of:
  catalog_read: 2026-10-16
contents:
- 9 つの土地被覆の確率 (water、trees、grass、flooded_vegetation、crops、shrub_and_scrub、built、bare、snow_and_ice)。合計は 1
- label: 確率が最も高い土地被覆の番号 (0〜8)
- 画像の属性: dynamicworld_algorithm_version、qa_algorithm_version
tables:
- name: images
  read: ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
  grain: Sentinel-2 L1C の 1 シーンの、10 m の 1 画素。画像の名前は元の Sentinel-2 L1C の名前と同じ
  rows: null
  id: []
  columns:
  - name: label
    type: 整数 (0〜8)
    meaning: 0 water、1 trees、2 grass、3 flooded_vegetation、4 crops、5 shrub_and_scrub、6 built、7 bare、8 snow_and_ice
  - name: water ... snow_and_ice
    type: 小数 (0〜1)
    meaning: 各土地被覆の確率の推定。9 つの合計が 1
---

# Dynamic World (dynamic-world)

Sentinel-2 のシーンが 1 枚撮られるたびに、その 10 m の画素ごとに、9 つの土地被覆の確率を深層学習のモデルで推定したもの。Google と World Resources Institute が作り、National Geographic Society が協力した。年に 1 回の土地被覆の地図と違い、シーンごとの予測が積み重なる。洪水、雪、火災の跡のような短い変化も、撮られた日の予測に現れる。

このリポジトリでは、分類済みの土地被覆の地図として使う。画素の確率やラベルを、点、格子、行政区に集計する入力になる。Sentinel-2 のバンドの値から土地被覆を推定し直す処理は扱わない。

このカードは、配布元 (Earth Engine のカタログ、dynamicworld.app、論文) の説明から書いた。行の数、値の分布、座標系は実測していない (未確認)。使う前に、使う範囲と期間で、画像の枚数、label の内訳、確率の分布、雲で欠ける画素の割合を測って、ここに足す。

## どこから読むか

Google Earth Engine の中でしか配られていない (2026-10-16 に調べた範囲で、Earth Engine の外のまとまった配布は見つからなかった)。

```python
import ee
ee.Initialize(project="自分の Google Cloud のプロジェクト")
dw = (ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
      .filterBounds(ee.Geometry.Point(139.76, 35.68))
      .filterDate("2024-01-01", "2025-01-01"))
print(dw.size().getInfo())
```

- Earth Engine を使うには、登録した Google Cloud のプロジェクトと認証 (`earthengine authenticate`) が要る。非商用 (個人、研究、教育、非営利) は無料で、商用と政府の業務は有料 (Earth Engine の非商用の条件のページ、2026-10-16)。データの CC BY 4.0 とは別の条件。
- 地図で見るだけなら <https://dynamicworld.app/explore>。
- 手元で集計するなら、期間で集約した画像を、範囲を絞って GeoTIFF に書き出す (`ee.batch.Export.image.toDrive` など)。書き出した日、範囲、集約の方法、`dynamicworld_algorithm_version` を書いておく。

論文: Brown, C.F., Brumby, S.P., Guzder-Williams, B. ほか、"Dynamic World, Near real-time global 10 m land use land cover mapping"、Scientific Data 9, 251 (2022)、doi:10.1038/s41597-022-01307-4。学習に使ったラベル付きの画像は PANGAEA (doi:10.1594/PANGAEA.933475) にあるが、土地被覆の地図そのものではない。

## 気をつけること

- 1 枚の画像は、1 つのシーンの予測。ある期間の土地被覆の地図にするには、期間の中の画像を集約する (label の最頻値、確率の平均など)。集約の方法と期間で、各土地被覆の面積は変わる。方法を書き、2 通り以上で比べる。
- 雲が 35% を超えるシーンは予測が無く、雲と雲の影の画素は欠ける (配布元の説明)。雲の多い地域と季節は、画像が少ない。期間ごとの画像の枚数と、欠けた画素の割合を数える。
- 1 枚の画像と狭い窓で予測しているので、時間の変化で決まる土地被覆 (crops) は確率が低く出やすい。乾いた明るい地面、砂、水面の照り返しも確率が低い (配布元の説明)。配布元は、最も高い確率にしきい値をかけて、自信のある画素を選ぶことを勧めている。しきい値を変えると結果がどう変わるかを見る。
- label は確率の最も高い番号で、確率の差が小さくても 1 つに決まる。確率のバンドを並べて見る。
- モデルの版 (`dynamicworld_algorithm_version`) が途中で変わると、同じ場所の土地被覆が、変化が無くても変わりうる (推測、未確認)。長い期間を比べるなら、版ごとに画像の数を数える。
- built (建物などで覆われた所) は、行政の都市の範囲や人口の多さとは別のもの。都市化度の代わりにしない。
