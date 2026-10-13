---
kind: catalog
id: planetary-computer
description: Microsoft Planetary Computer の、衛星画像、標高、土地被覆などのラスタの目録。STAC API で範囲と時期から item を探し、COG を Range で読む。
url: https://planetarycomputer.microsoft.com/api/stac/v1
access: 検索 (POST /search) は認証なし。ファイルは、匿名で取れる SAS トークンを URL に付けないと 409 になる (アカウント不要)
license: コレクションごとに違う。collection の license と、その link の先を読む
crs: コレクションごとに違う
spatial_coverage: 全世界
temporal_coverage: コレクションごと
as_of:
  checked: 2026-10-10
contents:
- Sentinel-2 L2A
- Landsat C2 L2
- HLS
- NASADEM
- ESA WorldCover
- 土地被覆
- 標高
---

# Microsoft Planetary Computer

衛星画像、標高、土地被覆などのラスタの目録。STAC API で範囲と時期から item を探し、COG を Range で読む。

この目録の中のコレクションごとのファイルはまだ書いていない。以前の調査で調べたもの (Sentinel-2 L2A、Landsat C2 L2、HLS、NASADEM) と、下で読めることを確かめたものが候補 (TODO.md)。

## 目録の引き方

STAC API `https://planetarycomputer.microsoft.com/api/stac/v1`。検索 (`POST /search`) は認証なしで通る。

```sh
curl -X POST https://planetarycomputer.microsoft.com/api/stac/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"collections": ["esa-worldcover"], "bbox": [139.7, 35.6, 139.8, 35.7], "limit": 1}'
```

## ファイルを読むには署名が要る (アカウントは要らない)

item の asset の URL (Azure Blob Storage) をそのまま読むと、409 `PublicAccessNotPermitted` が返る。匿名で取れる SAS トークンを URL に付けると読める。アカウントも鍵も要らない。

2026-10-10 に、東京付近の bbox で各コレクションの 1 item を検索し、最初の GeoTIFF の asset に Range 要求 (先頭 1,024 バイト) を投げた。

| コレクション | 署名なし | コレクション名のトークン | ストレージの置き場所 |
|---|---|---|---|
| sentinel-2-l2a | 409 | 206 | sentinel2l2a01 |
| landsat-c2-l2 | 409 | 206 | landsateuwest |
| hls2-s30 | 409 | 206 | hls2euwest |
| nasadem | 409 | 206 | nasademeuwest |
| esa-worldcover | 409 | 206 | ai4edataeuwest |
| io-lulc-annual-v02 | 409 | 206 | ai4edataeuwest |
| cop-dem-glo-30 | 409 | 403 | elevationeuwest/copernicus-dem |

署名の仕方は 3 つある。

| 方法 | URL | 向いているとき |
|---|---|---|
| コレクション名のトークン | `https://planetarycomputer.microsoft.com/api/sas/v1/token/<コレクション>` | 1 つのコレクションの多数のファイル。ただし cop-dem-glo-30 では 403 で、効かないコレクションがある |
| 置き場所のトークン | `https://planetarycomputer.microsoft.com/api/sas/v1/token/<ストレージのアカウント>/<コンテナ>` | URL の `https://<アカウント>.blob.core.windows.net/<コンテナ>/...` から作れる。cop-dem-glo-30 でも 206 |
| URL ごとの署名 | `https://planetarycomputer.microsoft.com/api/sas/v1/sign?href=<URL エンコードした href>` | 少数のファイル。cop-dem-glo-30 でも 206 |

- トークンは `?` の後ろに付ける。応答の `msft:expiry` が有効期限で、切れたら取り直す。
- Python なら `planetary-computer` パッケージの `sign` が同じことをする (ここでは使っていない)。
- 長い処理では、途中で期限が切れる。ファイルを開くたびに署名し直すか、期限の前に取り直す。

## ライセンス

コレクションごとに違う。collection の `license` と、その link の先の本文を読む。以前の調査の記録では、NASADEM は `proprietary` で LP DAAC の引用の方針へのリンク、Sentinel-2 は Copernicus Sentinel data の条件 (本文は未確認)。
