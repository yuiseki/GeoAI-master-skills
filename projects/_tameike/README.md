# _tameike: ため池の防災・水文・渇水監視プロジェクト

ため池数日本一の兵庫県（24,019件）、防災重点ため池数日本一の広島県（20,383件、重点指定約6,750箇所）、およびため池密度日本一の香川県（12,187件、6.39箇所/km²）を対象に、SAR画像解析、水文流向解析、交通網分断リスクなどを多角的に調査するプロジェクト群の置き場所。大きな生成物は `artifacts/_tameike/<名前>/` に置く。

## プロジェクト一覧

| プロジェクト | 状態 | 問い | 使っているデータ・手法 |
|---|---|---|---|
| [tameike-sar-water-area](tameike-sar-water-area/) | 報告済み (2026-11-06) | Sentinel-1 RTC で測る池の中の水面の割合は、近い日の Sentinel-2 の割合と、どの大きさの池まで合い、池ごとの増減を追えるか | `planetary-computer-sentinel-1` (RTC)、Sentinel-2 L2A、`gsi-dem-tiles` (DEM5A の水面の穴)、農水省ため池台帳 |
| [sar-drought-drawdown-monitoring](sar-drought-drawdown-monitoring/) | 検算で取り下げ (2026-11-06) | 12日周期の Sentinel-1 RTC 時系列から、盛夏渇水期のため池水面縮小をどの規模で検知でき、空間的に同期するか | `planetary-computer-sentinel-1` (RTC 10m)、農水省ため池台帳 |
| [tameike-cascade-pairs](tameike-cascade-pairs/) | 報告済み (2026-11-06) | 3 つの範囲のため池で、5 m DEM の上で上流の池の貯水量を足して並べると、台帳の貯水量だけの順で上位に入らない池が上位に入るか | `gsi-dem-tiles` (DEM5A z15、dem z14)、農水省ため池台帳、`terrain-hydrology` |
| [cascade-dam-break-routing](cascade-dam-break-routing/) | 検算で取り下げ (2026-11-06) | 報告された連鎖ため池群は、5 m DEM の上で水の流れでつながっているか | `gsi-dem-tiles` (DEM5A z15)、農水省ため池台帳、`terrain-hydrology` |

## 検算 (2026-11-06)

2 つのプロジェクトの前の版の数字は、データを処理した結果ではなく、スクリプトや JSON に手で書かれた値だった。

- `sar-drought-drawdown-monitoring`: 同じスクリプトを流し直すと、どの池の変化も、恒常水面の対照の観測日ごとの変動を超えなかった。急減水池 (松永溜池、満濃池など) を選ぶ根拠は無い。
- `cascade-dam-break-routing`: 5 m DEM で流れを追うと、松永溜池から二六池への連鎖も、満濃池から前谷下池への連鎖もつながっていなかった。

対象の池の選び方から、やり直す必要がある。やり直した結果:

- `tameike-cascade-pairs`: SAR の結果に頼らず、範囲の全ての池を同じ手順で数えた。3 つの範囲の全てで、上流の池の貯水量を足したときだけ上位 10% に入る池があった。
- `tameike-sar-water-area`: Sentinel-2 を比べる相手にし、池の輪郭の中だけを数えた。0.5〜5 ha の池では、S1 の水面の割合の増減が S2 と弱く同じ向きに動いた (相関 0.16〜0.24)。0.5 ha 未満では追えなかった。S1 だけで個々の池の減水を見張ることはまだできない。
