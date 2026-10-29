# _bear: クマの出没とブナの豊凶のプロジェクト

クマの出没通報のリスクと、その手がかりとしてのブナの豊凶を調べたプロジェクトをまとめた置き場所。大きな生成物は `artifacts/_bear/<名前>/` にある。プロジェクトどうしは入力を読み合うので (下の「使っているもの」)、1 つだけ別の場所へ動かさない。

## クマの出没

| プロジェクト | 問い | 使っているもの |
|---|---|---|
| [japan-bear-sighting-forecast](japan-bear-sighting-forecast/) | 秋田県の市町村 × 週の通報件数を 1〜8 週先まで予測できるか | |
| [bear-outbreak-weather](bear-outbreak-weather/) | クマの大量出没の年を、前の年の気温で説明できるか | |
| [akita-bear-risk-grid-100m](akita-bear-risk-grid-100m/) | 秋田県の 100 m セルの次の年度の通報を、環境と過去の通報で予測できるか (B_env) | |
| [bear-risk-transfer](bear-risk-transfer/) | 秋田で学習した 100 m のモデルを、岐阜、京都、石川、長岡へそのまま当てはめられるか | akita-bear-risk-grid-100m |
| [bear-risk-sources](bear-risk-sources/) | 当てはめで、建物、道路、川のデータの出どころや学習の地域の数で当たりがどう変わるか | akita-bear-risk-grid-100m、bear-risk-transfer |
| [akita-bear-mast-exposure](akita-bear-mast-exposure/) | 年のブナの豊凶 × ブナ・ナラ類の植生は、B_env の順位を良くするか (しなかった。cross-fit の追加の診断あり) | akita-bear-risk-grid-100m、beech-masting-triggers |

## ブナの豊凶

| プロジェクト | 問い | 使っているもの |
|---|---|---|
| [beech-masting-triggers](beech-masting-triggers/) | 東北 5 県の年の豊凶を、前の年までの気象と衛星で先に言い当てられるか | |
| [beech-masting-spatial-proxy](beech-masting-spatial-proxy/) | 地形と地点の気象で、同じ年の中の地点の豊凶の違いを当てられるか (当てられなかった) | beech-masting-triggers |
| [beech-masting-satellite-proxy](beech-masting-satellite-proxy/) | Landsat 5 の NDVI と NDMI の偏差で、同じ年の中の地点の違いを当てられるか (当てられなかった) | beech-masting-spatial-proxy |

## 総括

[bear-synthesis](bear-synthesis/) に、9 プロジェクトで何が予測でき、何ができなかったかをまとめた。場所は環境だけの地図 B_env で絞れるが、そこに過去の通報、年の豊凶 × 植生、季節内の直前の通報を足しても上がらなかった。予測変数の探索はここで止めている。

スクリプトの使い方は各プロジェクトの README にある。コマンドはリポジトリの直下から流す。
