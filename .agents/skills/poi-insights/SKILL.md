---
name: poi-insights
description: 施設 (POI) をカテゴリ、ブランド、営業状態、信頼度で取り出し、H3 や S2 の格子で数え、Gi* と多重比較の補正で集積とクラスターを見つけ、地域ごとに密度、人口あたりの数、ブランドの寡占 (HHI)、近くの競合、人口の近さを比べる。オープンな POI (Overture Maps の places、OpenStreetMap) で、商用の Places Insights と同じ問いに答え、データに無い属性 (評価、営業時間など) を答えから外す。
---

# poi-insights

「どこに何の店が集まっているか」「どの地域が足りないか」に、オープンな POI で答える。店の数を格子で数えて多い所を並べるだけでは、どこにでもある店の多さと、本当に集まっている所が区別できない。空のセルを含む全体と比べて集積を判定し、格子の大きさで答えがどう変わるかを並べて書く。

別の問いとの境界:
- 点がどの距離で集まっているかを、比べる基準の分布 (人口など) と比べるのは、点の配置の検定の問い。ここでは格子の上の集積の場所と、地域の比較を扱う。
- 店まで道のりで何分かかるかは、到達性の問い。ここでの近さは直線の距離。
- 店の数を予測するのは、ここでは扱わない。

| reference | 読むとき | 中身 |
|---|---|---|
| [grids-and-hotspots](references/grids-and-hotspots.md) | 格子の大きさと、集積の判定のしかたを決める前 | H3 と S2 の解像度と面積、Gi* の式と重み、多重比較の補正、クラスターのつなぎ方、解像度で答えが変わること |
| [attributes-and-gaps](references/attributes-and-gaps.md) | どの属性で絞るかを決める前、商用の POI と比べた答えを書く前 | カテゴリ、ブランド、営業状態、信頼度、出どころの扱い。商用の POI にあってオープンな POI に無い属性と、その影響 |
| [compare-regions](references/compare-regions.md) | 地域の比較 (`poi_compare.py`) を流す前 | 密度、人口あたり、HHI、競合の距離、人口の近さの定義と注意 |

## 手順

1. 問いを 1 行で書く。何の施設を、どの範囲で、何のために数えるか。使い道 (出店の候補、競合の確認、足りない地域の発見) を書く。
2. POI のデータの版、ライセンス、範囲を決め、版を固定する。範囲の全ての行を 1 回だけ写し、以降はその写しを読む。
3. 使う属性を決める ([attributes-and-gaps](references/attributes-and-gaps.md))。カテゴリは階層のどこかに含むかで取る。営業状態の欠けは「不明」として残し、営業中と数えない。信頼度で絞るなら、絞らない場合と並べる。
4. `scripts/poi_extract.py` で取り出す。範囲の全ての行が、他のカテゴリ、除いた営業状態、低い信頼度、採用のどれかに数えられ、合わなければ止まる。
5. `scripts/grid_hotspots.py` で、格子 (H3 の解像度、または S2 のレベル) ごとに数え、Gi* で集積を判定し、隣り合う集積セルをクラスターにする ([grids-and-hotspots](references/grids-and-hotspots.md))。解像度を少なくとも 3 段変え、クラスターの数と最大の集積がどう変わるかを書く。
6. 地域で比べるなら、地域の面 (行政区域など) と、人口の格子 (H3 のセルと人口) を用意し、`scripts/poi_compare.py` で比べる ([compare-regions](references/compare-regions.md))。
7. 別のデータ (OpenStreetMap など) と、格子ごとの数とブランドの数で照合する。一致しない所は、どちらの取りこぼしかを確かめるまで、結論に使わない。
8. 地図 (PNG) と表を書き出す。

```sh
uvx --from 'duckdb>=1.5.5' python scripts/poi_extract.py PLACES.parquet tmp/coffee.parquet \
  --bbox -0.52 51.28 0.34 51.70 --category coffee_shop --exclude-status permanently_closed
uvx --with h3 --with s2sphere --with numpy --with scipy --with duckdb python scripts/grid_hotspots.py tmp/coffee.parquet tmp/h3r9 \
  --grid h3 --res 9 --bbox -0.52 51.28 0.34 51.70 --group brand
uvx --from 'duckdb>=1.5.5' --with numpy --with scipy --with h3 python scripts/poi_compare.py tmp/coffee.parquet regions.parquet \
  tmp/regions.csv --population population_h3.parquet --within-m 500
```

## 書き出すもの

- 問い、使い道、データの版とライセンス、範囲の件数
- 抽出の数 (他のカテゴリ、除いた営業状態、低い信頼度、採用)、営業状態不明の数
- 格子の種類と解像度、集積の判定 (重み、補正、有意水準)、クラスターの数と上位の場所 (地図)
- 解像度と信頼度の絞り方を変えたときの違い
- 地域の比較の表 (定義を添えて)
- 別のデータとの照合の結果
- データに無い属性と、それで答えられない問い
- 確かめていないこと
