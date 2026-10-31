# _flood: 浸水のプロジェクト

浸水の記録と、国や都の浸水の想定を調べたプロジェクトの置き場所。大きな生成物は `artifacts/_flood/<名前>/` にある。

| プロジェクト | 問い | 使っているもの |
|---|---|---|
| [tokyo23-flood-record-vs-a31a](tokyo23-flood-record-vs-a31a/) | 23 区の 100 m セルで、浸水の記録から学習した予測モデルの上位の区域は、後の期間の浸水を A31a (洪水浸水想定区域) より多く捉えるか | |
| [underpass-ponding-exposure](underpass-ponding-exposure/) | 全国のアンダーパスで、公開の標高と道路で測る溜まりやすさの順位は、設定でどれだけ変わり、浸水や冠水の記録とどの程度合うか | mlit-underpass、OSM の道路、国土地理院の標高タイル、浸水実績、箇所表 |
| [tokyo-overfloor-rain-threshold](tokyo-overfloor-rain-threshold/) | 東京都の浸水実績で、都の雨量計の時間雨量が強い記録ほど床上浸水の割合は高いか。気象庁の観測所は強い雨をどれだけ見落とすか | tokyo-flood-record-jp、jma-rain-tokyo |
| [kita-inbanuma-sar-replication](kita-inbanuma-sar-replication/) | 北印旛沼の浸水を Sentinel-1 で検知した note 記事の主張は、公開データと記述から組み直した手順で再現するか (段 A: 記事 1) | sentinel-1-rtc、浸水推定図の輪郭線、DEM5A、WorldCover |
