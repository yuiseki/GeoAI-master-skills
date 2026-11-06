# 計画: Porto のタクシーの行き先の予測 (ECML/PKDD 2015) を再現する

流す前に書く。流した後に書き直さない。直すなら末尾の「計画の変更」に足す。

## 問いと使い道

- 問い: 走行中のタクシーの軌跡の始まり (接頭) と、呼ばれ方や時刻などの付随情報から、行き先を当てる課題で、論文の優勝モデル (行き先の塊の重み付き平均を出す MLP、de Brébisson ほか 2015) を、論文と同じ試験の作り方で再現できるか。再現できたとき、単純な基準 (接頭の最後の点) に対する差は、学習より後の時期の試験でも保たれるか。
- 使い道: 軌跡の予測のスキル (`trajectory-prediction`) の手順を、答えの分かっている定番の課題で確かめてから書く。再現できなければ、スキルにしない。
- 問いの種類: 予測。

## データ

- UCI Machine Learning Repository 339「Taxi Service Trajectory - Prediction Challenge, ECML PKDD 2015」(CC BY 4.0、doi:10.24432/C55W25)。`train.csv` (約 171 万本の全軌跡、15 秒ごとの点)、`Porto_taxi_data_test_partial_trajectories.csv` (競技の試験の 320 本の接頭)、`solution_fixed.csv` (その行き先)。
- 原本は `artifacts/_benchmark/taxi-destination-porto/raw/` に置き、SHA-256 を `outputs/sources.csv` に書く。原本はリポジトリに入れない。

## 論文の値 (比べる相手)

論文の表 2 の優勝モデル (MLP、塊、付随情報の埋め込みあり): 自前の試験 2.81 km、Kaggle の公開の試験 2.39 km、非公開の試験 1.878 km。埋め込みなし 2.93 km。

論文の試験の作り方 (著者のコードの `data/cuts/tvt_test.py`、`data/make_tvt.py` で確かめた): 学習の期間 (2013-07-01〜2014-06-30) から一様に選んだ 500 の時刻で、その時刻に走っていた軌跡をその時刻で切る。試験と検証の軌跡は学習から除く。

## 方法

- 前処理: 点の無い軌跡を除く。行き先は軌跡の最後の点。距離は半径 6371 km の haversine (競技の指標)。
- 分け方:
  - 自前の試験 S_rand: 学習の期間から一様に選んだ 500 の時刻 (種 42 を使うが、著者の時刻の列は写さず、自分で作る) で切る。検証 V_rand は別の 500 の時刻 (種 1337)。この 2 つに入った軌跡は学習から除く。
  - Kaggle の試験 S_kaggle: 320 本。正解は `solution_fixed.csv`。
  - 後の時期の試験 S_late (頑健性): 2014-04-01 以降に始まる軌跡を学習から除き、2014-04-01〜06-30 の 500 の時刻で切る。比べる相手は、同じ学習 (2014-03-31 まで) で、2013-07-01〜2014-03-31 の 500 の時刻で切った S_early。学習は S_early の軌跡も除く。
- 学習の接頭: 学習の軌跡を長さに比例する確率で選び、その中の切る位置を一様に選ぶ (全ての接頭からの一様な抽出。論文 2.1 と同じ分布)。
- モデル:
  - M0 ポルトの中心 (全ての学習の行き先の中央値の点) を常に予測する。
  - M1 接頭の最後の点を予測する。
  - M2 優勝モデル: 接頭の最初の 5 点と最後の 5 点 (足りなければ端の点を繰り返す、標準化) と、付随情報 7 つ (電話の客、乗り場、年の週、曜日、15 分刻みの時刻、日の種類、タクシー) の 10 次元の埋め込みを連ね、ReLU 500 の隠れ層 1 つ、行き先の塊への softmax の重みで塊の中心を平均して出す。損失は equirectangular の距離。塊は学習の行き先の mean-shift (帯域 0.001 度、bin seeding、最小 5)。最適化は momentum 0.9、学習率 0.01、batch 200 (著者の設定ファイル)。
  - M3 M2 から埋め込みを除いたもの (論文の model 3)。
