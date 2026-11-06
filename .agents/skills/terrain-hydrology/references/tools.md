# 道具

2026-11-06 に、3 つの候補のライセンス、版、入れ方、動かし方を確かめた。

| | ライセンス | 版 | 入れ方 | このスキルでの扱い |
|---|---|---|---|---|
| [pyflwdir](https://github.com/Deltares/pyflwdir) (Deltares) | MIT | 0.5.12 (2026-07-01) | PyPI。pure Python と numba。Python 3.11 以上 | `hydro.py` の計算 |
| [whitebox_next_gen](https://github.com/jblindsay/whitebox_next_gen) の Python 版 `whitebox_workflows` | MIT または Apache-2.0 (リポジトリに両方の LICENSE。GitHub の表示は NOASSERTION) | 2.0.6 | PyPI。Rust の拡張 | 照合の相手 |
| [WhiteboxTools](https://github.com/jblindsay/whitebox-tools) と PyPI の `whitebox` | MIT | 2.4.0 (2024-05)、Python パッケージ 2.3.6 | 初回の実行で本体を取得 | 使わない |

## pyflwdir

`hydro.py` が使う関数。

- `pyflwdir.dem.fill_depressions(elevtn, outlets="edge", idxs_pit=None, nodata=-9999.0, max_depth=-1.0)`: 窪地を埋めた DEM と D8 を返す (Wang and Liu 2006)。D8 は最も低い隣へ向き、最急降下ではない。`idxs_pit` を渡すと端が流出口でなくなる ([pitfalls](pitfalls.md))。
- `pyflwdir.from_array(d8, ftype="d8", transform=..., latlon=False)`: 向きのラスタから流れの網を作る。
- `FlwdirRaster.upstream_area(unit="km2")`: 集水面積。`latlon=False` では、画素の幅 × 高さをセルの面積とする。
- `FlwdirRaster.basins(idxs=..., ids=...)`: 流出点ごとの流域。複数の点を一度に渡すと入れ子が分割される。
- `FlwdirRaster.hand(drain, elevtn)`: HAND (Nobre ら 2016)。

選んだ理由: pure Python で依存が軽く、配列のまま扱え、テストに組み込みやすい。向きを自分で直せば (最急降下)、whitebox と同じ答えになった ([validation](validation.md))。

## whitebox_workflows (whitebox_next_gen)

whitebox_next_gen は、WhiteboxTools を作り直した Rust のモノレポで、Python 版が `whitebox_workflows`。水文に関わる関数は、名前で拾って 50 ほどあった (窪地の処理 6 種、D8、D∞、FD8、Rho8、MD∞ の流向と集水、流域、副流域、河道網、河道の次数、HAND に当たる `elevation_above_stream`、湿潤指数など)。有償の拡張はリポジトリの外にあり、このスキルの関数はライセンスキー無しで動いた。

呼び方 (2.0.6 で確かめた):

```python
import whitebox_workflows as wbw
env = wbw.WbEnvironment()
env.verbose = False
hy = env.hydrology
hy.fill_depressions(dem="/abs/dem.tif", output="/abs/filled.tif")
hy.d8_pointer(dem="/abs/filled.tif", output="/abs/pointer.tif")
hy.d8_flow_accum(input="/abs/filled.tif", out_type="cells", output="/abs/acc.tif")   # 向きのラスタでなく DEM から
hy.watershed(d8_pntr="/abs/pointer.tif", pour_pts="/abs/points.gpkg", output="/abs/ws.tif")  # 流出点は CRS つきの GeoPackage
```

向きの符号は既定で 1 北東、2 東、4 南東、8 南、16 南西、32 西、64 北西、128 北 (pyflwdir と違う)。呼び方と罠は [pitfalls](pitfalls.md)。

照合の相手にした理由: 実装が独立していて (Rust、別の作者)、同じ処理を別の道筋で計算できる。計算の本体にしなかった理由: まだ使い込んでおらず、値が黙って切り詰められる罠も見つかったため。もう少し使い込んでから、上流への報告を考える。

## WhiteboxTools と PyPI の whitebox

PyPI の `whitebox` 2.3.6 は、`download_wbt.py` で WhiteboxTools の本体を zip で取る。取得先は whiteboxgeo.com の固定名の zip か、第三者のリポジトリ (giswqs/whitebox-bin) の `raw/master` で、版もチェックサムも無い。同じ環境が作り直せないので使わない。WhiteboxTools 本体の最後のリリースは 2024-05。whitebox_next_gen の README は、自身を Whitebox の現在の主な版 (current major iteration) と書いている。
