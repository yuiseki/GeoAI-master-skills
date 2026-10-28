---
kind: dataset
id: yuiseki/fagus-crenata-masting-jp-2026-06
description: 東北 98 地点と北海道渡島半島 4 地点のブナ (Fagus crenata) の結実の 4 段階の評価 (1989〜2008 年) と、地点ごとの夏と春の気温の手がかり、カヌマ沢の種子トラップ、階層ベイズの個体群モデルの推定値。Dryad の記録 (Masaki ほか、版 5) を値を変えずに Parquet にしたもの。
url: https://huggingface.co/datasets/yuiseki/fagus-crenata-masting-jp-2026-06
license: CC0 1.0 (Dryad の記録のライセンス欄)。著者は Dryad の記録と論文の引用を求めている
formats:
- Parquet (4 表。座標は緯度と経度の列で、geometry の列は無い)
- Dryad の zip と元の CSV 4 つ、元の README (raw/20260605/)
crs: EPSG:4326 (study_sites の Latitude と Longitude。WGS84 の度)
spatial_coverage: 青森、岩手、宮城、秋田、山形の 98 地点と北海道渡島半島の 4 地点 (2026-10-28 に jp-admin-2026-09 の面で数えると、秋田県 31、青森県 28、山形県 23、岩手県 13、北海道 4、宮城県 3)。福島県と新潟県は無い。面ではなく調査地点の点
temporal_coverage: 結実の評価は 1989〜2008 年 (地点で欠けた年がある)、種子トラップは 1990〜2008 年。2009 年以後は入っていない
as_of:
  upstream_version: Dryad 版 5、2026-06-05
  huggingface_revision: db40a09e24cbc02d6f19a7180bafe5f04962f8f8
  checked: 2026-10-28
contents:
- 調査地点の位置、標高、名前 (ローマ字と日本語)
- 地点 × 年の結実の評価 (0 無し、1 不作、2 並作、3 豊作) と、夏の高温の手がかり T.HSM、春の低温の手がかり T.LSP (横持ち)
- カヌマ沢の種子トラップの花と種子の密度 (1 地点、19 年)
- 地点ごとの潜在変数 (花芽 P、開花 F、種子 S の年ごとの値) と、モデルのパラメータの事後分布の要約 (縦持ち)
tables:
- name: study_sites
  read: hf://datasets/yuiseki/fagus-crenata-masting-jp-2026-06@db40a09e24cbc02d6f19a7180bafe5f04962f8f8/parquet/study_sites.parquet
  grain: 1 つの調査地点
  rows: 102
  id:
  - ID
  join_keys:
  - column: ID
    type: BIGINT
    meaning: 地点の番号 1〜102。1〜4 が渡島半島、5〜102 が東北
    unique: true
    joins:
    - seed_rank_and_cues.ID
    - model_estimates.ID
  no_key:
  - name: code5
    note: 市町村コードは無い。点を jp-admin-2026-09 の面に入れて付ける
  columns:
  - name: Location
    type: VARCHAR
    meaning: 地域 (`Oshima Peninsula in Hokkaido` か `Tohoku region in Honshu`)
  - name: Site name in Japanese
    type: VARCHAR
    meaning: 地点の日本語の名前 (八甲田、大湯１ など)。市町村名ではない
  - name: Latitude
    type: DOUBLE
    meaning: 緯度 (WGS84)
  - name: Longitude
    type: DOUBLE
    meaning: 経度 (WGS84)
  - name: Altitude
    type: BIGINT
    meaning: 標高 (m)
