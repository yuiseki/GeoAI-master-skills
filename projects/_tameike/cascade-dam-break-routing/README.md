# cascade-dam-break-routing: 階段状連鎖ため池群のカスケード決壊水文解析

## 状態: 一旦保留（先行プロジェクト待ち）

本プロジェクトは、先行する **`projects/_tameike/sar-drought-drawdown-monitoring/`** において Sentinel-1 RTC 時系列解析によるため池の渇水・急減水・管理脆弱性の実態が判明した後に、抽出された高リスクため池水系を対象として再開します。

## 概要

- **問い**: 丘陵地谷筋に階段状に連なるため池群において、上流の大規模ため池（貯水量10,000m³以上）が決壊した際、国土地理院 5m DEM（DEM5A z15）に基づく D8 流向追跡上の下流ため池群へ連鎖波及する累積貯水エネルギーと、その直下流居住人口の曝露量はどのように集積しているか？
- **使い道**: 兵庫県・香川県および各市町村の防災・農政部局における、水系一貫カスケード決壊危険度マップの策定および事前放流バルブ・堤体補強予算の集中配分。
- **利用予定データ**:
  - `yuiseki/maff-tameike-list-jp-2026-03`（ため池台帳・諸元）
  - `gsi-dem-tiles` の `dem5a_z15`（航空レーザー 5m DEM、約 3.94m/px）
  - `yuiseki/estat-census-mesh-2020`（常住人口メッシュ）
- **主要な参照資料**:
  - [5m DEM 予備測定記録 (Probe)](../../../evals/curriculum/dry-runs/2026-11-06-tameike-cascade-5m-dem-probe.md)
  - [タスクカード](../../../evals/curriculum/task-cards/2026-11-06-tameike-cascade-dam-break.md)
  - [提案 JSON](../../../evals/curriculum/proposals/2026-11-06-tameike-cascade-dam-break-routing.json)
