# nyc-corridor-reliability

Google の Geospatial Analytics Playground の例「Compare morning and evening rush-hour delays across Boston corridors」を、オープンデータ (NYC DOT Traffic Speeds) で行う。ボストンには同じ粒度のオープンデータが無いため、ニューヨークで行った (report.md)。スキルは `.agents/skills/travel-time-reliability`。

- 報告: [report.md](report.md)
- 小さな表と図: `outputs/`。日ごとの生のデータと Parquet: `artifacts/_playground/nyc-corridor-reliability/`

## 再実行

```sh
CAP="systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% --"
PY="uvx -q --python 3.12 --with pandas --with numpy --with pyarrow --with matplotlib"
cd projects/_playground/nyc-corridor-reliability
$CAP $PY python scripts/run.py fetch prepare quality metrics corridors maps
```

- fetch は NYC Open Data の API (Socrata) から日ごとに全ての行を取る。この環境では 1 日に 4 分ほどかかり、4 日ずつ並べて取った。キーは要らない。
- 配信元は過去の行を書き換えないとは限らない。2026-11-12 の取得では 1,053,140 行。数が違えば取得日を書く。
