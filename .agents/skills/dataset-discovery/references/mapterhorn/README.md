---
kind: catalog
id: mapterhorn
description: Mapterhorn の全世界標高タイル目録。各国の公開 DEM (151 の配布元) と Copernicus GLO-30 を合わせ、Terrarium 符号化の可逆 WebP (512 画素) で PMTiles (planet.pmtiles と 458 の地域別 PMTiles) および zxy エンドポイントとして配る。
url: https://mapterhorn.com/data-access/
access: HTTP の Range 要求で PMTiles (planet.pmtiles、地域別 PMTiles) から切り出し (pmtiles extract) または直接タイル取得。単一タイルは https://tiles.mapterhorn.com/{z}/{x}/{y}.webp 。User-Agent 必須
license: 配布元ごとに違う (151 の配布元。CC BY 4.0 系、米国政府著作物、Licence Ouverte 2.0、Datenlizenz Deutschland、Copernicus、国土地理院コンテンツ利用規約等)。一覧は https://download.mapterhorn.com/attribution.json 。表示は「© Mapterhorn」と使用地域の配布元
crs: EPSG:3857 のタイルの画素 (値は画素の標高)
spatial_coverage: 全世界 (北緯・南緯 85.05 度まで)。z13 以上は細かい DEM のある地域のみ。海は 0
temporal_coverage: 配布元の DEM 取得年はまちまち (2025〜2026 年)。版は 0.0.13 (2026-10-16 / 2026-11-06 確認)
as_of:
  checked: 2026-11-06
  version: 0.0.13
contents:
- 全世界標高タイル (Terrarium 符号化可逆 WebP、512 × 512 画素)
- ズーム 0〜12 全球アーカイブ (planet.pmtiles、約 355.6 GB)
- ズーム 13〜18 地域別アーカイブ (ズーム 6 ごと 458 ファイル、計約 8.9 TB)
- 単一タイル HTTP エンドポイントおよび TileJSON
- 配布元メタデータ (attribution.json、151 提供元)
- ダウンロード URL リスト (download_urls.json、459 ファイル)
- ミラー状態 (mirrorstatus.json)
children:
- terrain.md
---

# Mapterhorn 目録 (mapterhorn)

各国の公開 DEM（151 提供元）と Copernicus GLO-30 を統合し、全世界の標高を 512 × 512 画素の可逆 WebP（Terrarium 符号化: $R \times 256 + G + B / 256 - 32768$）でタイル化したプロジェクト。Cloudflare（R2 Object Storage、Workers）の支援を受けて配布されている。

ベクトルタイルではなく、標高のラスタタイルである。

| ファイル | 種別 | 中身 |
|---|---|---|
| [terrain.md](terrain.md) | dataset | 全世界標高ラスタタイル (`mapterhorn/terrain`)。`planet.pmtiles`、地域別 PMTiles、凍結複製、HTTP タイル |

---

## 1. どこから読むか (Data Access)

