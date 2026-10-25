---
kind: dataset
id: gebco-2025
description: GEBCO 2025 Grid。全球の海底地形と陸の標高を15秒角の格子にした固定版。海底の観測密度は場所によって違う。
url: https://www.gebco.net/data-products-gridded-bathymetry-data/gebco2025-grid
license: GEBCO Grid は public domain。ただし出典表示が必要で、GEBCO の承認を示唆してはならない
formats:
- NetCDF-4
crs: 水平 WGS84 を想定。鉛直は平均海面基準を想定するが元データで混在する
spatial_coverage: 全球。海と陸
temporal_coverage: 2025年版。入力となった測量の時点は場所ごとに異なる
as_of:
  checked: 2026-10-25
contents:
- 海底地形と陸域の標高 (m)
- TID Grid による画素ごとのデータ由来の区分
tables:
- name: elevation
  read: https://www.gebco.net/data-products-gridded-bathymetry-data/gebco2025-grid
  grain: 15秒角の1画素。全球43200 × 86400画素
  rows: 3732480000
  id: []
- name: tid
  read: https://www.gebco.net/data-products-gridded-bathymetry-data/gebco2025-grid
  grain: elevation と同じ格子の1画素
  rows: 3732480000
  id: []
---

# GEBCO 2025 Grid

[配布元](https://www.gebco.net/data-products-gridded-bathymetry-data/gebco2025-grid)の固定版を使う。全球ファイルだけでなく範囲指定のダウンロードもある。全球の標高 NetCDF は非圧縮で約7.5 GB、TID Grid は約4 GBと配布元が説明する。2026-10-25 時点で配布ページと仕様を確認したが、画素は実読していない。利用時は対象範囲を切り出し、NetCDF 内の座標・NoData・鉛直基準を実ファイルで確かめる。

標高だけを実測深度として扱わない。測量に基づく場所と予測で埋めた場所があるため、TID Grid と併用し、観測方法による品質差を示す。船舶航行・安全用途には使えない。陸上の標高を海底地形と同じ観測過程だと見なさない。最新版ではなく2025年版を明記して再現性を保つ。

GEBCO は public domain とする一方、利用時の出典表示を求めている。再配布時にも[利用条件](https://www.gebco.net/data-products/gridded-bathymetry/terms-of-use)を再確認する。表示例は `GEBCO Compilation Group (2025) GEBCO 2025 Grid`。このカードだけを根拠に Hugging Face へ全量を複製しない。
