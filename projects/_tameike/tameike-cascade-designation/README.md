# tameike-cascade-designation: 連鎖の上流にある池は、防災重点農業用ため池に指定されているか

`tameike-cascade-breach` で見つけた連鎖 (2 つ以上の池が次々にあふれ、流れの近くに人が住む) の初めの池を、香川県、広島県、兵庫県が公表している防災重点農業用ため池の一覧と突き合わせて、指定されていない池を数え、点検の候補の一覧にする。

- 計画: [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md) (流す前にコミット、変更は末尾)
- 記録: [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)
- 報告: [report.md](report.md)
- 候補の一覧: [outputs/candidates.csv](outputs/candidates.csv)

## 再実行

```sh
cd projects/_tameike/tameike-cascade-designation
systemd-run --user --scope -q -p MemoryMax=2G -p MemorySwapMax=0 -- uvx --python 3.12 --with pytest pytest -q scripts/test_match.py
python3 scripts/fetch_lists.py     # 県の一覧の原本を artifacts/ に保存 (コミットしない)。県は一覧を更新する
systemd-run --user --scope -q -p MemoryMax=2G -p MemorySwapMax=0 -- uvx --python 3.12 --with openpyxl python scripts/parse_lists.py
systemd-run --user --scope -q -p MemoryMax=4G -p MemorySwapMax=0 -p CPUQuota=200% -- \
  uvx --python 3.12 --with duckdb==1.5.5 python scripts/run_match.py      # 約 1 分
python3 scripts/explore_exposure.py
python3 ../../../.agents/skills/analysis-reporting/scripts/check_project.py .
```

`parse_lists.py` は pdftotext (poppler) を使う。`run_match.py` は `tameike-cascade-breach/outputs/<box>_chains.csv` の台帳の行の列を読む。

県の一覧の原本と、それを読み取った `designated.csv` はコミットしていない。コミットしたのは、件数と、台帳 (農林水産省、PDL1.0) の名称と所在地で書いた候補の一覧である。

出典: 香川県「防災重点農業用ため池一覧表」、広島県「防災重点農業用ため池に係る防災工事等推進計画 別表 2」、兵庫県「特定農業用ため池、特定ため池及び防災重点農業用ため池指定一覧」を加工して作成。「農業用ため池一覧(令和8年3月末時点)」(農林水産省) を加工して作成。
