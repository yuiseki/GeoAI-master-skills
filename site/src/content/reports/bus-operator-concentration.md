---
title: 全国のバス停記録から、事業者の集中を読む
summary: 高齢者の住む地域で、近くの停留所に記録された事業者名が1種類しかない場所はどれほどあるか。
topic: 公共交通
kicker: 全国・1kmメッシュ
image: /images/bus-operator-share.png
imageAlt: 自治体別の、単一事業者名メッシュの65歳以上人口割合を示す地図
source: https://github.com/yuiseki/GeoAI-master-skills/blob/main/projects/_traffic_bus/japan-bus-operator-concentration-replication/report.md
---

## 問い

2020年の高齢者が住む1kmメッシュの周囲800mに、2022年度版のバス停データに記録された事業者名が1種類しかない地域は、全国でどれほどあるでしょうか。

## 分かったこと

停留所が800m圏にあるメッシュの65歳以上人口は約3,240万人。そのうち約1,489万人、**46.0%**が、記録上は事業者名1種類の停留所圏に住んでいました。停留所がない地域の約291万人は、集中とは分けて数えています。

![自治体別の単一事業者名メッシュの65歳以上人口割合](/images/bus-operator-share.png)

図の出典: 国土交通省「国土数値情報 P11（2022年度）」、総務省統計局「2020年国勢調査メッシュ」、行政界の加工結果。[データの版と利用条件](https://github.com/yuiseki/GeoAI-master-skills/blob/main/projects/_traffic_bus/japan-bus-operator-concentration-replication/README.md)。

割合では地方の自治体が、人数では大都市が目立ちます。自治体が現行の交通供給を確認する際には、割合と人数の両方が必要です。

## 数え方と確かさ

メッシュ $i$ の65歳以上人口を $a_i$、半径 $r$ 内の異なる事業者名の数を $k_i(r)$ とし、対象集合 $E$ について人口加重割合を求めました。

```math
p_r = \frac{\sum_{i \in E} a_i I\{k_i(r)=1\}}{\sum_{i \in E} a_i I\{k_i(r)\geq 1\}}.
```

半径を500mにすると58.5%、1,000mでは40.4%。**46.0%という値は800mという定義に依存します。** 距離はメッシュ中心からの直線距離で、歩行距離ではありません。

## 限界

事業者名が1種類でも、便数や運行頻度、撤退の確率、個人の移動困難は分かりません。人口は2020年、停留所は2022年度で時点が異なります。政策判断には現行の時刻表、共同運行、デマンド交通の確認が必要です。

[分析の原本・データの版・再現手順を見る](https://github.com/yuiseki/GeoAI-master-skills/blob/main/projects/_traffic_bus/japan-bus-operator-concentration-replication/report.md)
