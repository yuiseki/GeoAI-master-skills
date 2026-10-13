---
kind: service
id: valhalla
description: 自前の経路検索 (Valhalla)。2 点以上の経路の距離と所要時間を返す。
url: https://valhalla.yuiseki.net
protocol: valhalla
license: ODbL-1.0 (経路の元の OSM データ)
spatial_coverage: 構築した範囲 (日本で実測。範囲の全体は確かめていない)
temporal_coverage: 元の OSM データの時点は確かめていない
as_of: {measured: 2026-10-13}
operations:
  - name: route
    method: POST
    path: /route
    params: ["body は JSON 文字列 (json.dumps)、Content-Type は application/json", "locations: [{lat, lon}, ...] の 2 点以上", "costing: auto、pedestrian、bicycle など (必須)", "units: kilometers"]
    returns: JSON の root は dict。経路は payload['trip']、距離は payload['trip']['summary']['length'] (units の単位)、所要時間は payload['trip']['summary']['time'] (秒)。routes というキーは無い
  - {name: locate, method: POST, path: /locate, returns: 座標が道路網のどこに当たるか}
  - {name: status, method: GET, path: /status, returns: 状態}
gotchas:
  - "応答の最上位のキーは trip だけだった (実測)。routes は無い。"
  - "東京駅 (35.6812, 139.7671) から上野駅 (35.7141, 139.7774) を pedestrian で引くと、length 4.323 (km)、time 3113.184 (秒) だった (2026-10-13 実測)。"
  - "costing は必須。時間は秒で、距離の単位は units で決まる。"
  - "locations は lat と lon のキー名つきの dict の配列で渡す (上の実測の形)。"
---

# Valhalla

2 点以上の経路の距離と所要時間。分析では、直線距離ではなく道のりを特徴量にする、到達できる範囲の目安に使う。

```sh
curl -sS -X POST -H 'Content-Type: application/json' \
  -d '{"locations":[{"lat":35.6812,"lon":139.7671},{"lat":35.7141,"lon":139.7774}],"costing":"pedestrian","units":"kilometers"}' \
  https://valhalla.yuiseki.net/route
```

## 気をつけること

- 上の東京駅から上野駅の例は、徒歩で 1 回流した結果だけを確かめた。`auto` や `bicycle`、3 点以上の経路は、ここでは流していない。
