---
kind: dataset
id: yuiseki/opencellid
description: "OpenCelliD の携帯基地局セル位置を日付固定した GeoParquet。"
url: https://huggingface.co/datasets/yuiseki/opencellid
license: "CC BY-SA 4.0。帰属表示と ShareAlike 条件を守る"
formats:
- GeoParquet 1.0
crs: "OGC:CRS84"
spatial_coverage: "世界の OpenCelliD 掲載セル"
temporal_coverage: "2026-10-06 のスナップショット"
as_of:
  checked: 2026-10-26
  hf_revision: 82e4acdb5ea93250ea6128ce08c03a4ca8870c88
contents:
- 携帯電話セル識別子と推定位置
tables:
- name: cell_towers
  read: https://huggingface.co/datasets/yuiseki/opencellid/resolve/82e4acdb5ea93250ea6128ce08c03a4ca8870c88/parquet/2026-10-06/cell_towers.parquet
  grain: 携帯電話ネットワークのセル1件
  rows: 5502843
  id:
  - radio, mcc, net, area, cell
---

# OpenCelliD 2026-10-06

固定 GeoParquet は5,502,843行。無線方式、MCC、ネットワーク、エリア、セル ID を識別列とし、`lon`、`lat`、geometry (Point) を持つ。位置はコミュニティ測定からの推定で、アンテナ設備の測量位置や稼働状態を示さない。`range` と `samples` を信頼性の解釈に使う。日次 export は直近18か月の測定状況で対象が変わる。CC BY-SA 4.0 の帰属・ShareAlike 条件に従う。
