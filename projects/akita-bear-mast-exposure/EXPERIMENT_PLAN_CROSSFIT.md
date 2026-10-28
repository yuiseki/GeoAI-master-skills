# 計画 (追加の診断): β の学習に in-sample の B_env を使ったことが、β を 0 へ押したか

流す前に書く。流した後に書き直さない。直すなら末尾の「計画の変更」に足す。

## 位置づけ

- これは post-hoc methodological diagnostic で、新しい生態の仮説ではない。元の確認 ([EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)、[report.md](report.md)) の結論「preregistered experiment では not supported」は書き換えない。
- 問い: β を当てるときの学習の年度の B_env を、その年度の通報を使わずに作ったスコア (cross-fit、out-of-fold) に替えても、mast_scarcity × beech_oak exposure の追加の価値は 0 のままか。
- 見ていた結果: 元の確認と反証の全て (β は 2025 年度 −0.007、2026 年度 −0.007、capture@5% の差 +0.0002、+0.0003)。

## 変えないもの

元の凍結した仕様 (`outputs/b1_frozen_spec.json`、sha256 655c8590…) のまま:

- exposure: beech_oak の 2 km (NaN は 0)。
- mast_scarcity: retrospective = 5 − 同じ年の結実時の指数、operational = 5 − 同じ年の開花時の指数。両方を出す。
- モデルの形: logit P = α(年) + offset + β × mast_scarcity(年) × exposure。目的の年の順位は logit(B_env の既存の面) + β × mast_scarcity(目的の年) × exposure。
- 目的の年: 2025 年度 (既存の B2 の面)、2026 年度 4〜9 月 (既存の B3 の面)。比べる相手は既存の B_env。
- 指標: capture@5% (主)、capture@10%、件数で重みを付けた capture@5%。10 km ブロックの復元抽出 (1,000 回、種 0) の 90% 区間。

変えるのは、β を当てるときの学習の年度の offset だけ。

## cross-fit の B_env

既存の `projects/akita-bear-risk-grid-100m/scripts/model_eval.py` の `run_models(..., models=["B_env"])` をそのまま呼ぶ (28 の静的な特徴量、`HistGradientBoostingClassifier`、同じハイパーパラメータ、ラベル = その年度に通報が 1 件以上、県内の全セル、random_state 0)。学習の年度だけを変える。B_env の特徴量は静的なので、スコアはセルごとに 1 つで、どの年度を採点するかによらない。

| 目的 | β を当てる年度 | その年度の offset に使う B_env の学習の年度 |
|---|---|---|
| 2025 年度 | 2023 | 2024 |
| 2025 年度 | 2024 | 2023 |
| 2026 年度 | 2023 | 2024、2025 |
| 2026 年度 | 2024 | 2023、2025 |
| 2026 年度 | 2025 | 2023、2024 |

学習する組は {2024}、{2023}、{2024, 2025}、{2023, 2025}、{2023, 2024} の 5 つ。{2023} と {2023, 2024} は既存の b1 と b2 の B_env と同じ組なので、保存済みのスコア (float32) と一致することを確かめ、手順が既存と同じである証拠にする (一致しなければ止まって記録する)。

## 先に確かめること (β を当てる前)

年度 (2023、2024、2025) ごとに、cross-fit のスコアと in-sample のスコア (元の確認で使った面: 2025 年度の目的では b2、2026 年度の目的では b3) の両方について:

- capture@5%、AUC、AP
- 陽性と陰性のセルのスコアの分布 (分位点)
- 2 つのスコアの Spearman と、性能の差 (in-sample − cross-fit)

読み方: in-sample の性能が cross-fit よりはっきり高ければ (capture@5% で 0.01 以上)、学習の年度の通報への当てはまりが in-sample の側にある、と書く。ここでは mast × exposure との関係は見ない。

## β の当て直しと読み方

- 出す値 (目的の年ごと、retrospective と operational): β、SE、β × mast_scarcity(目的)、capture@5% の差と 90% 区間、capture@10% の差、件数の重み付き capture@5% の差。元の in-sample の β と並べる。
- 3 つの型 (先に決める):
  - C: capture@5% の差が 2025 年度と 2026 年度の両方で正かつ 90% 区間の下限が正 (retrospective)。元の null に stacking の設計による false negative の可能性がある、と書く。この場合も「仮説の支持」とは呼ばず、別の事前登録の実験を立て直す候補とする。F1、F2 を既存の仕様のまま流し直す。
  - B: C でなく、cross-fit の β が少なくとも一方の目的の年で |β| / SE ≥ 1.96、かつ元の |β| の 3 倍以上。学習の残差には信号らしきものがあるが、未来の年度へは一般化しない、として閉じる。
  - A: C でも B でもない。今回の null は in-sample の offset だけでは説明できない、として mast × static beech/oak exposure の枝を完全に閉じる。
- operational は並べて出すが、型の判定は retrospective で行う。
- 新しい特徴量、半径、植生の分類、mast の変換、モデルの族、並べ替えの設計は足さない。

## commit の単位

1. この計画
2. cross-fit の B_env の生成と確かめ
3. β の当て直しと目的の年の採点
4. (C のときだけ) 並べ替え
5. 短い診断の報告 (`report_crossfit.md`)

## 計画の変更

| 日時 | 何を見た後に | 何を変えたか | 理由 | 結論への影響 |
|---|---|---|---|---|
