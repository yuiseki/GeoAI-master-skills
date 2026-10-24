---
kind: dataset
id: esa-cci-biomass-v7
description: ESA Biomass CCI v7 の全球森林の木本地上部バイオマスと不確実性。
url: https://climate.esa.int/en/catalogue/6429d1aafe1e43b9b414e4a5a7f8b903/
license: ESA Biomass CCI 個別利用条件。利用は無償。再配布の可否は明文未確認
formats:
- GeoTIFF
- NetCDF
crs: EPSG:4326 (製品ガイド記載。ファイル自体は未実読)
spatial_coverage: 全球の森林・木本植生
temporal_coverage: 2005〜2012年と2015〜2024年の年次。2013〜2014年は無い
as_of:
  checked: 2026-10-25
contents:
- 木本の地上部バイオマス密度 (Mg/ha)
- 画素ごとの不確実性、および一部年の差分と品質フラグ
tables:
- name: agb_maps
  read: https://climate.esa.int/en/catalogue/6429d1aafe1e43b9b414e4a5a7f8b903/
  grain: 年 × 100m画素。粗い集約版もある
  rows: null
  id: []
---

# ESA Biomass CCI v7

## 料金、規模、取得経路

- [ESA の目録](https://climate.esa.int/en/catalogue/6429d1aafe1e43b9b414e4a5a7f8b903/) は v7 全体で816.28 GB、11,417ファイルと表示する。100m原本だけでなく粗い集約版や関連ファイルも含む目録の値である。ラスタは未実読。
- CEDA のダウンロードと FTP へのリンクが目録にある。固定ファイルを取得する方式で、検索・集計APIは未確認。
- 来歴は Sentinel-1、Envisat ASAR、ALOS/PALSAR 等の衛星観測を年ごとに組み合わせて推定したもの。100mの値は現地で直接量った値ではない ([製品目録](https://climate.esa.int/en/catalogue/6429d1aafe1e43b9b414e4a5a7f8b903/))。
- [製品ガイド v7 の第9節](https://climate.esa.int/media/documents/Product_User_Guide_PUG_V7.0.pdf) は教育・研究・商用利用とも無償で、出典表示を要求する。広告や商業宣伝では事前にレイアウトの承認を求める。データ個別の[利用条件](https://artefacts.ceda.ac.uk/licences/specific_licences/esacci_biomass_terms_and_conditions_v2.pdf)には再配布の許諾が明記されていない。一般の[サイト利用条件](https://climate.esa.int/en/terms-and-conditions/)はウェブサイトの素材の再配布を禁止しており、データを勝手にCC BYとみなさない。

## Hugging Face への凍結

元データの再配布について配布元の明確な許諾を確認できるまで保留。再現性のためには、当面は元の v7 のURL・DOI・取得日・対象ファイル名を記録する。

## 注意

AGB は木本の乾燥重量で、炭素密度とは別の量。草地・農地の地上部植生を網羅した一般的な炭素地図ではない。差分を読むときは不確実性と品質フラグを使い、2013〜2014年の欠年を隠さない。