- 計算の予算: CPU 4 コア (GPU は使わない)。著者は GPU で半日学習している。試走で 1 step の時間を測り、M2 と M3 の step 数を、試験の点を見る前に記録に書いて固定する。検証の点で早期終了する (最良の検証の時点の重みを使う)。
- 乱数: 学習の種を固定し、記録に書く。

## 主張の地図

| claim_id | 主張 | 効く判断 | 区画 |
|---|---|---|---|
| C0 | 手順 (切り方、指標、基準) は論文の設定を写している | 先へ進むか | B0 |
| C1 | M2 は S_rand で論文の 2.81 km に近い誤差を出し、M1 と M0 より小さい | スキルにしてよいか | B1 |
| C2 | M2 の M1 に対する差は、後の時期の試験でも保たれる | スキルに時期のずれの注意を書くか | B2 |
| C3 | 付随情報の埋め込みは誤差を下げる (M3 > M2) | 論文の切り分けの再現 | B3 |

## 区画

### B0: 手順の確かめ (sanity)

- claim tested: C0
- mode: confirmatory
- observable quantity: (a) S_kaggle での M0 の誤差を、競技の公開の基準 (常にポルトの中心) の値と並べる。(b) S_rand と V_rand の本数を論文 (19,770、19,427) と並べる。(c) テストで、haversine の手計算、切る位置、端の繰り返し、接頭の抽出の分布 (長さに比例) を確かめる。
- decision rule: テストが通り、(b) の本数が論文の ±30% に入れば先へ進む。外れたら切り方を見直し、止める。(a) は公開の基準の値が手に入らなければ記録だけにする
- failure interpretation: 切り方か読み方が論文と違う
- priority / run order: sanity、順番 1

### B1: 再現 (decisive)

- claim tested: C1
- mode: confirmatory
- data / analysis unit: 接頭 1 本
- observable quantity: S_rand と S_kaggle の、M0〜M2 の平均 haversine 誤差 (km)
- comparator / control: 論文の 2.81 km (S_rand)、M1、M0
- uncertainty: S_rand は切る時刻ごとの塊のブートストラップ (2,000 回) の 95% 区間。同じ時刻の軌跡は同じ道の混み方を共有するので、軌跡ごとには振らない。S_kaggle は 5 つの時刻しかないので、軌跡ごとのブートストラップを参考に書くだけ
- decision rule: S_rand で M2 の誤差が 3.1 km 以下 (論文の 2.81 の 1.1 倍) で、M2 の区間の上限が M1 の区間の下限より小さければ「再現した」。3.1 を超えれば「再現しない」とし、予算の不足か手順の違いかを書いて、スキルにしない
- failure interpretation: 学習の予算が足りない、塊か入力の作り方が違う
- alternative explanation being tested: 論文の点は GPU の長い学習でしか出ない
- priority / run order: decisive、順番 2

### B2: 後の時期 (robustness)

- claim tested: C2
- mode: confirmatory
- observable quantity: 2014-03-31 までで学習し直した M2 と M1 の、S_early と S_late での誤差と、その差 (M1 − M2)
- uncertainty: B1 と同じ塊のブートストラップ
- decision rule: S_late での差 (M1 − M2) の区間が 0 より上なら「保たれる」。S_late の差が S_early の差の半分未満なら「時期で大きく縮む」と書く
- failure interpretation: 行き先の分布か付随情報の意味が時期で変わる
- priority / run order: robustness、順番 4

### B3: 埋め込みの切り分け (exploratory)

- claim tested: C3
- mode: exploratory
- observable quantity: S_rand での M3 と M2 の誤差の差
- decision rule: なし (論文の 2.93 対 2.81 と向きが同じかを書く)
- priority / run order: 順番 3

## 計画の変更

| 日付 | 変更 | 結果を見た後か | 理由 |
|---|---|---|---|