公式サイトの [Data Access](https://mapterhorn.com/data-access/) では、3 系統のデータ取得方法が提供されている。

### (1) 単一タイル HTTP エンドポイント
- Tile zxy: `https://tiles.mapterhorn.com/{z}/{x}/{y}.webp`
- TileJSON: `https://tiles.mapterhorn.com/tilejson.json`
- 注意: Python の `urllib` 既定の User-Agent では 403 が返る。リクエストヘッダーに独自の User-Agent（例: `User-Agent: GeoAI-Skills/1.0`）を付与して取得する。1 タイルあたり約 50〜170 KB。

### (2) エリア切り出し (Area Extracts via `pmtiles` CLI)
対象地域（bounding box: `min_lon,min_lat,max_lon,max_lat`）のみを HTTP Range 要求で切り出してローカルの単一 PMTiles に統合できる。

```sh
# 1. Bounding Box を定義 (例: インターラーケン)
BBOX="7.74,46.60,7.96,46.75"

# 2. ズーム 0〜12 (全球) から切り出し (--dry-run で事前に容量確認可能)
pmtiles extract --bbox=$BBOX https://download.mapterhorn.com/planet.pmtiles planet.pmtiles

# 3. ズーム 13 以上 (該当地域のズーム 6 タイル) から切り出し
pmtiles extract --bbox=$BBOX https://download.mapterhorn.com/6-33-22.pmtiles regional.pmtiles

# 4. 2 つのアーカイブをマージして z0〜z17 の一貫 PMTiles を作成
pmtiles merge planet.pmtiles regional.pmtiles extract_combined.pmtiles
```

### (3) アーカイブ一括ダウンロードとミラー (Mirrors)
- 一次サーバー: `https://download.mapterhorn.com/`
- ミラー状態: `https://download.mapterhorn.com/mirrorstatus.json`（各ミラーの同期状況と URL）
- Source Cooperative: `https://data.source.coop/mapterhorn/mapterhorn/`（地域別 PMTiles のみ。planet は無し）
- 凍結複製 (z.yuiseki.net): `https://z.yuiseki.net/static/mapterhorn/2026-01-06/planet.pmtiles`（2026-01-07 取得、約 664 GB、ズーム 0〜12。配布元の現行更新に左右されない実験固定用）

---

## 2. ファイル一覧 (`download_urls.json`) と規模・注意点

全アーカイブの URL、ファイルサイズ、ハッシュ、BBox、ズーム範囲は [download_urls.json](https://download.mapterhorn.com/download_urls.json)（版 `0.0.13`）に定義されている。

### 容量とアイテム数（実測値）
- ファイルサイズ: 約 162 KB（161,912 バイト）
- 収録アイテム数: 459 アイテム（全球 `planet.pmtiles` 1 件 ＋ ズーム 6 地域別 PMTiles 458 件）
- 総容量: 9,251.72 GiB (約 9.03 TiB)
  - `planet.pmtiles`: 355,579,263,191 バイト（約 355.6 GB）、ズーム 0〜12
  - 地域別 PMTiles（458 件）: 計約 8.9 TB、ズーム 13〜18

### 地域別タイルの最大ズーム分布
| 最大ズーム | ファイル数 | 該当地域の例 |
|---:|---:|---|
| z12 | 1 | `planet.pmtiles`（全球） |
| z13 | 155 | 粗い DEM のみの地域、洋上島嶼など |
| z14 | 102 | 中解像度地域 |
| z15 | 53 | 地方部など |
| z16 | 93 | 日本全域（基盤地図情報 DEM10B/5A）、欧州など |
| z17 | 43 | アルプス山脈、北米詳細地域など |
| z18 | 12 | 超高解像度航空 LiDAR 公開地域 |

### `download_urls.json` の取り扱い上の注意
> [!CAUTION]
> `download_urls.json` は 459 件の完全な URL・MD5・座標枠を含むため、テキスト全体を不用意に LLM のプロンプトやコンテキストに読み込むと、トークン消費（数万トークン）を招く。
> 全文を読まずに、jq や Python のストリーミング・辞書引き で目的の緯度経度・地域名に絞って利用する。

#### 緯度経度から該当する地域別 PMTiles (`6-{x}-{y}.pmtiles`) を特定する計算式
ズーム 6 のタイル座標 ($x_6, y_6$) は以下の Web メルカトル変換式で求まる:

$$x_6 = \left\lfloor \frac{\text{lon} + 180}{360} \times 2^6 \right\rfloor$$

$$y_6 = \left\lfloor \left( 1 - \frac{\ln(\tan(\text{lat} \times \frac{\pi}{180}) + \sec(\text{lat} \times \frac{\pi}{180}))}{\pi} \right) \times 2^5 \right\rfloor$$

---

## 3. 日本列島をカバーする地域別 PMTiles (実測値)

日本の領域（東経 122〜154 度、北緯 20〜46 度）と交差する地域別 PMTiles は 計 22 ファイル 存在する。主要な本土カバーファイルは以下の通り:

| ファイル名 | 容量 | ズーム | 経度範囲 | 緯度範囲 | 主な対象地域 |
|---|---:|---|---|---|---|
| `6-56-25.pmtiles` | 61.11 GiB | z13–z16 | 135.00° 〜 140.62° | 31.95° 〜 36.60° | 関東・東海・近畿東部・伊豆 (東京・名古屋・京都・大阪東部) |
| `6-55-25.pmtiles` | 57.92 GiB | z13–z16 | 129.38° 〜 135.00° | 31.95° 〜 36.60° | 近畿西部・中国・四国・九州東部 (大阪西部・神戸・広島・高松・福岡) |
| `6-57-23.pmtiles` | 40.91 GiB | z13–z16 | 140.62° 〜 146.25° | 40.98° 〜 45.09° | 北海道中東部 (札幌・旭川・釧路・知床) |
| `6-56-24.pmtiles` | 37.68 GiB | z13–z16 | 135.00° 〜 140.62° | 36.60° 〜 40.98° | 東北中南部・新潟・北陸 (仙台・福島・新潟・富山・金沢) |
| `6-57-24.pmtiles` | 20.69 GiB | z13–z16 | 140.62° 〜 146.25° | 36.60° 〜 40.98° | 東北太平洋岸・関東東部沖 (八戸・三陸・銚子沖) |
| `6-56-23.pmtiles` | 7.17 GiB | z13–z16 | 135.00° 〜 140.62° | 40.98° 〜 45.09° | 青森・北海道道南 (函館・渡島半島・津軽) |
| `6-55-26.pmtiles` | 5.09 GiB | z13–z16 | 129.38° 〜 135.00° | 27.06° 〜 31.95° | 九州南部・大隅諸島 (鹿児島・宮崎・屋久島・種子島) |
| `6-54-25.pmtiles` | 0.88 GiB | z13–z16 | 123.75° 〜 129.38° | 31.95° 〜 36.60° | 九州西部・五島列島・対馬 (長崎・佐世保) |

日本の範囲の原典 DEM は国土地理院の基盤地図情報（1m、5m、10m）であり、最大ズームは `z16`（地上解像度約 2.4m）まで提供されている。

---

## 4. 配布元とライセンス (`attribution.json`)

[attribution.json](https://download.mapterhorn.com/attribution.json) には 151 の配布元が明記されている。
- 全球ベース: Copernicus GLO-30 (30m)
- 日本: 国土地理院（「国土地理院コンテンツ利用規約／測量法に基づく国土地理院長承認（使用）R 8JHs 131」）
- 成果物での帰属表示: 「© Mapterhorn」 に加え、使用範囲の元データ配布元を表示する。
