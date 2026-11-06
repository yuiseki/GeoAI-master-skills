# Dry-Run Log: 兵庫県・香川県のため池を軸とした5つの多角的研究テーマの生成と実データパイロット検証

- 実施日: 2026-11-06
- 目的: 「兵庫県と香川県のため池を軸に、水文解析、交通網分析、SAR画像解析などが活用できないか考えつつ、調査研究テーマを5つ立案する」という依頼に対し、`.agents/skills/research-question-generation/SKILL.md` の規定に従い、DuckDB による全数パイロット集計を実施した上で、既存課題・プロジェクトと重複しない5つの高難易度研究テーマを策定・評価する。

---

## 1. 入力データの精査と実測ベースライン (DuckDB 実測証拠)

ため池数日本一の兵庫県（24,019件）およびため池密度日本一の香川県（12,187件、6.39箇所/km²）を対象に、農林水産省ため池台帳（`yuiseki/maff-tameike-list-jp-2026-03`）、国勢調査1kmメッシュ（`yuiseki/estat-census-mesh-2020`）、国土地理院指定緊急避難場所（`yuiseki/gsi-evacuation-sites-jp`）、国交省都市計画決定GISデータ（`yuiseki/mlit-toshi-keikaku-jp`）、OSM道路網（`yuiseki/osm-japan-src-2026-08`）の全件クロス集計を実施した。

### 主要な実測値（ベースライン統計）

| 指標 | 兵庫県 | 香川県 | 備考・解釈 |
|---|---:|---:|---|
| **総ため池数** | **24,019** 件 | **12,187** 件 | 兵庫が全国1位、香川が密度全国1位 |
| **近傍間距離中央値 (Nearest Neighbour)** | **89.7 m** | **96.9 m** | 両県ともにため池同士が極めて過密 |
| **300m以内に他のため池が存在する割合** | **90.9%** (21,825件) | **95.1%** (11,587件) | 谷筋に沿った「階段状連鎖ため池群」の存在 |
| **完全同一座標の共有ため池数** | 13 件 | **421 件** | 香川県では連鎖池を一括代表点登録する運用が頻発 |
| **堤高 9999.9 センチネル数** | **860 件** | **0 件** | 兵庫県台帳特有の欠損埋め値 |
| **貯水量 9999.9 センチネル数** | **867 件** | **0 件** | 兵庫県台帳特有の欠損埋め値 |
| **水面積 NULL (欠損) 件数** | **1,719 件** | **3 件** | 兵庫県は面積未計測が多数 |
| **名前に「(非)」接頭辞が付く件数** | **693 件** | **0 件** | 神戸市北区(374)、洲本市(63)、丹波篠山市(51)等 |
| **面積 0.001 km² 未満 (10a未満、30m四方以下)** | **13,998 件 (58.3%)** | **8,134 件 (66.7%)** | 一般的な10m SAR衛星では解像度限界 |
| **面積 0.01 km² 以上 (1ha以上、100画素以上)** | **1,504 件 (6.3%)** | **659 件 (5.4%)** | Sentinel-1 RTC で安定検知可能な限界 |
| **貯水量 10,000 m³ 以上の池** | **2,713 件** | **1,281 件** | 決壊時のエネルギーが大きい重点危険池 |
| **貯水量 100,000 m³ 以上の池** | **318 件** | **192 件** | 大規模ダム相当のため池 |
| **ため池が存在する1km人口メッシュの居住人口** | **1,947,384 人** | **547,928 人** | 広大な人口がため池直近に居住 |
| **ため池 >=10箇所の過密メッシュ居住人口** | **200,510 人** (662メッシュ) | **130,779 人** (483メッシュ) | 最大ため池数は兵庫99箇所、香川50箇所 |
| **300m圏内にため池がある指定避難場所数** | **762 箇所** | **347 箇所** | 全避難場所の20〜36%がため池至近 |
| **洪水指定かつ貯水量10,000m³以上近接避難場所** | **310 箇所** | **118 箇所** | 避難所自体が直撃を受ける重大リスク |

---

## 2. 棄却した候補 (Rejected Candidates) と理由

`research-question-generation` の原則「答えられる問いを量産するのではなく、棄却を優先する」に基づき、予備検討段階の3候補を明確に棄却した。

1. **`rejected-01`: 兵庫県・香川県におけるため池数と総貯水量の市町村別単純集計ランキング**
   - *棄却理由*: `maff-tameike-list-jp-2026-03` を `GROUP BY municipality` で集約するだけの単純集計（trivial）であり、空間構造の解析や意思決定者の判断分岐を含まないため棄却。
2. **`rejected-02`: アメダス年間降水量データとため池密度の相関分析**
   - *棄却理由*: 瀬戸内式気候の少雨地域にため池が多いことは歴史・農業地理学的に自明であり、行政の防災・維持管理意思決定に資する新しい介入ポイントが存在しないため棄却。
