# 事前学習モデル

大量の人工データや実データで事前に学習したモデルに、こちらのデータを入力として読ませて予測させる。学習し直さずに使えるので、行が少ない表でも試せる。

| モデル | 対象 | このスキルでの扱い |
|---|---|---|
| TabPFN | 表形式の回帰と分類 | `compare_models.py` の `tabpfn_v2` |
| TimesFM | 時系列の予測 | 入れていない。time-series-analysis で扱う |

## ライセンスは版ごとに違う

重みのライセンスは版ごとに違い、新しい版ほど商用に使えないことがある。使う前に、その版の重みのライセンスを読む。パッケージのコードのライセンス (TabPFN も TimesFM も PyPI では Apache-2.0) と、重みのライセンスは別物。2026-10-10 に Hugging Face の各リポジトリのカードと LICENSE を読んだ結果:

| 重み | ライセンス | 商用 |
|---|---|---|
| TabPFN v2 (`Prior-Labs/TabPFN-v2-reg`、`-clf`) | Prior Labs License 1.1 | 可。表示の義務あり (下) |
| TabPFN 2.5、2.6、3、3.5 (`Prior-Labs/tabpfn_2_5` ほか) | 版ごとの TabPFN ライセンス | 不可。研究と内部の評価だけ。出力を社内の商用の判断に使うことも不可 |
| TimesFM 1.0、2.0、2.5 (`google/timesfm-*`) | Apache 2.0 | 可 |
| TimesFM 3.0 (`google/timesfm-3.0-pytorch`) | TimesFM Non-Commercial License 1.0 | 不可。出力を商用の判断や顧客への成果物に使うことも不可 |

TabPFN v2 の Prior Labs License 1.1 は、Apache 2.0 に第 10 項を足したもの。重みやそれを含む製品を配布、公開するときは、ライセンスの写しを添え、「Built with PriorLabs-TabPFN」を関連するサイトや文書に目立つように示す。重みや出力を使って別のモデルを作って公開するなら、その名前を「TabPFN」で始める。公開しない内部の評価と試験には、この表示は要らない。

## パッケージの既定は使えない版

`tabpfn` 9.1.0 は、既定で v3.5 の重みを使う (`settings.py` の `model_version` の既定が `ModelVersion.V3_5`)。v3.5 は商用に使えない。何も指定せずに `TabPFNRegressor()` を作ると、商用に使えない重みを使うことになる。

`compare_models.py` の `tabpfn_v2` は、次の 3 つを固定している。

- 版: `create_default_for_version(ModelVersion.V2, ...)`
- 重みのファイル: `tabpfn-v2-regressor.ckpt`、`tabpfn-v2-classifier-finetuned-zk73skhh.ckpt` (`tabpfn` 9.1.0 の v2 の既定のファイル)
- Hugging Face のコミット: 回帰は `4972a65a1b30806315c6f92499959ffbfc69a673`、分類は `f851f2a3c941544733b712d8c0f96dfae9b28862`。`tabpfn` は既定ではコミットを固定せずに最新を取る。分類のリポジトリは 2026-04-26 にも更新されている

テスト (`test_tabpfn_uses_the_pinned_v2_weights`) で、作ったモデルがこのファイルとコミットを指していることを確かめている。

## 動かし方

```sh
uvx --with tabpfn==9.1.0 --with duckdb --with scikit-learn python scripts/compare_models.py \
  tmp/table.parquet ID TARGET F1 F2 F3 --task regression --models linear tabpfn_v2 \
  --folds-file tmp/folds_region.parquet
```

- `torch` が入るので初回は時間がかかる。
- `device="cpu"` に固定している。GPU には常駐のサービスがあるので使わない。行が数百なら CPU で足りる (209 行の 5 分割で約 3 秒)。
- ログインは要らない。v2 のリポジトリは公開で、2.5 以降は同意の手続きが要る。
- `tabpfn` 9.1.0 のコードに、利用状況を外部に送る処理は見つからなかった (`telemetry`、`posthog` などで検索)。

## 試した結果

国 × 1 年の平均寿命を 1 人あたり GDP (対数)、人口 (対数)、都市人口の割合で予測した (WDI、2022 年、209 か国、種 3 つの平均、2026-10-10):

| モデル | R2 (行を無作為に 5 分割) | R2 (地域ごとに 5 分割) |
|---|---:|---:|
| linear | 0.631 | 0.521 |
| tabpfn_v2 | 0.624 | 0.484 |

行が少ない表でも、線形を超えなかった。事前学習モデルも、基準と線形と同じ分割で並べてから採用する。
