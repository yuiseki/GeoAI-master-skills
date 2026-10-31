# record-vs-occurrence

提供された 100 区画の表 (`data/units.csv`、1 行 = 1 km の 1 区画) の記録の件数から、人口あたりの発生が多い地域を言えるかを確かめた。記録の多さが、調査 (訪問) の多さと人口の多さでどこまで説明できるか、発生の西東の比が検出の仮定でどう変わるかを分けて測った。

- [報告](report.md)
- [計画](EXPERIMENT_PLAN.md) と [実行の記録](EXPERIMENT_TRACKER.md)

再実行は、プロジェクトのディレクトリで次を流す。数字と図の来歴は `outputs/` に、根拠の抜き書きは `outputs/evidence.txt` に書き出す。

```sh
python3 scripts/analysis.py
```

作者は `/tmp/venv-geoai` の Python で流した。スクリプトが読み込むパッケージは、スクリプトの先頭にある。
