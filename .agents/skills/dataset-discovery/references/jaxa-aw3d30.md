---
kind: dataset
id: jaxa-aw3d30
description: JAXA の全球約30m数値表層モデル。地表だけでなく建物と樹木の高さを含む。
url: https://www.eorc.jaxa.jp/ALOS/en/dataset/aw3d30/aw3d30_e.htm
license: JAXA の地球観測データ利用方針。利用は無償で出典表示が必要。原データの再配布可否は未確認
formats:
- GeoTIFF (DSM、MSK、STK、QAI)
crs: 水平座標はタイルごとに確認。高さは EGM96 による標高と公式 FAQ に記載
spatial_coverage: 全球の陸域。版と地域で欠けや品質が異なる
temporal_coverage: 主な元画像は2006〜2011年。版は地域ごとに V3.1、V4.0、V4.1 などが混在
as_of:
  checked: 2026-10-25
contents:
- DSM (数値表層モデル)
- MSK、STK、QAI と元画像の一覧
tables:
- name: aw3d30_tile
  read: https://www.eorc.jaxa.jp/ALOS/en/dataset/aw3d30/aw3d30_e.htm
  grain: 1度 × 1度のタイル内の約30mの画素
  rows: null
  id: []
---

# JAXA AW3D30

[公式配布ページ](https://www.eorc.jaxa.jp/ALOS/en/dataset/aw3d30/aw3d30_e.htm)はユーザー登録とログインを要求する。2026-10-25 にページと[FAQ](https://www.eorc.jaxa.jp/ALOS/en/inquiry/faq_e.htm)を確認したが、登録・ファイル取得はしておらず画素・CRS・各タイルの容量は未実測。配布リストは23,993タイル。日本の多くは V3.1、その他の地域は主に V4.1 といった版の混在に注意する。

DSM は地面そのものの高さではない。建物や樹木がある都市では地盤高や浸水深の代理にそのまま使わない。観測年も公開版年も異なる。MSK と元画像の一覧を使い、対象地域ごとに欠損と観測時点を監査する。

[JAXA の利用方針](https://earth.jaxa.jp/policy/en.html)で無償利用と出典表示を確認し、第三者への原データ再配布は明示の確認ができていないため保留する。
