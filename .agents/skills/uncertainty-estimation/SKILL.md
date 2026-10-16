---
name: uncertainty-estimation
description: モデルの不確かさを信じてよいかを確かめる。分類なら確率の較正 (Brier、ECE、信頼性の表)、回帰なら予測区間 (共形予測) とその被覆率。全体だけでなく、地域や年などのグループごとに見る。予測を確率や区間として使う前に使う。
---

# uncertainty-estimation

確率や区間は、全体で約束を守っていても、特定のグループで守っていないことがある。全体の数字に加えて、本番で使う単位のグループごとに確かめる。

| reference | 対象 |
|---|---|
| [calibration](references/calibration.md) | 分類の確率。モデルが 0.3 と言った行の 3 割が陽性か |
| [intervals](references/intervals.md) | 回帰の予測区間。区間を作るのに使っていない行の 9 割を、90% の区間が覆うか |
| [cv-plus-and-cqr](references/cv-plus-and-cqr.md) | 自分でモデルを当てて作る、保証の付く区間。fold のモデルを使う CV+ と、分位点のモデルを広げる CQR (雑音の大きい行で区間が広がる) |
| [input-uncertainty](references/input-uncertainty.md) | 入力と前処理 (位置の誤差、按分の推定、分類の誤り) の不確かさが後の段階へ伝わること。固定すると区間が狭すぎる |

## 手順

1. 予測をどう使うかを書く。確率をそのまま使うのか、しきい値で 0/1 にするのか、区間で幅を示すのか。
2. 交差検証の外側の予測を (repeat、model、id、target、prediction) の列の Parquet に書き出す (書き方は [references/predictions-file.md](references/predictions-file.md))。学習に使った行の予測では、不確かさを小さく見積もる。
3. `scripts/uncertainty.py` で、全体と、グループ (`--by`、地域、年、所得階層など) ごとに確かめる。
4. ずれていたら、その原因を探す。時代による基準の割合のずれか、特定のグループの雑音の大きさか、モデルの癖か。
5. 直すなら、学習側の中で較正する、グループごとに区間を作る、などを行い、同じ分割表で確かめ直す。
6. 書き出す。

```sh
uvx --with duckdb --with scikit-learn python scripts/uncertainty.py calibration tmp/predictions.parquet \
  --table tmp/table.parquet --id ID --by year
uvx --with duckdb --with scikit-learn python scripts/uncertainty.py intervals tmp/predictions.parquet \
  --table tmp/table.parquet --id ID --by region --calibrate-by region --alpha 0.1
uvx --with duckdb --with scikit-learn python scripts/uncertainty.py recalibrate tmp/predictions.parquet \
  --table tmp/table.parquet --id ID --method isotonic --time year --calibrate-before 2023
```

予測のファイルではなく、表と特徴量からモデルを当てて区間を作るなら `scripts/conformal.py` (CV+ と CQR)。`--test-by region` で地域ごとに伏せる。

```sh
uvx --with duckdb --with numpy --with scikit-learn --with pyarrow python scripts/conformal.py cqr tmp/table.parquet \
  --target Y --features A,B,C --test-by region --by region
```

`--time 列 --calibrate-before T` を付けると、較正し直しも区間も、T より前の行だけで作って T 以降の行に当てる。時代のずれがある問題では、こちらの数字を報告する (references/calibration.md)。

区間は、作るのに使った残差の行と、被覆率を測る行を分ける。`--calibrate-by 列` は、その列の値ごとに、他の値の行の残差で区間を作る (無ければ無作為な 5 つの群)。地域ごとに使うなら、地域で伏せる。予測のファイルに `role` の列 (`calibration`、`test`) があれば、1 つのモデルの較正用の行で区間を作り、試験用の行で測る (共形予測の保証が付くのはこれだけ、references/intervals.md)。各行の区間を他の全ての行から作り、同じ行で被覆率を測ることはしない。同順位が無ければ、その被覆率はモデルによらず ceil((1 - alpha) n)/n に決まる。

テストは `uvx --with duckdb --with scikit-learn --with pytest pytest scripts/test_uncertainty.py`。ECE を手で計算できる例と一致すること、Brier が scikit-learn と一致すること、同じ行で作って同じ行で測る被覆率がモデルによらず k/n に決まること、1 つのモデルの較正用の行で作った区間が新しい行を約束どおり (0.90 から 0.91) 覆うこと、群ごとに伏せた分位点が同じ値の多いデータで総当たりと一致すること、雑音の大きい群を伏せると被覆率が下がること (同じ行で測る方法では 90% のまま) を確かめている。伏せた群の残差も使う、較正用でない行の残差も使う、分位点の順位を 1 つずらす、ECE の重みを落とす、のそれぞれで落ちることを確かめてある。較正し直しが交差フィットであること (手で組んだ交差フィットと一致)、過去で較正すると基準の割合の上昇を直せないこと、雑音が大きくなると時間順の区間が覆えなくなること、空の入力の ECE が 0 でなく NaN であることも確かめ、全行で較正する、過去でなく全期間で較正する、区間に後の期間の残差を使う、のそれぞれで落ちることを確かめてある。

CV+ と CQR のテストは `uvx --with duckdb --with numpy --with scikit-learn --with pytest pytest scripts/test_conformal.py`、MAPIE との照合は `scripts/test_conformal_crosscheck.py` (references/cv-plus-and-cqr.md)。どちらも、学習の行と新しい行が交換可能でなければ保証は無い。地域ごとに伏せた国の平均寿命では、どの型でも被覆が 0.74〜0.82 に落ちた。

## 書き出すもの

- 予測の使い方と、確かめた分割表
- 分類: Brier、ECE、信頼性の表を、全体とグループごとに
- 回帰: 約束した割合、区間を作った行と測った行の分け方 (role、時間、伏せた群)、全体とグループごとの被覆率、区間の幅
- ずれの原因の見立てと、直したならその方法と結果
