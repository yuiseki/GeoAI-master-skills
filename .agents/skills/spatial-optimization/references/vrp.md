# VROOM (pyvroom) による配車・巡回ルート最適化 (CVRP / VRPTW)

VROOM (`pyvroom`) を使って、容量制約・時間枠制約付きの複数車両配車計画問題 (CVRP / VRPTW) を解く (`scripts/vrp_routing.py`)。自前の移動時間行列・コスト行列をそのまま受け取り、OSRM/Valhalla サーバを立てずにローカルで高速に解ける。

## 手法の仮定と性質

- VROOM はメタヒューリスティック (局所探索と大規模近傍探索) であり、大域的最適解の証明は出さない。ただし小〜中規模の問題では高精度な解をミリ秒〜数秒で返す。
- `pyvroom` の内部行列 (`_vroom.Matrix`) は符号なし 32 bit 整数 (`uint32` / C の `unsigned int`) を要求する。Windows 環境では `numpy.asarray(x, dtype="uint32")` がバッファ形式 `'L'` となり `RuntimeError: Incompatible buffer format!` を起こすため、`np.uintc` (形式 `'I'`) で `_vroom.Matrix` を直接構築して渡す (`_to_vroom_matrix`)。
- 浮動小数点の移動時間・時間枠・作業時間は `scale` 倍 (既定 100) して整数に丸めて渡す。
- VROOM は全顧客を回れない場合でもエラーで止まらず、一部の顧客を `unassigned` として残りのルートを返す (`status == "PARTIAL"`)。
- 解が得られた後、返されたルート列から元の浮動小数点の行列・容量・時間枠で総移動時間・総コスト・容量制約・時間枠制約を直接再計算し、単純な最近傍ヒューリスティック (`vrp_nearest_neighbor_heuristic`) と並べて返す (`vrp_recompute`)。

## 答えの分かる小さな例と合成データ

- 4 地点の対称 TSP (手計算で最適距離 4.0) で、VROOM が最適巡回と一致することを確認済み (`test_vrp_routing.py::test_tsp_hand_calculated`)。
- 需要 4 の 2 顧客・容量 6 の 2 車両の CVRP で、2 台に分割されて総移動時間 22.0 になることを確認済み (`test_cvrp_capacity_split`)。
- 時間枠が順序を強制する VRPTW で、時間枠を満たす順序 (`[2, 1]`) が選ばれることを確認済み (`test_vrptw_time_window_forces_order`)。
- 総容量不足の合成データで `status == "PARTIAL"` と未割当顧客を正しく報告することを確認済み (`test_vrp_unassigned_when_capacity_exceeded`)。
- 6 地点 TSP (4 乱数種) で総当たり (全列挙) と最適距離が一致し、最近傍ヒューリスティック以下の距離になることを確認済み (`test_tsp_matches_brute_force`)。
- 制約違反を埋め込んだ偽のルートに対して `vrp_recompute` が容量違反と時間枠違反を検出することを確認済み (`test_recompute_detects_capacity_and_tw_violation`)。

## 他の実装との照合

- 5 つの乱数種の小規模 VRPTW インスタンス (デポ + 4 タスク、2 車両) で、`cpsat_location.solve_schedule` (OR-Tools CP-SAT による厳密最適解) と `solve_vrp` (pyvroom) の総移動時間が一致することを確認済み (`test_vrp_crosscheck.py`)。

## 使えない条件

- 大域的最適性の証明や双対値・下限値が必要な場合は MILP (`scipy.optimize.milp`) または CP-SAT (`references/cp-sat.md`) を使う。
- 移動時間行列そのもの (道路網上の最短経路や時刻別の混雑) は本スクリプトでは作らない。事前に道路ネットワークから OD 行列を計算して渡す。
- 時間帯によって移動時間が変わる (time-dependent travel times) 問題や、確率的な需要・移動時間は VROOM の静的行列モデルではそのまま扱えない。

## 使い方とテスト

```sh
uvx --with numpy --with pyvroom --with duckdb --with pytest pytest .agents/skills/spatial-optimization/scripts/test_vrp_routing.py
uvx --with numpy --with pyvroom --with ortools --with pytest pytest .agents/skills/spatial-optimization/scripts/test_vrp_crosscheck.py
```

CLI 実行例:

```sh
python .agents/skills/spatial-optimization/scripts/vrp_routing.py \
  --matrix od.csv --jobs jobs.csv --vehicles vehicles.csv
```
