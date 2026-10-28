# beech-masting-triggers

東北 5 県のブナの結実の豊凶 (1989〜2026 年度) を、前の年までの気象と衛星の値で先に言い当てられるか、どの手がかりが引き金かを調べる。計画は [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)、実行の記録は [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)。

## 置き場所

- `scripts/`: コードとテスト。
- `outputs/`: 報告が引く小さな表。`tohoku_beech_index.csv` は東北森林管理局のプレスリリースの表を読み取ったもの (出典: 東北森林管理局ウェブサイト https://www.rinya.maff.go.jp/tohoku/sidou/buna.html を加工して作成。PDL1.0)。
- `artifacts/beech-masting-triggers/`: 取った PDF、気象と衛星の地点の値。

## 再現

リポジトリの直下から。

```sh
# 1. 豊凶指数の表 (PDF を取り、読み取り、2 つのリリースと箇所数で照合する)
uvx --with pdfplumber python projects/beech-masting-triggers/scripts/tohoku_index.py \
  artifacts/beech-masting-triggers/raw projects/beech-masting-triggers/outputs

# 2. Dryad の地点と、作り直した指数の照合
uvx --from 'duckdb>=1.5.5' --with numpy python projects/beech-masting-triggers/scripts/dryad_sites.py \
  projects/beech-masting-triggers/outputs

# テスト
cd projects/beech-masting-triggers/scripts && uvx --with pdfplumber --with numpy --with pytest python -m pytest -q
```
