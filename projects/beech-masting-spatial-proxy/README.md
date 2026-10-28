# beech-masting-spatial-proxy

東北 98 地点のブナの結実の評価 (地点 × 年、0〜3、1989〜2008 年) を、前年の結実、地形、年ごとの気象と水分、地形 × 気象の交互作用で当て、学習に使っていない年と地点の両方で当たるかを確かめる。当たるなら、観測の無い場所の豊凶を環境のラスタから作る面 (proxy) の根拠になる。県 × 年で調べた [beech-masting-triggers](../beech-masting-triggers/) の続きだが、分析の単位が地点 × 年なので別にした。

計画は [EXPERIMENT_PLAN.md](EXPERIMENT_PLAN.md)、実行の記録は [EXPERIMENT_TRACKER.md](EXPERIMENT_TRACKER.md)。

## 置き場所

- `scripts/`: コードとテスト。
- `outputs/`: 報告が引く小さな表と図。
- `artifacts/beech-masting-spatial-proxy/`: 読んだ DEM のタイル、地点 × 月の気象の値などの大きな中間物 (git に入れない)。

## データ

- 目的変数: `yuiseki/fagus-crenata-masting-jp-2026-06` 版 db40a09 (Dryad、Masaki ほか、CC0)。東北 98 地点だけ。北海道 4 地点は別の地域の検証のために読まない。
- 地形: Mapterhorn の複製 `z.yuiseki.net/static/mapterhorn/2026-01-06/planet.pmtiles` のズーム 12。
- 気温: `yuiseki/agera5-japan-monthly-temperature-1979-2026` 版 348e459。
- 水分: `yuiseki/agera5-japan-monthly-water-1979-2026` 版 b3d1a83 (AgERA5 の月別降水と FAO の月別基準蒸発散量、CC BY-SA 4.0)。この研究のために凍結した。作り方は Hugging Face の `scripts/build.py`。
