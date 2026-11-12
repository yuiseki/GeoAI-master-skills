# nyc-arterial-reliability

NYC DOT の旅行時間 (Open Data「DOT Traffic Speeds」i4gi-tjb9) の 2026 年 9 月の平日で、朝 (06〜10 時) と夕 (16〜20 時) のラッシュに、どの路線の遅れが大きく、どの区間の所要時間が読めないか、朝と夕の差の不確かさ (日の引き直しの 95% 区間) を出す。報告は [report.md](report.md)。

## 構成

- `scripts/` 自分で書いたコード (番号順に流す)。`report_template.md` は報告の雛形で、`08_build_report.py` が表を CSV から写して `report.md` を作る。
- `outputs/` 報告が引く表、JSON、ログ。`figures/` 図 (PNG)。
- 大きな生成物 (取り出した生データ、15 分の区切りの Parquet) は `/work/artifacts/nyc-arterial-reliability/` (来歴は同ディレクトリの `PROVENANCE.json`)。

## 再実行 (作業場所 /work/projects/nyc-arterial-reliability で。要ネットワーク)

```sh
ulimit -v 12000000   # この環境に systemd-run が無いので、メモリの上限は ulimit で掛けた
A=/work/artifacts/nyc-arterial-reliability/raw
uvx --with pandas --with pyarrow python scripts/01_download.py $A          # 約 15 分。日ごとに保存し、再開できる
uvx --with pandas --with pyarrow python scripts/03_data_checks.py
uvx --with pandas --with pyarrow python scripts/04_prepare_bins.py
uvx --with pandas --with pyarrow --with numpy python scripts/05_analysis.py
uvx --with pandas --with pyarrow --with numpy python scripts/06_robustness.py   # 数分
uvx --with pandas --with pyarrow --with numpy --with matplotlib python scripts/07_tables_figures.py
uvx --with pandas python scripts/08_build_report.py
python3 /work/.agents/skills/analysis-reporting/scripts/check_project.py projects/nyc-arterial-reliability  # /work から
```

(`02_explore.py` は最初の探索で、報告の数字には使っていない。)

## 版 (2026-11-12 に測定、[versions.txt](outputs/versions.txt))

Python 3.12.15、pandas 3.1.1、pyarrow 26.0.1、numpy 2.5.4、matplotlib 3.11.2、uv 0.8.24。GeoAI-master-skills の版 ea461bd (`travel-time-reliability/scripts/ttr_metrics.py` の関数を読み込んで使う)。乱数の種は 20261112。データは 2026-11-12 に取得 (9 月分 1,056,287 行)。ライブのデータなので、後で取り直すと値が違うことがある。
