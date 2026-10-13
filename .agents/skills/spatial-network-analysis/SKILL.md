---
name: spatial-network-analysis
description: 道路などの線のデータからネットワークを作り、道のりの距離、到達圏、道のりと直線距離の比を測る。直線距離では足りない問い (歩いて何分か、どこまで届くか) や、施設配置などの最適化に渡す距離行列を作るときに使う。
---

# spatial-network-analysis

直線距離は、川、線路、行き止まりを知らない。人や車が動く距離を問うなら、道のりで測る。道のりはネットワークの作り方 (どの道を入れるか、どこでつなぐか、範囲をどこで切るか) で決まるので、作り方を書く。

| reference | 中身 |
|---|---|
| [building-the-graph](references/building-the-graph.md) | Overture の道路からネットワークを作る。どの道を入れるか、連結成分、範囲の端 |
| [measures](references/measures.md) | 道のりの距離、点の寄せ方、到達圏、迂回率 |

## 手順

1. 何が動くか (歩行者、車、自転車) と、問いを書く。
2. 道路を範囲で切り出す (dataset-discovery の references/overture/)。問いの範囲より広めに切る。範囲の端では外への道が切れる。
3. `scripts/road_network.py build` で、動くものに合った道の種類だけでネットワークを作る。連結成分の数と、最大の成分の割合を見る。
4. 点 (出発地、目的地) を最大の連結成分の節点に寄せ、寄せた距離を書く。寄せた距離が大きい点は、道路の無い場所か、範囲の外にある。
5. 測る (到達圏、迂回率、距離行列)。たどり着けない組は、数を書き、0 や大きな値で埋めない。
6. 書き出す。

```sh
uvx --with numpy --with scipy --with scikit-learn --with shapely --with duckdb --with pyarrow \
  python scripts/road_network.py build tmp/roads.parquet \
  --exclude-classes footway,steps,path,pedestrian,cycleway,bridleway,track \
  --out-edges tmp/drive_edges.parquet --out-nodes tmp/drive_nodes.parquet
uvx ... python scripts/road_network.py reach tmp/drive_edges.parquet tmp/drive_nodes.parquet \
  --lon 139.7774 --lat 35.7141 --within 500 1000 2000
uvx ... python scripts/road_network.py detour tmp/drive_edges.parquet tmp/drive_nodes.parquet --pairs 2000
uvx ... python scripts/road_network.py matrix tmp/walk_edges.parquet tmp/walk_nodes.parquet \
  --origins tmp/demand.parquet --destinations tmp/candidates.parquet --out tmp/matrix.parquet
```

`matrix` は、出発地と目的地 (どちらも id、lon、lat の表) を最大の連結成分の節点に寄せ、全ての組の道のり、直線距離、寄せた距離を書き出す。道のりは寄せた節点の間のもので、寄せた距離は足していない。施設配置などの最適化の入力にできる。

テストは `uvx --with numpy --with scipy --with scikit-learn --with shapely --with duckdb --with pytest pytest scripts/test_road_network.py`。線の長さが大円距離であること、線を connector の位置で切り、並びが順でなくても正しく切ること、折れ線の後の区間の上の connector をその区間に置くこと、最短経路が共有の connector を通ること、つながらない組が無限大であること、点を大円距離で最寄りの節点に寄せ、孤立した小片を避けられること、同じ 2 点を結ぶ道が 2 本あれば短いほうを使うことを確かめている。connector を並べ替えない、寄せるときに経度と緯度を取り違える、平行な道の長いほうを取る、節点を最初の区間にしか置かない、のそれぞれで落ちることを確かめてある。

## まだできないこと

- 一方通行と、曲がれない交差点 (`prohibited_transitions`)。ネットワークは向きの無いグラフ。車の道のりは実際より短く出うる。
- 速度。道のりの距離だけで、時間ではない。`speed_limits` と道の種類から時間にするのは未実装。
- 高さ (`level_rules`)。立体交差でも、connector を共有していればつながる。共有していなければつながらない (Overture の側でそう表されている)。

## 書き出すもの

- 動くもの、入れた道の種類、切り出した範囲
- 節点、辺、総延長、連結成分の数と最大の成分の割合
- 点の寄せた距離、最大の成分に寄せ直した点
- 測ったもの (到達圏、迂回率、距離) と、たどり着けない組の数
- まだできないことのうち、結論に効きうるもの
