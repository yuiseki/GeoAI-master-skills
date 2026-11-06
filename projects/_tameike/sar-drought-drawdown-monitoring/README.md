# sar-drought-drawdown-monitoring: 12日周期 Sentinel-1 RTC 時系列によるため池水面縮小・渇水監視解析

## 問いと使い道

- **問い**:
  香川県讃岐平野、兵庫県淡路島、および広島県（防災重点ため池全国最多）のため池群において、12日周期の Sentinel-1 RTC（10m 分解能、VV/VH 偏波）の時系列後方散乱強度（$\gamma^0$）から、盛夏渇水期・農業取水期の水面縮小（drawdown）をどの規模（面積閾値）のため池まで安定して検知できるか？また、近隣ため池間で渇水による急減水は空間的に同期するか？
- **使い道**:
  1. **広域ため池渇水モニタリングの運用基準策定**: 香川県農政水産部・兵庫県農政環境部・広島県農林水産局・土地改良区における衛星監視の検知可能下限面積の把握と誤警報防止。
  2. **カスケード決壊解析への高リスク水系特定**: 盛夏期に極端な水位低下や急減水を示す管理脆弱ため池を抽出し、後続プロジェクト `projects/_tameike/cascade-dam-break-routing/` の重点対象を選定する（特に直下に住宅密集地を抱える防災重点ため池集中水系）。

---

## 利用データセット

| データセットID / 出典 | 役割・内容 | 解像度・頻度 |
|---|---|---|
| `planetary-computer-sentinel-1` (`sentinel-1-rtc`) | 後方散乱強度 $\gamma^0$（VV/VH）、水面縮小・露出検知 | 10m、12日周期 |
| `yuiseki/maff-tameike-list-jp-2026-03` | ため池台帳（位置、水面積、貯水量、堤高） | ポイント（全件） |
| **気象庁 (JMA) アメダス観測所** | 香川・淡路島各地点の地上日降水量、日照時間、最大風速（干天判定・強風日特定） | 地点（高松、滝宮、洲本等） |
| **JAXA GCOM-C SGLI 蒸発散量** (`JAXA.JASMES_GCOM-C.SGLI_ET.v1_global_8-day`) | 衛星観測地表面温度等による蒸発散量（JAXA Earth API） | 約 5km、8日別 |
| **JAXA GSMaP 日別降水量** (`JAXA.EORC_GSMaP_standard.Gauge.00Z-23Z.v6_daily`) | 衛星全球降水マップ（地上雨量計補正済み） | 0.1度（約10km）、日別 |
| **FAO AgERA5 基準蒸発散量** (`yuiseki/agera5-japan-monthly-water-1979-2026`) | FAO-56 Penman-Monteith 算定基準蒸発散量（`et0_mm`）と降水量（水収支 baseline） | 0.1度、月別 |

```
projects/_tameike/sar-drought-drawdown-monitoring/
  README.md               問い、使い道、構成、再現手順
  EXPERIMENT_PLAN.md      実験計画 (流す前に固定した仮説、主張、区画、判断規則)
  EXPERIMENT_TRACKER.md   実験実行の記録
  scripts/                時系列抽出・水面変動検知・対照補正コード
  outputs/                報告が引く比較表、閾値感度表、検証図 (CSV, JSON, PNG)

artifacts/_tameike/sar-drought-drawdown-monitoring/
  (大容量の Sentinel-1 RTC GeoTIFF、時系列 Parquet、抽出マスク等)
```

---

## 再現手順 (Planned Commands)

1. **メタデータおよび観測シーンの特定**:
   - Planetary Computer STAC API より香川・淡路地域の同一相対軌道（12日周期）Sentinel-1 RTC データを検索・選定。
2. **ため池ポリゴン・バッファと対照区の作成**:
   - 農水省ため池台帳の諸元と位置に基づき、水面積規模別（$\ge 5\text{ha}$, $1\text{〜}5\text{ha}$, $0.1\text{〜}1\text{ha}$）のポリゴンおよびエロージョン内部コア領域を生成。
   - 恒常水面、安定樹林、農地対照区を設定。
3. **時系列後方散乱プロファイルの抽出と変化検知**:
   - `scripts/extract_sar_timeseries.py`
   - `scripts/analyze_drawdown.py`
4. **実験計画（EXPERIMENT_PLAN.md）に基づく仮説判定**:
   - `EXPERIMENT_TRACKER.md` に各区画（B0〜B4）の結果を記録。
