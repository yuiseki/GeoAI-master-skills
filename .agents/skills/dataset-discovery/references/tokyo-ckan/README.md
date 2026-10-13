# 東京都オープンデータカタログ (tokyo-ckan)

東京都と区市町村が CKAN で公開しているデータセットの目録。施設一覧、統計表など。yuiseki が作った非公式の STAC で、持っているのはメタデータだけ。ファイルは各組織のサイトにある。

## 目録の引き方

- 入口: `https://stac.yuiseki.net/tokyo-ckan/`
- 使い方の正本は目録の直下の `AGENTS.md` (`https://stac.yuiseki.net/tokyo-ckan/AGENTS.md`)。表から始めること、区市町村を比べるなら共通項目 (family) から入ること、推定した項目をどこまで信じるかが書いてある。まずそれを読む。
- 1 組織が 1 コレクション、1 データセットが 1 item、1 ファイルが 1 asset。
- `items.parquet` (2026-10-10 に 9,698 行) と `assets.parquet` (83,821 行) が表。`catalog.json` もある。`collections.parquet` は無い (404)。

## 気をつけること

- CKAN には場所も時刻も無いので、目録の場所と時刻は推定値。推定の根拠は `tokyo:footprint_basis` と `tokyo:datetime_basis`。場所は公開した組織の管轄区域の矩形で、データの点がその中にあるとは限らない。
- 時刻がデータの時期を表すのは、`datetime_basis` が `resource-name` か `dataset-title` のものだけ。
- 同じ名前のデータセットでも列の構成が同じとは限らない。`family_layout_match` で確かめる。
- ファイルのリンクは切れる。study-geoai-algo-py の記録では、23 区の施設一覧の CSV 194 件のうち 11 件が 2026-09-28 に 404 で、残り 183 件を `https://z.yuiseki.net/static/tokyo-ckan-files/` に中身を変えずに置いてある。文字コードは UTF-8、CP932、UTF-16 が混ざり、緯度と経度の列があっても値が空のものが多い。
- ライセンスはほぼ CC-BY-4.0。データセットごとに確かめる。