- name: seed_rank_and_cues
  read: hf://datasets/yuiseki/fagus-crenata-masting-jp-2026-06@db40a09e24cbc02d6f19a7180bafe5f04962f8f8/parquet/seed_rank_and_cues.parquet
  grain: 1 つの調査地点。年は列 (横持ち 64 列)
  rows: 102
  id:
  - ID
  join_keys:
  - column: ID
    type: BIGINT
    meaning: study_sites の ID
    unique: true
    joins:
    - study_sites.ID
  columns:
  - name: Obs.seed.rnk.YYYY
    type: BIGINT
    meaning: その年の結実の評価 (1989〜2008 の 20 列)。0 無し、1 不作 (数本の樹冠に実)、2 並作 (半数以上の木の樹冠上部に実)、3 豊作 (大半の木の樹冠全体に実)。東北は東北森林管理局の職員の毎秋の目視、渡島半島は種子トラップから同じ基準で
    missing: NULL は評価が無い年 (60 セル)。-1 は 61 セル (1999 年の ID 49〜102 の 54、2004 年の ID 5〜10 と 16 の 7) で、元の README に定義が無い。評価として読まない
  - name: T.HSM.YYYY
    type: DOUBLE
    meaning: 夏の高温の手がかり。7〜8 月の日最高気温の 1990 年代平均からの正の偏差の、連続した日の積算 (°C·日) を標準化した値 (平均 0、SD 1)。20 km 以内の気象台の値を標高で補正
  - name: T.LSP.YYYY
    type: DOUBLE
    meaning: 春の低温の手がかり。4〜5 月の日最低気温の負の偏差の積算に −1 を掛けて標準化した値
- name: kanumazawa_traps
  read: hf://datasets/yuiseki/fagus-crenata-masting-jp-2026-06@db40a09e24cbc02d6f19a7180bafe5f04962f8f8/parquet/kanumazawa_traps.parquet
  grain: カヌマ沢渓畔林試験地 (39.1°N、140.9°E) の 1 年
  rows: 19
  id:
  - Year
  no_key:
  - name: ID
    note: 地点の ID は無い。102 地点のどれにあたるかは書かれていない
  columns:
  - name: Year
    type: BIGINT
    meaning: 年 (1990〜2008)
  - name: Total density of flowers (per 0.5m2)
    type: DOUBLE
    meaning: ブナの成木の真下の 8 個のトラップの平均の花の密度 (0.5 m² あたり)
  - name: T.HSM
    type: DOUBLE
    meaning: 夏の高温の手がかり。元の README は標準化済みとするが、値は 0〜180.7 (平均 58.7) で °C·日のままに見える
- name: model_estimates
  read: hf://datasets/yuiseki/fagus-crenata-masting-jp-2026-06@db40a09e24cbc02d6f19a7180bafe5f04962f8f8/parquet/model_estimates.parquet
  grain: 1 つの地点の 1 つのパラメータ (縦持ち)
  rows: 6747
  id:
  - ID
  - Parameter
  join_keys:
  - column: ID
    type: BIGINT
    meaning: study_sites の ID
    unique: false
    joins:
    - study_sites.ID
  columns:
  - name: Parameter
    type: VARCHAR
    meaning: P.YYYY、F.YYYY、S.YYYY (花芽、開花、種子の相対量、0〜1) と、alpha.const、alpha.HSM、alpha.LSP、beta.EIP、beta.RPF、beta.SR、gamma.BFMS、gamma.FPBF の 8 つ。地点で 44〜68 個と揃っていない
  - name: Mean
    type: DOUBLE
    meaning: 事後平均。ほかに Median、SD、95% CI lower、95% CI Upper、Rhat
---

# 東北と渡島半島のブナの結実 102 地点 (fagus-crenata-masting-jp-2026-06)

Masaki ほかが Dryad に出した「Data on seed production from 102 Fagus crenata sites in northern Japan and process model parameters for predicting annual variation」(doi:10.5061/dryad.7sqv9s54n、版 5、2026-06-05) の凍結コピー。値は変えず、CSV の `NA` を NULL にして Parquet にしてある。元の zip、CSV、README は `raw/20260605/` にある。

