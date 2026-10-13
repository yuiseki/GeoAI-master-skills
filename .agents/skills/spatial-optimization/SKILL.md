---
name: spatial-optimization
description: 施設の配置などの選択問題を、決定変数、目的、制約に定式化して解き、手で組める発見的な解と比べ、選んだ解から目的を計算し直して確かめる。設定 (p、半径、距離の測り方) を変えて答えの変わり方も見る。どこに置くか、どう割り当てるかを決める問いに使う。
---

# spatial-optimization

ソルバーが「最適」と言うのは、与えたモデルの中での最適でしかない。モデルが問いと違えば、最適な答えは間違った答え。解いたら、選んだ解から目的を計算し直し、手で組める解と比べる。最適解が手で組んだ解より悪ければ、モデルが間違っている。

| reference | 問題 |
|---|---|
| [p-median](references/p-median.md) | p か所を選び、需要から最寄りの施設までの重み付きの距離の合計を最小にする |
| [coverage](references/coverage.md) | p か所を選び、一定の距離以内に入る需要の重みを最大にする |

割当、輸送、LP の双対、CP-SAT、多目的はまだ書いていない (TODO.md)。

## 手順

1. 問いを、決定変数 (何を選ぶか)、目的 (何を良くするか)、制約 (何を守るか) で書く。言葉の問いと式がずれていないかを、小さな例で手で確かめる。
2. 入力を作る。需要の点と重み (WorldPop の人口など)、候補地、距離行列 (spatial-network-analysis の `road_network.py matrix`)。たどり着けない組があれば先に扱う。
3. `scripts/facility_location.py` で、MILP と発見的な解の両方で解く。スクリプトは、選んだ施設から目的を計算し直し、ソルバーの値と食い違うか、最適解が発見的な解より悪ければ止まる。
4. 設定を変えて解き直す。p、半径、距離の測り方 (道のりか直線か)、需要の重み。答え (目的の値と選ぶ場所) がどう変わるかを書く。
5. 解の意味を確かめる。選んだ場所を地図で見る。目的の値を、1 単位の需要あたりの距離のような分かる量に直す。
6. 書き出す。

```sh
uvx --with numpy --with scipy --with duckdb python scripts/facility_location.py \
  tmp/matrix.parquet tmp/demand.parquet --problem p-median --p 1 3 5 10
uvx --with numpy --with scipy --with duckdb python scripts/facility_location.py \
  tmp/matrix.parquet tmp/demand.parquet --problem coverage --radius 500 --p 3 5 10
```

テストは `uvx --with numpy --with scipy --with duckdb --with pytest pytest scripts/test_facility_location.py`。小さな問題で、MILP が全ての組み合わせの総当たりと同じ最適値を出し、発見的な解はそれより悪くないこと、目的を計算し直すこと、どの候補にも届かない需要で止まること、施設の選び方が悪いのに自分の値は正しく報告する「最適解」を、発見的な解との比較で捕まえることを確かめている。割当の制約を外す、被覆の制約を外す、発見的な解との比較を外す、目的を計算し直さない、のそれぞれで落ちることを確かめてある。

## 書き出すもの

- 問いの言葉と、決定変数、目的、制約
- 需要、候補地、距離の作り方と数
- 設定ごとの MILP の状態と値、発見的な解の値、解くのにかかった時間
- 選んだ場所と、設定を変えたときの変わり方
- 目的を分かる量に直したもの (1 人あたりの距離、被覆の割合)
