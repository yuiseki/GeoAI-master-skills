# CP-SAT による容量付き単一割当配置と時間枠スケジューリング

OR-Tools CP-SAT (`ortools.sat.python.cp_model`) を使って、出発地を分けない容量付き施設配置 (単一割当 CFLP) と、複数チームの時間枠付き巡回スケジューリングを解く (`scripts/cpsat_location.py`)。

## 手法の仮定と性質

- CP-SAT は決定変数と係数を整数で扱う。浮動小数点の距離や移動時間は `scale` 倍 (既定 100) して整数に丸める。丸めによる誤差が問題になる精度 (10^-3 未満の差など) では `scale` を大きくするか、連続変数の MILP (`scipy.optimize.milp`) を使う。
- 単一割当 CFLP (`solve_cflp`) は各需要点 i をちょうど 1 つの開設施設 j に割り当てる (`sum_j x[i, j] == 1`)。1 つの需要点の需要量 w[i] が最大施設容量 max(s) を超える場合、総容量 sum(s) >= sum(w) であっても実行不能になる (輸送問題との違い)。
- 時間枠スケジューリング (`solve_schedule`) は `AddCircuit` による部分巡回除去と `AddNoOverlap` による時間重複禁止を組み合わせ、各チームが拠点 (index 0) から出発して拠点へ戻る閉路を構成する。目的は全チームの合計移動時間の最小化。
- 解が得られた後、元の浮動小数点の距離行列・移動時間行列と元の容量・時間枠を用いて目的値と制約違反を直接再計算し、ソルバの内部スケーリング値に依存せず検証する (`cflp_recompute`)。

## 答えの分かる小さな例と合成データ

- 4 需要点・2 候補地の単一割当 CFLP (手計算で最適目的値と割当が一意に定まる例) で、開設施設・割当・再計算目的値が手計算と一致することを確認済み (`test_cpsat_location.py::test_cflp_hand_calculated`)。
- 総容量 >= 総需要であっても、1 需要点の需要が各施設の容量を超える合成データで単一割当が実行不能 (infeasible) になることを確認済み (`test_cflp_single_source_infeasible`)。
- 小規模インスタンス (4 乱数種) で総当たり (全列挙) と最適目的値が一致することを確認済み (`test_cflp_matches_brute_force`)。
- 下界: 手計算の丸めの幅 (`test_rounding_slack_by_hand`)、丸めで費用が増える 1 需要点の例で下界が真の最適 1.06 を超えないこと (`test_cflp_bound_survives_costs_rounded_up`)、総当たりの最適値を下界が超えないこと (4 乱数種)、丸めの無い費用で幅とギャップが 0 になること、需要が 1/scale の倍数でないとき元の問題の下界を出さないこと、下界より下の実行可能解で止まることを確かめている。幅の向き、開設費の項、需要ごとの最大、倍数の判定、下界より下の検査のそれぞれを外すと、テストが落ちる。
- 時間枠付きスケジューリングで、時間帯が競合する 2 タスクを 1 チームで回れず 2 チームに分割される例、および移動時間を考慮した到着時刻が時間枠内に収まることを確認済み (`test_schedule_time_windows_and_travel`, `test_schedule_multi_team_split`)。

## 他の実装との照合

- `scipy.optimize.milp` (HiGHS) で定式化した同一の単一割当 CFLP と、`solve_cflp` の結果を 5 つの乱数種・設定で照合し、最適目的値が一致することを確認済み (`test_cpsat_crosscheck.py`)。

## 使えない条件

- 需要を複数施設に分割して割り当てたい場合は単一割当 CFLP ではなく輸送問題 (`references/transport.md` / `scripts/transport.py`) を使う。
- 施設数・タスク数が大きく (例えば施設 > 50、タスク > 100)、時間枠や容量が密に絡む大規模問題では CP-SAT が `time_limit_s` 内に最適証明 (`OPTIMAL`) に達せず `FEASIBLE` (実行可能解) で止まることがある。下の「解の言い方の段」に従い、下界とギャップを書く。
- 車両の容量・時間枠・複数デポなど複雑な VRP 制約が主目的の場合は VROOM (`references/vrp.md` / `scripts/vrp_routing.py`) の方が高速に良い解を出しやすい。

## 解の言い方の段 (CFLP)

ソルバーの状態を、そのまま元の問いの答えと読まない。言い方は、届いた段より強くしない。

1. 候補: ソルバーが返した解。まだ何も確かめていない。
2. 実行可能: 元の距離、需要、容量で、割当と容量を全て検算した (`cflp_recompute`。通らなければ止まる)。
3. 下界つき: 元の単位の下界 `bound` があり、`gap` = (解の値 − 下界) / 解の値 で、最適からどれだけ離れうるかが言える。
4. 最適: `status` が `optimal`。ただし CP-SAT が証明するのは、費用を `scale` 倍して整数に丸めた模型の中での最適。元の単位では、`gap` の幅の中での最適と書く。
5. 別の実装と一致: HiGHS の MILP や総当たりと同じ値 (`test_cpsat_crosscheck.py`、小さな問題だけ)。

`solve_cflp` が返す下界の作り方:

- CP-SAT の下界 (`BestObjectiveBound`) は丸めた費用の模型のもの。丸めで費用が増えた分を、解が使いうる項について足し上げ (`rounding_slack`: 需要ごとに使える候補の中で最も増えた分と、開設費の増えた分の大きい順に p 個)、それを引くと元の単位の下界になる。費用が 1/scale の倍数なら、引く分は 0。
- 需要と容量が 1/scale の倍数でないと、容量の行そのものが丸められ、元の問題の解を丸めた模型が受け付けない場合がある。そのときは元の問題の下界とは言えないので、`bound` と `gap` を出さず (`bound_scope` が `rounded_model`)、丸めた模型の下界だけを `rounded_model_bound` に残す。`scale` を上げて倍数にするか、需要と容量の単位を変える。
- 元の問題で実行可能な解 (CP-SAT の解と発見的な解) が下界より下なら、模型か丸めが間違っているので止まる。
- 時間切れ (`UNKNOWN`) は、解が無いことの証拠にならない。止まるときにそう書く。

合成の 60 需要点、25 候補地、p = 6 (乱数種 7、1 スレッド) で、上限を変えた:

| 上限 | 状態 | 解の値 | 下界 | ギャップ |
|---:|---|---:|---:|---:|
| 0.05 秒 | feasible | 3,624.2 | 1,347.1 | 63% |
| 0.5 秒 | feasible | 2,326.8 | 2,076.4 | 11% |
| 5 秒 | optimal | 2,261.1 | 2,260.8 | 0.01% |

0.05 秒の解は最適より 60% 悪いが、状態だけを見ると「解けた」と読める。報告には状態と並べて下界とギャップを書く。この考え方は LLM4MIP (MIPLIB の未解決問題に LLM のエージェントを当てた研究、MIT) のスキルの、証拠の段に応じて言い方を決める規則から取った (`docs/related-work.md`)。

## 使い方とテスト

```sh
uvx --with numpy --with ortools --with duckdb --with pytest pytest .agents/skills/spatial-optimization/scripts/test_cpsat_location.py
uvx --with numpy --with scipy --with ortools --with pytest pytest .agents/skills/spatial-optimization/scripts/test_cpsat_crosscheck.py
```

CLI 実行例 (単一割当 CFLP):

```sh
python .agents/skills/spatial-optimization/scripts/cpsat_location.py cflp \
  --demands demands.csv --sites sites.csv --od od.csv --p 2
```
