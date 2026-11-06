---
kind: catalog
id: jaxa-earth
description: JAXA Earth API の目録。JAXA と関連機関の地球観測データ 119 コレクション (STAC の root から辿れるのは 112) を、STAC の静的な JSON と COG で配る。登録も API キーも要らない。
url: https://data.earth.jaxa.jp/stac/cog/v1/catalog.json
access: 静的な STAC の JSON を root から辿り、COG を HTTP の Range で読む。登録、API キー、回数制限なし (2026-11-05 時点のサイトの記載)。Python と JavaScript のクライアントもある
license: STAC の license 欄は全コレクション proprietary。条件は各コレクションの rel=license のリンク先。root の 112 件のうち 103 件は JAXA の研究データ等の利用条件 (出所表示で改変と第三者配布可、商用は事前に JAXA へ連絡)。NASA LP DAAC の 8 件と ESA CCI の 1 件は元の配布元の条件
crs: STAC の proj:epsg が正。110 件が EPSG:4326、南極の海氷が EPSG:3031、北極が EPSG:3995。GeoTIFF 自体に CRS が入っているかはコレクションで違う (GSMaP の月別は無し、AW3D30 v4.1 は有り)
spatial_coverage: 全球が中心。日本だけのコレクション (高解像度土地利用土地被覆図、GCOM-C の 250 m 地表面温度、Today's Earth - Japan の河川と氾濫原) もある
temporal_coverage: コレクションごと。2000 年からの GSMaP 降水、2012 年からの AMSR2、2018 年からの GCOM-C など。更新が続くものと、平年値 (normal) のものがある
as_of:
  checked: 2026-11-05
  ai_catalog_last_update: 2026-07-01
contents:
- ALOS の AW3D30 (DSM、v3.2 と v4.1)
- ALOS-2 PALSAR-2 の森林・非森林図
- 日本の高解像度土地利用土地被覆図 (2020、2022、2024)
- GSMaP の降水 (時別、日別、半月、月、平年値)
- GCOM-C SGLI の地表面温度、海面水温、クロロフィル a、植生指数、蒸発散
- GCOM-W AMSR2 の海面水温、土壌水分、海氷密接度
- MODIS の地表面温度、植生指数、エアロゾル、日射 (JASMES と NASA)
- 気象庁 COBE-SST の平年値、Copernicus の土地被覆 (2019)
- Today's Earth - Japan の時別の河川流量、河川水深、氾濫原の水深と浸水面積率 (2019-11 から。root からはリンクされていない)
---

# JAXA Earth API

JAXA 地球観測研究センター (EORC) が、自分のデータと関連機関のデータを COG に直して配っている目録。入口は STAC の root の 1 ファイルで、そこからリンクを辿ると、どのコレクションのどの日付のどのタイルの COG にも着く。サーバー側の処理は無く、全部が静的なファイルなので、登録も API キーも要らない。

```text
https://data.earth.jaxa.jp/stac/cog/v1/catalog.json
```

AI 向けのデータカタログ ([catalog.v2.md](https://data.earth.jaxa.jp/app/mcp/catalog.v2.md)) は、コレクションごとに ID、`collection.json` の URL、題名、バンド名、bbox、解像度 (km)、期間、時間分解能を Markdown で並べたもの。コレクションを選ぶときは先にこれを読む。最終更新は 2026-07-01 なので、期間や最新の日付は STAC で確かめる。

2026-11-05 に突き合わせると、catalog.v2.md の 119 件は STAC の root の子 112 件をすべて含み、さらに Today's Earth - Japan の 7 件 (`JAXA.UTokyo_TE_MSM.*.v2_japan_hourly`) が root に無かった。この 7 件の `collection.json` は実在し、同じ形で辿れる (例: 氾濫原の水深 `FLDDPH`、日本の bbox、1/60 度のモデルを 90 ppu に、2019-11-29 から時別、JAXA の利用条件)。STAC の root だけを歩くと見落とす。全体を数えるときは catalog.v2.md の ID も合わせる。

[サイトのトップ](https://data.earth.jaxa.jp/ja/)、[データセット一覧](https://data.earth.jaxa.jp/ja/datasets/index.html)、[ご利用条件](https://data.earth.jaxa.jp/ja/#license)。

## STAC の辿り方

2026-11-05 に root の catalog.json (24,479 バイト) を読んだ。子 (rel=child) は 112 件で、各コレクションの `collection.json` を指す。コレクションは Wasabi の S3 (`s3.ap-northeast-1.wasabisys.com/je-pds/cog/v1/`) に置かれている。

階層は次の 5 段。GSMaP の月別降水 (`JAXA.EORC_GSMaP_standard.Gauge.00Z-23Z.v6_monthly`) で、2026-10 の COG まで辿った。

| 段 | ファイル | 中身 |
|---|---|---|
| コレクション | `<ID>/collection.json` | 説明、引用 (cite-as)、ライセンスのリンク、`summaries` (`je:cog_level_max`、`je:ppu_max`、`je:epsg`、`je:stac_date_format`)。子は日付 |
| 日付 | `<ID>/<日付>/catalog.json` | 書式は `je:stac_date_format` (`YYYY`、`YYYY-MM`、`YYYY-MM/DD`、`YYYY-MM/DD-hh`、平年値は `MM` や `MM-DD`)。月別 GSMaP は 2000-03 から 2026-10 まで 320 件。子はレベル |
| レベル | `<日付>/<n>/catalog.json` | 0 が最も粗い。番号が 1 上がるとタイルの幅が半分、画素が 2 倍細かくなり、`je:cog_level_max` で最も細かい `je:ppu_max` (1 度あたりの画素数) に届く。子は経度の帯 |
| 経度の帯 | `<n>/E090.00-E180.00/catalog.json` | 子 (rel=item) は緯度で切ったタイルの item |
| item | `.../N00.00-N90.00.json` | `assets` にバンド名をキーにした COG の相対 URL、`properties` に期間と `proj:epsg` |

月別 GSMaP のレベル 0 は 180 度角のタイルが 2 枚で 0.2 度 (900 × 900 画素、オーバービューは 2 段)。レベル 1 は 90 度角が 8 枚で 0.1 度 (900 × 900 画素)、これが `je:ppu_max` = 10 に当たる。解析には最も細かいレベルを使い、粗いレベルは表示か下見に使う。

```text
https://s3.ap-northeast-1.wasabisys.com/je-pds/cog/v1/JAXA.EORC_GSMaP_standard.Gauge.00Z-23Z.v6_monthly/2026-10/1/E090.00-E180.00/E090.00-N00.00-E180.00-N90.00-PRECIP.tiff
```

この COG は Range 要求に 206 を返し、rasterio で関東 (東経 138.5〜141.0 度、北緯 34.5〜36.5 度) の窓だけを読めた。float32、DEFLATE、256 × 256 のブロック、nodata は -999.9。

## つまずきやすい点

- GeoTIFF に CRS が入っていないコレクションがある。月別 GSMaP の COG は、rasterio で開くと `crs` が `None` になる。AW3D30 v4.1 の COG には EPSG:4326 が入っていた (2026-11-06)。どちらでも、STAC の item の `proj:epsg` (またはコレクションの `je:epsg`) を正として付ける。付けずに他のラスタと重ねると、黙ってずれるか、失敗する。
- レベル 0 の COG のオーバービューは、`OVV_RESAMPLING=MODE` (最頻値) で作られている。降水や温度のような連続量の粗いオーバービューは平均ではない。量を集計するときは、最も細かいレベルの画素から自分で集計する。
- タイルは緯度 ±90 度まで切られていても、データの範囲はコレクションの bbox まで。GSMaP は南北 60 度までで、その外は nodata。
- コレクションの `id` は、112 件のうち 62 件で文字列 `collection` になっている。コレクションの識別には、root の子の URL のディレクトリ名 (= AI 向けデータカタログの id) を使う。
- item の `properties` は期間を正しく表さないことがある。月別 GSMaP の 2026-10 の item は、`start_datetime` が 2026-10-01T00、`end_datetime` が 2026-10-01T23 だった。月の値かどうかは、日付のディレクトリとコレクションの時間分解能で判断する。`updated` には文字列の `"null"` が入っていた。
- 更新が続くコレクションは、最新の月や日が後から作られる。2026-10 の月別 GSMaP の item は 2026-11-03 に作られていた (`created`、COG の Last-Modified も同じ日)。再現が要るときは、COG の URL、ETag、Last-Modified を記録する。JAXA は「将来予告なく仕様変更、または公開終了する場合がある」と書いている。
- 単位はバンド名から読めず、STAC にも無い。catalog.v2.md は題名や説明に書くことがある (蒸発散の `[mm/day]`、Today's Earth の `unit: m` など) が、GSMaP は「Precipitation Rate」とあるだけで単位が無い。月別 GSMaP の関東の窓の平均は 0.113 だった。mm/h の月平均なら 10 月の 744 時間で約 84 mm で、桁は合う。単位は元製品の資料で確かめてから使う。

## クライアント

Python の `jaxa-earth` (PyPI、2026-11-05 時点で 0.1.6) と JavaScript のモジュールがある。どちらも上の STAC と COG を読むだけなので、使わなくても rasterio や GDAL の `/vsicurl/` で直接読める。

```sh
systemd-run --user --scope -q -p MemoryMax=2G -p MemorySwapMax=0 -- \
  uvx --with rasterio python -I read_cog.py <COG の URL>
```

## ライセンス

[JAXA Earth API のご利用条件](https://data.earth.jaxa.jp/ja/#license) (2026-11-05 確認):

- 登録、API キー、回数制限は無い。API のモジュールは無償で使え、オープンソースのモジュールは改変できる。
- データのライセンスは、各データの STAC に書かれた条件に従う。
- API を使って作った結果を論文やウェブサイトで公表するときは、その旨を書く (例: 「本データは JAXA Earth API を使用して取得したものです」)。
- 現状有姿で、正確性や継続を保証しない。

STAC の `license` は 112 件とも `proprietary` で、実際の条件は rel=license のリンク先にある。root の 112 件のリンク先の内訳は、`https://earth.jaxa.jp/en/data/policy/` が 71 件、`https://earth.jaxa.jp/policy/` が 32 件、`https://lpdaac.usgs.gov/data/data-citation-and-policies/` が 8 件 (NASA の MODIS の地表面温度)、ESA CCI の土地被覆のページが 1 件 (Copernicus の土地被覆)。JAXA の条件を指す 103 件には、`NASA.EOSDIS` で始まる 6 件と気象庁の COBE-SST の平年値 1 件も含まれる。ID の接頭辞でなく、リンク先で条件を決める。

JAXA の[研究データ等の利用条件](https://earth.jaxa.jp/ja/data/policy/)は、出所表示 (JAXA と研究名、例: 「Credit: GSMaP (JAXA)」) を条件に、改変と第三者への配布 (二次的著作物の公表を含む) を認めている。JAXA 以外の機関のデータを含むものは、その機関も表示する (例: 「JAXA/NASA」)。商用利用は無償で可能だが、事前に JAXA への連絡が要る。サイトのご利用条件の「商用利用も可能です」だけを読んで、連絡を省かない。

固定版を Hugging Face などに置き直すことは、JAXA の利用条件のコレクションなら出所表示の条件で認められる (2026-11-05 の読み)。NASA と ESA のコレクションは、それぞれの条件を読んでから判断する。

## 既存の reference との関係

[jaxa-aw3d30](../jaxa-aw3d30.md) は、ログインが要る公式の配布 (1 度タイルの GeoTIFF) を指している。同じ AW3D30 は、ここで v3.2 と v4.1 (2024-04 公開) が登録なしの COG で読める (`JAXA.EORC_ALOS.PRISM_AW3D30.v4.1_global`、`je:ppu_max` = 3600、1 秒角)。最も細かいレベル (3) は 1 度角のタイルで、`2024-04/3/E139.00-E140.00/E139.00-N35.00-E140.00-N36.00-DSM.tiff` のように経度の帯と緯度で引ける (int16、nodata -9999、EPSG:4326 が入っていた)。2026-11-06 に、この COG を 2 タイル分つないで UTM 54N の 30 m にし、相模川のダムの流域を切った。山地の流域には使えたが、DSM なので湖の面が平らにならず、山中湖が深い窪地に見えた。item の assets は `DSM` と `MSK` の 2 つで、STK、QAI、元画像の一覧は無い。観測時点の監査に STK や元画像の一覧が要るときは公式の配布を使う。
