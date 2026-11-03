# _urban: 都市の変化のプロジェクト

建物や道路の変化 (再開発、解体、造成) を衛星から拾えるかを調べたプロジェクトの置き場所。大きな生成物は `artifacts/_urban/<名前>/` にある。

| プロジェクト | 問い | 使っているもの |
|---|---|---|
| [chishirodai-sar-redevelopment](chishirodai-sar-redevelopment/) | 千葉市若葉区千城台東の団地の解体を Sentinel-1 の時系列で日付けできるか。周り約 6 km 四方のズーム 16 のタイルを SAR で順位付けすると、写真で大きく変わったタイルを上位で拾えるか | sentinel-1-rtc (軌道 46)、sentinel-2-l2a、国土地理院 年度別空中写真 (2019、2024 年度)、WorldCover、OSM の工事区域 |
