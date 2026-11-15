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
- 時間枠付きスケジューリングで、時間帯が競合する 2 タスクを 1 チームで回れず 2 チームに分割される例、および移動時間を考慮した到着時刻が時間枠内に収まることを確認済み (`test_schedule_time_windows_and_travel`, `test_schedule_multi_team_split`)。

## 他の実装との照合

- `scipy.optimize.milp` (HiGHS) で定式化した同一の単一割当 CFLP と、`solve_cflp` の結果を 5 つの乱数種・設定で照合し、最適目的値が一致することを確認済み (`test_cpsat_crosscheck.py`)。

## 使えない条件

- 需要を複数施設に分割して割り当てたい場合は単一割当 CFLP ではなく輸送問題 (`references/transport.md` / `scripts/transport.py`) を使う。
- 施設数・タスク数が大きく (例えば施設 > 50、タスク > 100)、時間枠や容量が密に絡む大規模問題では CP-SAT が `time_limit_s` 内に最適証明 (`OPTIMAL`) に達せず `FEASIBLE` (実行可能解) で止まることがある。解のステータス (`status`) とギャップを確認する。
- 車両の容量・時間枠・複数デポなど複雑な VRP 制約が主目的の場合は VROOM (`references/vrp.md` / `scripts/vrp_routing.py`) の方が高速に良い解を出しやすい。

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
