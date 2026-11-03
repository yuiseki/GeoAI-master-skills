# _flood: 浸水のプロジェクト

浸水の記録と、国や都の浸水の想定を調べたプロジェクトの置き場所。大きな生成物は `artifacts/_flood/<名前>/` にある。

| プロジェクト | 問い | 使っているもの |
|---|---|---|
| [tokyo23-flood-record-vs-a31a](tokyo23-flood-record-vs-a31a/) | 23 区の 100 m セルで、浸水の記録から学習した予測モデルの上位の区域は、後の期間の浸水を A31a (洪水浸水想定区域) より多く捉えるか | |
| [underpass-ponding-exposure](underpass-ponding-exposure/) | 全国のアンダーパスで、公開の標高と道路で測る溜まりやすさの順位は、設定でどれだけ変わり、浸水や冠水の記録とどの程度合うか | mlit-underpass、OSM の道路、国土地理院の標高タイル、浸水実績、箇所表 |
| [tokyo-overfloor-rain-threshold](tokyo-overfloor-rain-threshold/) | 東京都の浸水実績で、都の雨量計の時間雨量が強い記録ほど床上浸水の割合は高いか。気象庁の観測所は強い雨をどれだけ見落とすか | tokyo-flood-record-jp、jma-rain-tokyo |
| [kita-inbanuma-sar-replication](kita-inbanuma-sar-replication/) | 北印旛沼の浸水を Sentinel-1 で解析した note 記事 2 本 (範囲、深さと水面) の主張は、公開データと記述から組み直した手順で再現するか | sentinel-1-grd、sentinel-1-rtc、浸水推定図の輪郭線と深さ、DEM5A、WorldCover |
| [kita-inbanuma-sar-changepoint](kita-inbanuma-sar-changepoint/) | 北印旛沼の周りで、Sentinel-1 の同じ軌道の 3〜10 月の時系列に画素ごとの変化点の検定を当てると、浸水した所で浸水の始まった日と水が引いた日が出るか。隣り合う 2 枚の差より得か | sentinel-1-rtc (軌道 39 と 141)、浸水推定図の輪郭線、DEM5A、WorldCover |
| [tokyo23-underpass-listing](tokyo23-underpass-listing/) | OSM のタグから作った 23 区のアンダーパスのうち、国の一覧に載るのはどれか。一覧は浸水実績の区域に入る箇所に寄っているか | 凍結の OSM、mlit-underpass、冠水想定箇所、tokyo-flood-record-jp |
| [hagibis-tokyo-sar-flood-record](hagibis-tokyo-sar-flood-record/) | 台風第 19 号 (2019) の雨の後の Sentinel-1 で、東京都の浸水実績の区域は背景より暗くなるか。河道は見えるか。暗くなった所は A31a の区域に寄るか | sentinel-1-rtc (軌道 46 と 39)、tokyo-flood-record-jp、A31a 想定最大規模、N03、OSM の多摩川、WorldCover |
