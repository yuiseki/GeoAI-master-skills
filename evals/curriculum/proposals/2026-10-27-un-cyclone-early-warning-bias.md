# 提案課題: 国連「すべての人に早期警戒を（EW4All）」に向けた全球サイクロン人口曝露評価における 3 つの空間・統計バイアスの解明（UN Open GIS Initiative 視点・第2弾）

- **提案ID**: `2026-10-27-un-cyclone-early-warning-bias`
- **作成日**: 2026-10-27
- **生成モード**: `exploration`（第1弾の武力紛争×航空インフラ枝とは独立した、気象災害・早期警戒システム・気候適応の新たな枝）
- **ステータス**: `critic_review`（`validate_candidate.py` 検証通過・パイロット実測済）
- **パイロット・棄却記録**: `evals/curriculum/dry-runs/2026-10-27-un-cyclone-early-warning-bias.md`

---

## 1. 問いと使い道（UN Open GIS Initiative Contributor と周囲の意思決定）

- **問い**:
  UN Open GIS Initiative および国連「すべての人に早期警戒を（Early Warnings for All: EW4All）」・UN-SPIDER・OCHA 事前行動（Anticipatory Action）・UNDP の優先支援国選定に向け、2001〜2025年の強い熱帯低気圧（カテゴリー3相当以上、最大風速 96 kt 以上、経路から 100 km 圏内）に対する国別・人間開発指数（HDI）階層別の曝露人口は、
  1. **風速定義の選択**: ナイーブな `WMO_WIND >= 96 kt`（北大西洋・北東太平洋は1分平均風速だが、北西太平洋・インド洋・南太平洋は10分平均風速かつ欠測が多い列） vs 1分平均最大風速へハーモナイズした風速 `COALESCE(TRY_CAST(USA_WIND AS DOUBLE), WMO_WIND / 0.88) >= 96 kt`
  2. **H3 人口セルと国境の空間結合法**: セル重心交差（`ST_Centroid`） vs 六角形ポリゴン交差（`ST_Intersects(poly, geom)` による小島嶼開発途上国 SIDS・沿岸部の救済）
  3. **イベント集約の選択**: ユニーク曝露人口（期間中1回以上被災） vs 嵐識別子（`DISTINCT SID`）単位の年間期待延べ曝露人口 vs 3時間経路点（Track Points）の単純合算
  の選択によってどう変化し、どの低・中 HDI 国および小島嶼国（SIDS）が真の最優先支援国として浮上するか？

- **使い道（誰が何を決めるか）**:
  - **UN Open GIS Initiative の Contributor / UN-SPIDER / OCHA Centre for Humanitarian Data (HDX)**:
    1. **IBTrACS 全球熱帯低気圧データの標準ハーモナイズ仕様の策定**: 海域別 WMO 地域専門気象センター（RSMC）の風速平均時間差（1分平均 vs 10分平均）と `WMO_WIND` 欠測によって、アジア・アフリカ（北西太平洋 `WP`・北インド洋 `NI`・南インド洋 `SI`）の被災国が北大西洋・カリブ海諸国に対して系統的に過小評価されるバグを防ぐ。
    2. **H3 グリッド人口データの沿岸・小島嶼国（SIDS）空間結合仕様の標準化**: 22km H3 r4 セルの重心が海上に落ちることで、国連が最も重視する SIDS（トンガ、ミクロネシア、キリバス、モーリシャス、バルバドス、バハマ等）の人口が 98〜100% 消失する空間結合エラーを防ぐ。
  - **UNDRR（EW4All）・OCHA（事前行動資金 CERF）・UNDP の計画官**:
    - 物理的な反復サイクロン曝露が高く、かつ人間開発指数（`hdicode`: Low / Medium HDI）が低いため早期警戒・避難インフラ支援が最も急務な国（マダガスカル、モザンビーク、バングラデシュ、ミャンマー、ハイチ、および太平洋・インド洋・カリブ海の SIDS）への優先投資配分を決める。

---

## 2. 使うデータセットと固定版

| データセットID | レイヤー | 固定版 (Git Commit) | 主な利用列と役割 |
|---|---|---|---|
| `yuiseki/ibtracs-v04r01` | `track_points_since1980` | `7492b1ac35fbbcc304c752d3ff7d381c73a24510` | `SID` (嵐ID), `SEASON` (2001–2025), `BASIN`, `ISO_TIME`, `LAT`, `LON`, `WMO_WIND`, `WMO_AGENCY`, `USA_WIND`, `DIST2LAND`, `geometry` |
| `yuiseki/kontur-population-2023-11-01-22km` | `population_r4` | `2e7291f8c2d4b9c06bb4ff0e43be14e538e0600d` | `h3` (H3 resolution 4), `population` (推計人口), `geometry` (`EPSG:3857` → `EPSG:4326` 変換) |
| `yuiseki/undp-hdr` | `data` (`composite_indices`) | `dfc80c7de776473bd140d87c690600686f30833a` | `iso3`, `country`, `hdicode` (`Low`, `Medium`, `High`, `Very High`), `hdi_2023` |
| `yuiseki/natural-earth` | `ne_10m_admin_0_countries` | `efdd0668c57c9d42307e12eacbf66d8d151de5b9` | `ADM0_A3`, `ISO_A3_EH`, `NAME_JA`, `POP_EST`, `geometry` |

---

## 3. 実データパイロットの主要発見（`pilot_un_cyclone_aa.py`）