3. **`rejected-03`: Sentinel-1 SAR による全ため池の一律水有無 2値分類**
   - *棄却理由*: パイロット実測の結果、兵庫の58.3%・香川の66.7%のため池は面積 0.001 km² 未満（30m×30m以下）であり、Sentinel-1 の 10m 画素および 1〜2 画素の位置ズレ・スペックルノイズのもとでは物理的に判別不能である。観測分解能の限界を無視したモデル構築は工学的に破綻するため棄却し、「検知限界面積閾値の解明」という問い（Theme 2）へ再設計した。

---

## 3. 採択した5つの多角的研究テーマ

各テーマは独立した分析スキル、データセット統合、意思決定主体、反証可能な作業仮説を持つ。

| # | テーマ名 / 視点 | Proposal ID | 分析スキル | 主な結合データセット | 意思決定主体 |
|---|---|---|---|---|---|
| **1** | **水文解析・カスケード連鎖決壊**<br>階段状連鎖ため池の水文流向追跡と直下流人口曝露 | `2026-11-06-tameike-cascade-dam-break-routing` | `terrain-hydrology` | ため池台帳 + `gsi-dem-tiles` + 国勢調査1kmメッシュ | 兵庫・香川両県農政部・市町村防災部局 |
| **2** | **SAR画像解析・渇水期貯水監視**<br>Sentinel-1 RTC による水面縮小検知限界閾値と枯渇同期 | `2026-11-06-tameike-sar-drought-drawdown-monitoring` | `sar-change-detection` | ため池台帳 + `planetary-computer-sentinel-1` + 自治体行政界 | 香川県農政水産部・土地改良区・気象水文部局 |
| **3** | **交通網分析・道路網分断避難リスク**<br>ため池決壊時の道路遮断と指定緊急避難場所の孤立・迂回解析 | `2026-11-06-tameike-evacuation-road-network-severance` | `spatial-network-analysis` | ため池台帳 + `gsi-evacuation-sites-jp` + `osm-japan-src-2026-08` | 市町村危機管理室・土木部局・警察本部 |
| **4** | **都市計画規制・スプロール曝露**<br>低層住宅地用途地域と台帳未登録・非指定池 `(非)%` の重層 | `2026-11-06-tameike-urban-sprawl-downstream-exposure` | `spatial-data-integration` | ため池台帳 + `mlit-toshi-keikaku-jp` (`youto`) + 国勢調査メッシュ | 兵庫県都市整備部・神戸市都市局・建築住宅局 |
| **5** | **観測バイアス・データガバナンス**<br>センチネル値・同一座標縮退・行政境界断層の計量監査 | `2026-11-06-tameike-hyogo-kagawa-governance-audit` | `observation-bias-audit` | ため池台帳 + `jp-admin-2026-09` + 国勢調査メッシュ | 農水省農村振興局・国交省・消防庁・デジタル庁 |

---

## 4. 全提案のバリデーション結果

```sh
for f in evals/curriculum/proposals/2026-11-06-*.json; do
  python3 .agents/skills/research-question-generation/scripts/validate_candidate.py "$f"
done
```

- `2026-11-06-tameike-cascade-dam-break-routing.json`: `{"status": "critic_review", "reasons": []}`
- `2026-11-06-tameike-sar-drought-drawdown-monitoring.json`: `{"status": "critic_review", "reasons": []}`
- `2026-11-06-tameike-evacuation-road-network-severance.json`: `{"status": "critic_review", "reasons": []}`
- `2026-11-06-tameike-urban-sprawl-downstream-exposure.json`: `{"status": "critic_review", "reasons": []}`
- `2026-11-06-tameike-hyogo-kagawa-governance-audit.json`: `{"status": "critic_review", "reasons": []}`

全5件の提案 JSON が必須フィールド・データセット接続グラフ・変数実在性・非自明性・Rubric 等のハードゲートチェックを全てクリアした。

---

## 5. 詳細 Probe (予備測定) の実施記録

提案候補の実効性をさらに担保するため、個別テーマの実データ Probe を実施した。

- **Theme 1 (連鎖決壊水文解析)**:
  - `evals/curriculum/dry-runs/2026-11-06-tameike-cascade-5m-dem-probe.md`: 国土地理院 5m DEM（`gsi-dem-tiles/dem5a_z15`、解像度約 3.94 m/pixel）の淡路島・讃岐平野での疎通（200 OK）、淡路市深山池〜深山下池間の 43.3% 堤体法面勾配の実測、およびため池水面 NaN マスク（タイル内 28 箇所・3.79%）に伴う水文流向追跡の前処理要件（水面標高補間と余水吐ブリーチ）を実証・記録した。
  - 実測スクリプト: `evals/curriculum/dry-runs/tameike-pilots/probe_cascade_5m_dem.py`
  - 出力データ: `evals/curriculum/dry-runs/tameike-pilots/probe_cascade_5m_dem.json`

