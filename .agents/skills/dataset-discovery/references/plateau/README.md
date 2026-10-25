---
kind: catalog
id: plateau
description: 国土交通省 PLATEAU の都市別3D都市モデルの目録。CityGMLなどの配布版を選ぶ入口。
url: https://www.mlit.go.jp/plateau/open-data/
access: PLATEAU VIEW のデータカタログ API を匿名で閲覧できる。個別 ZIP のアクセス・容量はデータごとに確認する
license: PLATEAU のサイトポリシーは公共データ利用規約1.0を基本とするが、自治体や個別データの条件を確認する
crs: 都市・ファイルごとに異なる。CityGML の srsName を読んで確かめる
spatial_coverage: 日本の公開都市。収録範囲と地物クラスは都市・年ごとに異なる
temporal_coverage: 都市・公開年度・元資料年度ごと
as_of:
  checked: 2026-10-25
contents:
- 都市ごとの CityGML ZIP と建物・道路・地形などの地物クラス
- 公開年度、仕様版、ファイルサイズなどの目録
---

# PLATEAU 3D都市モデル

[公式配布ページ](https://www.mlit.go.jp/plateau/open-data/)から都市と年度を選ぶ。[PLATEAU VIEW のデータカタログ API](https://docs.plateauview.mlit.go.jp/datasets/citygml/)の `GET https://api.plateauview.mlit.go.jp/datacatalog/plateau-datasets` は、2026-10-25 に匿名で応答した。`citygml` と `latest_citygml` はそれぞれ307レコードだったが、公開ページの「306都市」とは数え方が異なる。レコード件数を自治体数と同一視しない。

例として札幌市 2020 年のレコードには都市コード `01100`、仕様 `4.1`、登録年2024、CityGML ZIP の公称サイズ2,718,857,700バイトがあった。元ファイルは未実読。`latest` は変わるので都市コードと年、必要なら取得ファイルのハッシュを固定する。CityGML は地物の高さ・建物用途・LOD が均一ではない。解析前に元資料の時点、LOD、属性欠損、ファイル内 CRS を確かめる。

[サイトポリシー](https://www.mlit.go.jp/plateau/site-policy/)に公共データ利用規約1.0と互換ライセンスの説明がある。再配布はデータ単位の出典・自治体の追加条件を確認した上で判断する。数 GB の都市 ZIP を無条件に Hugging Face へ複製しない。