1. **H3 r4 セルを「重心（Centroid）」で国境に結合すると、世界の沿岸人口 3億9,793万人と小島嶼国（SIDS）の人口 100% が消滅する**:
   - 緯度 ±40度以内の Kontur H3 r4 セル（`48,954` セル）を Natural Earth 国境ポリゴンに結合する際、セル重心交差（`ST_Intersects(ST_Centroid(poly), country.geom)`）を使うと、沿岸および島嶼の **`4,267` セル・人口 `3億9,793万人` が海上に落ちて国コード `NULL` として脱落**する。
   - 特に **トンガ（`TON` 10.4万人）、ミクロネシア連邦（`FSM` 10.4万人）、キリバス（`KIR` 12.6万人）、セントビンセント（`VCT` 10.3万人）、セントルシア（`LCA` 18.5万人）、グレナダ（`GRD` 12.5万人）、バルバドス（`BRB` 28.2万人）、モーリシャス（`MUS` 130.1万人）、モルディブ（`MDV` 50.7万人）、セーシェル（`SYC` 10.6万人）、シンガポール（`SGP` 273.2万人）では人口の 100.0% が消失**し、**バハマ（`BHS`）でも 98.3%（40.5万/41.2万人）が消失**する。六角形ポリゴン交差（`ST_Intersects(poly, country.geom)`）を使うことで初めてこれらが完全に救済される。
2. **`WMO_WIND` の海域別定義差（10分平均 vs 1分平均）と欠測により、アジア・アフリカのカテゴリー3以上サイクロン曝露人口が 74%（3.2億人分）過小評価される**:
   - 2001〜2025年の IBTrACS において、北大西洋（`NA`）と北東太平洋（`EP`）は米国 NHC が RSMC のため `WMO_WIND` と `USA_WIND` の `>= 96 kt` 嵐数が完全一致する（`NA`: 88対88、`EP`: 110対110）。
   - しかし 10分平均風速を使う他海域では、`WMO_WIND >= 96 kt` と 1分平均統一風速 `>= 96 kt` で嵐数が **北西太平洋（`WP`）で `99` 対 `225`（2.27倍）、北インド洋（`NI`）で `15` 対 `26`（1.73倍）、南インド洋（`SI`）で `85` 対 `128`（1.51倍）、南太平洋（`SP`）で `41` 対 `56`（1.37倍）** と大きく乖離する。
   - この結果、世界のカテゴリー3相当以上（100 km 圏内）ユニーク曝露人口は **`1億1,472万人`（ナイーブ `WMO_WIND`）から `4億3,478万人`（1分平均統一、3.79倍）** へ、年間期待延べ曝露人口は **`722万人/年` から `3,753万人/年`（5.20倍）** へ急増する。
   - 国別では、**ベトナム（`VNM`）が `0人` → `1,001万人`**、**バングラデシュ（`BGD`, Medium HDI）が `220万人` → `2,235万人`（10.2倍）**、**フィリピン（`PHL`）の年間延べ曝露が `122万人/年` → `1,416万人/年`（11.6倍）**、**マダガスカル（`MDG`, Low HDI）が `102万人` → `627万人`（6.1倍）**、**モザンビーク（`MOZ`, Low HDI）が `255万人` → `726万人`（2.8倍）**、**ミャンマー（`MMR`, Medium HDI）が `238万人` → `609万人`（2.6倍）** と劇的に逆転する。
   - UNDP HDI 階層別でも、**Low HDI 国のユニーク曝露人口は `364万人` → `1,360万人`（3.74倍）、Medium HDI 国は `3,004万人` → `7,965万人`（2.65倍）** に跳ね上がる。
3. **3時間経路点（Track Points）の単純合算による 1.95 倍の過大計上**:
   - 嵐識別子（`DISTINCT SID`）で重複除去した年間期待延べ曝露人口は **`3,753万人/年`** だが、3時間ごとの経路点行をそのまま合算すると **`7,329万人/年`（1.95倍）** に膨らみ、嵐の進行速度が遅い地域（ハイチ `HTI` で 4.6倍、香港 `HKG` で 4.2倍）で順位が歪む。

---

## 4. 同時に検討して棄却した候補（3件）

1. **候補B（棄却）**: Meta Movement Distribution (`yuiseki/meta-move-dist`) の2026年6〜8月データを用いた全球の長期気候変動移住の推定
   - **棄却理由 (`short_window_and_platform_selection_bias`)**: 2026年6〜8月の76日間の短期データかつ Facebook 位置共有利用者に限定され、長期の気候移住を識別できないため。
2. **候補C（棄却）**: EDGAR 国別温室効果ガス排出量 (`yuiseki/edgar-ghg-countries`) と UNDP HDI (`yuiseki/undp-hdr`)・Penn World Table (`yuiseki/pwt`) の国別クズネッツ曲線回帰
   - **棄却理由 (`no_spatial_necessity`)**: 国×年の非空間テーブル結合のみで完結し、空間座標・距離・トポロジーを一切使わないため。
3. **候補D（棄却）**: タイムゾーン境界 (`yuiseki/timezone-boundary-builder-2026d`) と国連人口推計 (`yuiseki/un-wpp`) の重ね合わせによる時間帯別人口集計
   - **棄却理由 (`trivial_aggregation_without_decision_stakes`)**: 単純な集計にとどまり、国連の具体的な人道・防災の意思決定を左右する方法論的判断が無いため。
