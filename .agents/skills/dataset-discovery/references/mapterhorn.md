---
kind: dataset
id: mapterhorn/terrain
description: 全世界の標高のラスタタイル。各国の公開 DEM (151 の配布元) と Copernicus GLO-30 を合わせ、Terrarium の符号化で 512 画素の可逆 WebP にしたもの。z0〜12 は 1 つの PMTiles (planet.pmtiles)、z13 以上は地域ごとの PMTiles、1 枚ずつ読むタイルの入口もある。ベクトルタイルではない。
url: https://mapterhorn.com/data-access/
license: 配布元ごとに違う (151 の配布元。CC BY 4.0 系が最も多く、ほかに米国政府の著作物、Licence Ouverte 2.0、Datenlizenz Deutschland、Copernicus のライセンス、国土地理院コンテンツ利用規約と測量法の承認など)。一覧は https://download.mapterhorn.com/attribution.json 。表示は「© Mapterhorn」と、使う範囲の配布元
formats:
- PMTiles (タイルは 512 × 512 画素の可逆 WebP、Terrarium)
- XYZ のタイル (https://tiles.mapterhorn.com/{z}/{x}/{y}.webp)
crs: EPSG:3857 のタイルの画素 (値は画素の標高)
spatial_coverage: 全世界 (北緯、南緯 85.05 度まで)。z13 以上は、細かい DEM のある地域だけ。海は 0 (海底の地形は入っていない)
temporal_coverage: 配布元の DEM の取得年はまちまち (2025〜2026 年に取得)。版は 0.0.13 (2026-10-16 に読んだ download_urls.json)
as_of:
  fetched: 2026-10-16
  version: 0.0.13
contents:
- 標高 (m)。Terrarium の符号化 (R × 256 + G + B / 256 - 32768)
- 配布元ごとの名前、ライセンス、解像度 (0.25〜30 m)、元のデータの tar の場所 (attribution.json)
tables:
- name: planet
  read: https://download.mapterhorn.com/planet.pmtiles
  grain: ズーム 0〜12 のタイルの 1 画素 (z12 で、赤道の Web メルカトルで約 19.1 m)
  rows: null
  id:
  - z
  - x
  - y
  columns:
  - name: rgb
    type: WebP (RGB)
    meaning: Terrarium で符号化した標高。R × 256 + G + B / 256 - 32768 で m に直す
- name: regional
  read: https://download.mapterhorn.com/{z6}-{x6}-{y6}.pmtiles (一覧は https://download.mapterhorn.com/download_urls.json)
  grain: ズーム 13 以上 (最大 18) のタイルの 1 画素。ファイルはズーム 6 のタイル 1 枚の範囲
  rows: null
  id:
  - z
  - x
  - y
- name: planet_frozen_2026_01_06
  read: https://z.yuiseki.net/static/mapterhorn/2026-01-06/planet.pmtiles
  grain: ズーム 0〜12 のタイルの 1 画素。yuiseki の凍結した複製 (2026-01-07 取得)。上書きされないので、実験の入力にはこちらを使う
  rows: null
  id:
  - z
  - x
  - y
  columns:
  - name: rgb
    type: WebP (RGB)
    meaning: Terrarium で符号化した標高。R × 256 + G + B / 256 - 32768 で m に直す
- name: tiles
  read: https://tiles.mapterhorn.com/{z}/{x}/{y}.webp
  grain: 1 枚のタイル (512 × 512 画素)。TileJSON は https://tiles.mapterhorn.com/tilejson.json
  rows: null
  id:
  - z
  - x
  - y
---

# Mapterhorn の標高タイル (mapterhorn)

各国の公開の DEM と Copernicus GLO-30 を合わせて、全世界の標高を 1 つのタイルの集まりにしたもの。タイルは 512 × 512 画素の可逆 WebP で、色に標高を符号化している (Terrarium)。地図の陰影や 3D 表示のためのタイルとして作られているが、画素の値は標高 (m) に戻せるので、点や面に標高を付ける入力に使える。

ベクトルタイルではない。OpenStreetMap の地物は入っていない。

## どこから読むか

| 入口 | 中身 | 大きさ (2026-10-16) |
|---|---|---|
| `https://download.mapterhorn.com/planet.pmtiles` | ズーム 0〜12、全世界 | 355,579,263,191 バイト (約 356 GB) |
| `https://download.mapterhorn.com/{z}-{x}-{y}.pmtiles` | ズーム 13 以上、ズーム 6 のタイル 1 枚の範囲ごと。458 ファイル | 最大 18 まで。全部で約 9.9 TB |
| `https://tiles.mapterhorn.com/{z}/{x}/{y}.webp` | 1 枚ずつ | 1 枚 57〜164 KB (読んだ 5 枚) |
| `https://data.source.coop/mapterhorn/mapterhorn/` | 地域の PMTiles の複製 (459 のうち 156。planet は無い) | |

PMTiles は HTTP の Range で読める (planet.pmtiles とその複製で 206 が返った)。一部の範囲だけ要るなら、`pmtiles extract` で範囲を切り出すか、使うタイルだけを読む。planet.pmtiles を丸ごと落とさない。

ファイルの一覧、大きさ、md5、ズームの範囲は `download_urls.json`、配布元とライセンスは `attribution.json`、複製の状態は `mirrorstatus.json` にある。

## 凍結した複製 (z.yuiseki.net)

配布元の planet.pmtiles は上書きで更新されるので、実験の入力には yuiseki の母艦にある日付つきの複製を使う。

| 項目 | 値 (2026-10-28 に読んだ) |
|---|---|
| 入口 | `https://z.yuiseki.net/static/mapterhorn/2026-01-06/planet.pmtiles` (2026-01-07 取得)。`static/mapterhorn/planet.pmtiles` (日付なし) は 404 |
| 大きさ | 663,868,447,387 バイト。HTTP の Range に 206 で答える (HEAD に Range を付けると 200 が返るので、GET で確かめる) |
| ヘッダー | PMTiles 版 3、ズーム 0〜12、タイル WebP、タイルの圧縮なし、ディレクトリは gzip。タイルの項目 9,396,124、中身 9,318,520 |
| メタデータ | `attribution` だけ (`© Mapterhorn`)。Mapterhorn の版の番号は入っていない |

- 配布元の現行 (版 0.0.13、約 356 GB) より大きい。版が違うと値も違いうるので、使った入口と取得日を書く。
- 東北のブナの 98 地点で、ズーム 12 の標高と Dryad の地点の標高 (Altitude) を照合した結果は、`projects/_bear/beech-masting-spatial-proxy/outputs/terrain_audit.json` (GeoAI-master-skills) にある。

## 測ったこと

2026-10-16 に、`tiles.mapterhorn.com` のタイルを 5 枚読み、Terrarium の式で m に直した。

| 場所 | ズーム | その点の値 | 近く (7 × 7 画素) の最大 | 比べる値 |
|---|---:|---:|---:|---|
| 富士山の山頂 | 12 | 3,771.00 | 3,771.00 | 公称 3,776 m |
| 富士山の山頂 | 15 | 3,770.25 | 3,774.50 | 公称 3,776 m |
| 東京湾 | 10 | 0.00 | 0.00 | 海は 0。同じタイルの最小は -6.0 (海面より低い陸) |
| 死海 | 10 | -432.00 | -432.00 | 湖面は海面下 430 m ほど |
| エベレスト | 12 | 8,718.00 | 8,733.00 | 公称 8,849 m。タイル全体の最大も 8,735.5 |

- 値は丸められている。ズーム 10 と 12 は 1 m 単位、ズーム 15 は 0.25 m 単位だった (読んだタイルで)。
- 低いズームの画素は広いので、峰の頂は低く出る。エベレストはズーム 12 で 100 m 以上低い。山頂の高さや斜面の傾きを測るなら、使うズームを書き、細かいズームと比べる。
- 標高の基準 (楕円体高か、どの geoid の高さか) は、配布元ごとに違いうる。確かめていない (未確認)。

## 配布元とライセンス

`attribution.json` に 151 の配布元がある。解像度は 0.25〜30 m。全世界の下地は Copernicus GLO-30 (30 m) で、細かい DEM のある国や地域では、その DEM が使われる。

日本の範囲は、国土地理院の基盤地図情報の数値標高モデル (1 m、5 m、10 m) で、配布元は「国土地理院コンテンツ利用規約／測量法に基づく国土地理院長承認（使用）R 8JHs 131」と書いている。日本の範囲を加工して配り直すときの手続きは確かめていない (未確認)。日本向けの版として、source.coop の `smartmaps/mapterhorn-japan-bridge` (Terrarium の WebP) もある。

ライセンスは配布元ごとに違う。結果を公開するなら、使った範囲の配布元を `attribution.json` から引き、その表示を添える。

## 気をつけること

- Python の `urllib` の既定の User-Agent では、タイルの入口が 403 を返した (curl では 200)。User-Agent に自分の名前を付けて読む。
- タイルは Web メルカトルの格子。画素は地上で正方形ではなく、緯度が上がるほど東西に縮む。画素の位置の計算は gsi-dem-tiles のカードと同じ (タイルの幅が 256 でなく 512)。距離や傾きは、メートルの座標系に移してから測る。
- 版は `download_urls.json` の `version` で分かる。上書きで更新されるので、使った版と日付を書き、使ったタイルは手元に保存する。
- WebP を読むには Pillow などが要る。可逆なので、画素の値はそのまま使える。
