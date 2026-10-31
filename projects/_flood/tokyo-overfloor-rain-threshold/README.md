# tokyo-overfloor-rain-threshold

東京都の浸水実績の記録で、1 時間の雨量が強いほど床上浸水の割合が高いか、その跳ね上がりの境 (70 mm/h) が前半と後半の期間をそろえても残るかを調べた。都の雨量計が強い雨を記録したとき、最寄りの気象庁の観測所がそれを捉えるかも確かめた。

- [報告](report.md)
- [計画](EXPERIMENT_PLAN.md) と [実行の記録](EXPERIMENT_TRACKER.md)

入力は、`projects/_flood/tokyo23-flood-record-vs-a31a/scripts/01_fetch.py` が版を固定して取った浸水実績 (tokyo-flood-record-jp@354b0d9) と気象庁の雨量 (jma-rain-tokyo@4391f76)。中間のデータは `artifacts/_flood/tokyo-overfloor-rain-threshold/` に、報告の数字は `outputs/` に置く。

再実行は、プロジェクトのディレクトリで次の順に流す。

```sh
uvx --from 'duckdb>=1.5.5' --with numpy --with pandas --with pyarrow python scripts/01_units.py
uvx --from 'duckdb>=1.5.5' --with numpy --with pandas --with pyarrow python scripts/02_blocks.py
uvx --from 'duckdb>=1.5.5' --with numpy --with pandas --with pyarrow python scripts/03_within_period.py
uvx --with matplotlib python scripts/04_fig.py
```

テストは `uvx --with pytest --with numpy --with pandas pytest scripts/test_overfloor.py`。
