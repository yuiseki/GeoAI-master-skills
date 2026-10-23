---
name: thematic-mapping
description: 空間の値や分析の結果 (件数、率、水準、クラス、残差、変化) を、量と意味を壊さず、比べられる地図 (塗り分け図) にする。値の種類から色の型を決め、区切り方 (等間隔、分位、Fisher-Jenks、意味のある固定の線) を並べてクラスの入れ替わりを数え、複数の地域や時点では区切りを共通にするかを決め、NoData を 0 と別に描き、凡例に単位を、地図に CRS と版と区切り方を残す。分析全体の報告の組み立ては扱わない。
---

# thematic-mapping

塗り分け図は、区切り方と色で見え方が大きく変わる。同じ値でも、等間隔なら全体がほぼ 1 色になり、分位なら全ての色が同じ面積を占める。地図を描く前に、値の種類、区切り方、比べる相手を決め、決めたことを地図と一緒に残す。

このスキルが答えるのは、「この値を、どの区切り、どの色、どの凡例で描けば、問いに対して誤解を生まないか」まで。何を分析するか、地図を報告書にどう組み込むかは、このスキルの外。

| reference | 中身 |
|---|---|
| [classification](references/classification.md) | 区切り方ごとの見え方 (歪んだ値で、クラスの割合と入れ替わる単位の数)、Fisher-Jenks、mapclassify との照合 |
| [color-and-scale](references/color-and-scale.md) | 値の種類と色の型、虹色を避ける理由、NoData と 0、件数をそのまま塗るか、色覚の多様性での見え方 (`scripts/cvd.py`) |
| [comparable-maps](references/comparable-maps.md) | 複数の地域や時点を並べるときの、共通の区切りと個別の区切り |

## 手順

1. 値の種類を決める (`--kind`)。件数 (count)、率 (rate)、水準 (level)、クラス (category)、残差 (residual)、変化 (change)。件数なら、そのまま塗ってよいかを先に疑う。大きな単位ほど件数は多い。問いが件数そのもの (どこに何件あるか) でなければ、率か密度にしてから描く ([color-and-scale](references/color-and-scale.md))。
2. 色の型を決める。件数、率、水準は順序の色 (明るさが値の順に並ぶ)、残差と変化は中央から分かれる色 (中央は 0 か基準の値、`--centre`)、クラスはクラスの色。虹色 (rainbow、jet、turbo など) は使わない。種類に合わない色はスクリプトが止める。
3. 区切り方を決める (`--method`)。値の意味のある線 (基準、法の上限、政策の閾値) があれば固定の線 (`fixed`)。無ければ、問いに合わせて選ぶ。分布の形だけから機械的に選ばない。
4. 他の区切り方と比べる (`--compare`)。クラスが入れ替わる単位の割合を見る。入れ替わりが大きいなら、地図の印象は区切り方の選択に依存すると書き、2 通りの地図を並べることを考える ([classification](references/classification.md))。
5. 複数の地域や時点を並べるなら、区切りを共通にするか、それぞれで決めるかを決めて書く (`--groups`)。比べたいのが水準の違いなら共通の区切り。それぞれの中の並びなら個別の区切り ([comparable-maps](references/comparable-maps.md))。
6. 描く (`--png`)。欠損と NoData は 0 と別の色と模様にし、凡例にその数を書く。凡例の題に値と単位を書き、地図に区切り方、CRS、データの版と日付を書く。同じ名前の JSON に、それらと区切りの値とクラスごとの数を残す。単位やデータの版に日本語を書くと、スクリプトは描く前に日本語のフォントを選び、地図の全ての文字をそのフォントが描けるかを確かめ、描けなければ地図を書かずに止まる (`scripts/cjk_font.py`。フォントが無い環境では `pip install matplotlib-fontja` で IPAex ゴシックが入る)。matplotlib はフォントが無くても止まらず、文字の抜けた地図を保存するため。使ったフォントは JSON の `font` に残る。
   単位の境は濃い灰色の線で描く。白い線は淡い色の上で消え、同じクラスの隣どうしが 1 つの面に見えるため。地図には単位の名前を書く (`--label` に名前の列、例 `--label name`)。`--label` が無ければ、単位が 50 以下のときは ID を書く。多すぎて読めないなら `--no-labels`。面積 0 の内側の輪 (面を小さな面から作ったときの継ぎ目) は、縁取りすると筋に見えるので描かず、外した数を出す。凡例の区切りの値は、1,000 以上なら桁区切りの整数で書く。
7. 書き出す (下の節)。面積や人口の違いによる見かけの差を、地図だけで現象の差と読まない。

```sh
uvx --with numpy --with duckdb --with shapely --with matplotlib python scripts/classify_map.py \
    tmp/units.parquet id rate --kind rate --unit "per 1,000" --method quantile --classes 5 \
    --compare equal jenks --crs EPSG:6677 --source "census 2020 (2026-10-16)" --label name --png tmp/rate.png
```

テストは `uvx --with numpy --with duckdb --with shapely --with matplotlib --with pillow --with pytest pytest scripts/test_classify_map.py`。等間隔、分位、固定の線の区切りと割り当て、Fisher-Jenks が明らかな群を分け、全ての 3 分割の中で群の中の 2 乗和が最小であること、範囲の外の固定の線で止まること、歪んだ値で区切り方が食い違うこと、色と種類の組み合わせと虹色の拒否、件数と面積の相関の警告、NoData を数えること、地図と JSON の記録、区切り方の比べ、クラスの値に数の区切りを当てると止まること、単位の名前を書いて JSON に残すこと、ラベルの文字もフォントで確かめること、境の色が全てのクラスの色から見分けられること、面積 0 の輪を外して本物の穴を残すこと、ラベルの点が曲がった単位の中に入ること、凡例の値を e 表記にしないことを確かめている。割り当ての境界を誤る、虹色の検査を外す、NoData を 0 にする、Fisher-Jenks の探索を省く、のそれぞれで落ちる。mapclassify との照合は `uvx --with numpy --with duckdb --with shapely --with matplotlib --with mapclassify --with pytest pytest scripts/test_classify_map_crosscheck.py`。

## まだできないこと

- 面だけ。点の大きさの地図 (比例記号)、ラスタの地図、カルトグラム。
- 2 つの変数を 1 枚に重ねる地図。
- 色覚の多様性への配慮の確かめ (色の型は順序と中央から分かれる色に限っているが、見え方は確かめていない)。
- 縮尺、方位、背景の地図。

## 書き出すもの

- 値の種類と単位。件数を塗るなら、その理由と、面積との相関
- 区切り方と理由、区切りの値、クラスごとの単位の数
- 他の区切り方でクラスが入れ替わる単位の割合
- 複数の地図を並べたなら、区切りが共通か個別か
- 色の型と名前、NoData の数と描き方
- CRS、データの版と日付 (地図の JSON に残る)