分析では、ブナの豊凶の年ごとの変動と、その地域での揃い方 (同じ年に広い範囲で豊作や凶作になるか) に使う。クマの大量出没と実りの関係を考える材料になるが、年が 1989〜2008 年までで、手元のクマの通報 (秋田 2022〜2026 年、岐阜 FY2014〜、京都 FY2009〜2018) とは重ならない。

## 表

| 表 | 1 行 | 行 | 中身 |
|---|---|---:|---|
| `study_sites` | 地点 | 102 | 位置、標高、名前 |
| `seed_rank_and_cues` | 地点 (年は列) | 102 | 結実の評価 20 年分と、夏と春の気温の手がかり |
| `kanumazawa_traps` | 年 | 19 | カヌマ沢の種子トラップの花と種子の密度 |
| `model_estimates` | 地点 × パラメータ | 6,747 | 潜在変数とモデルのパラメータの事後分布の要約 |

## 実測 (2026-10-28、DuckDB 2.0.0)

| 項目 | 値 |
|---|---|
| 地点の都道府県 (jp-admin-2026-09 の面に点を入れて) | 秋田県 31 (ID 49〜79)、青森県 28、山形県 23、岩手県 13、北海道 4、宮城県 3。どの面にも入らない点は 0 |
| 秋田県の地点の市町村 | 北秋田市 6、仙北市 6、鹿角市 4、大館市 3、藤里町 3、五城目町 2、秋田市 2、由利本荘市 2、東成瀬村 1、湯沢市 1、にかほ市 1 |
| 評価の値 (2,040 セル) | 0 が 547、1 が 669、2 が 370、3 が 333、-1 が 61、NULL が 60 |
| 豊作 (3) の多い年 | 2000 年 (評価のある 102 地点のうち 72)、1995 年 (61)、2005 年 (55)。秋田県の 31 地点では 2000 年 28、2005 年 19 |
| 全地点で豊作の無い年 | 1991、1996、1999、2001、2006 年 |
| ID の一意 | study_sites と seed_rank_and_cues は ID で 102 行が一意。model_estimates は (ID, Parameter) で 6,747 行が一意 |

## 気をつけること

- 2008 年で終わる。2022 年以後のクマの通報の年と結ぶには、同じ東北森林管理局の評価の続き (元の README が示す森林総合研究所の「タネダス」<https://www.ffpri.affrc.go.jp/labs/tanedas/>) を別に取る必要がある。このデータセットには無い。
- 1999 年は東北の ID 49〜102 (秋田県の 31 地点を全て含む) が -1 で、その年の秋田県の評価は事実上無い。-1 の意味は元の README に無い。
- 評価は目視の 4 段階で、量ではない。量は `kanumazawa_traps` の 1 地点だけ。
- 地点は林の中の調査地点の点で、市町村や面の代表ではない。名前 (大湯１、玉川第一 など) は地区名で、同じ名前の市町村とは違う。
- `seed_rank_and_cues` の T.HSM と T.LSP は標準化した値 (平均 0、SD 1) だが、`kanumazawa_traps` の同じ名前の列は元の単位に見える (T.LSP は -95.3〜-0.3)。2 つの表の値を混ぜない。
- `model_estimates` は地点ごとに持つパラメータの数が違う (44〜68)。横に広げるときは欠けた組み合わせを NULL として扱う。
- 地点の平年の気候 (WorldClim 由来、CC BY 4.0) は Zenodo の別の記録 (doi:10.5281/zenodo.20550356) で、ここには無い。

## 出典の表示

CC0 なので表示は義務ではないが、著者は次の 2 つの引用を求めている。

> Masaki T., et al. Data on seed production from 102 Fagus crenata sites in northern Japan and process model parameters for predicting annual variation. Dryad. https://doi.org/10.5061/dryad.7sqv9s54n
>
> Masaki T., Hoshizaki K., Homma C. (2025) Disentangling the effects of geographical location and local climate on masting in Fagus crenata using a comprehensive population model. Basic and Applied Ecology. https://doi.org/10.1016/j.baae.2025.05.004
