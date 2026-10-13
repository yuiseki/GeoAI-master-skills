# Overture: transportation

道路、鉄道、水路の線 (segment) と、それらが接する点 (connector)。最短経路や到達圏のネットワークに使う。

## 2 つの種類

版 2026-09-23.1 (2026-10-10 実測)。

| 種類 | 1 行 | 行数 | ファイル |
|---|---|---:|---:|
| `segment` | 1 本の線 (道路、鉄道、水路) と属性 | 352,054,710 | 128 |
| `connector` | 線どうしが接する点 | 421,978,977 | 32 |

全世界は大きいので、目録の item の範囲 (README.md) と `bbox` 列で、使う範囲だけを読む。

## segment の列

`id`、`names`、`subtype` (road、rail、water)、`class` (motorway、primary、residential、footway など)、`subclass`、`connectors`、`road_surface`、`road_flags`、`rail_flags`、`width_rules`、`level_rules`、`access_restrictions`、`speed_limits`、`prohibited_transitions`、`routes`、`destinations`、`sources`、`geometry`、`version`、`bbox`。

- `connectors` は (connector_id、at) の並び。`at` は線の上の位置で、始点が 0、終点が 1。途中で他の線と接する点も入る。ネットワークにするには、線を `at` の位置で切り、connector を節点、切った線を辺にする。
- 速度、通行の制限、路面などは「線のどこからどこまで」(`between`) 付きの並び。1 本の線の中で値が変わる。
- `geometry` の CRS 名は `OGC:CRS84`。

## 例: 台東区の付近

経度 139.76〜139.82、緯度 35.69〜35.73 に bbox が重なる segment を読んだ (2026-10-10、範囲の重なる 4 ファイルから 97 秒)。

| subtype | class | 本数 |
|---|---|---:|
| road | footway | 8,094 |
| road | residential | 5,455 |
| road | service | 2,591 |
| road | tertiary | 2,238 |
| road | unclassified | 2,084 |
| road | steps | 1,051 |
| road | secondary | 807 |
| road | primary | 524 |
| road | trunk | 509 |
| rail | standard_gauge | 192 |
| rail | subway | 63 |
| road | motorway | 65 |

- 合計 24,170 本。歩道 (footway) と階段 (steps) が 4 割近くを占める。車の到達圏を作るなら class で絞る。
- `connectors` の数は、どの線も 2 以上 (両端)。2 つが 9,804 本、3 つが 8,470 本、4 つが 3,128 本で、途中で他の線と接する線が多い。
- bbox で絞ると、範囲の端をまたぐ線も入る。ネットワークの端では、範囲の外への道が切れている (範囲の端の単位で近傍が欠ける端の効果と同じ)。
