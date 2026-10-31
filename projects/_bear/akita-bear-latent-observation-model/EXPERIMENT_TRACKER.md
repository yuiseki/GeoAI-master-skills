# 記録: 熊の潜在の空間利用と観測の過程の識別

流すたびに 1 行足す。行を消さない。失敗した実行も残す。計画と違うことをしたら deviation に書く。

| run_id | block_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|
| R001 | inputs | sanity | align_inputs.py: 100 m セルを 5 km メッシュへ、yo4 の記録、クマダス 4〜9 月の件数、共変量、H の主成分 | yo4 rev 7f635cb、reports.parquet、生の共変量 (sha256 は JSON) | done | outputs/inputs_summary.json | 共変量の欠けの確認を core mesh だけにした (非 core の 1 メッシュに欠け。主の分析に入らない) | 交差 550、yo4 の枠 549、core 480 (計画の見込みどおり)。core の記録の割合 E6 0.758、E7 0.944。E6=1 かつ E7=0 は 0。core の通報 1,641 / 1,189 / 3,962 / 3,275 件 (県 1,671 / 1,205 / 4,052 / 3,366)。分散 / 平均 7.4〜33.7 で過分散。H の第 1 主成分は分散の 0.736、5 列とも正の負荷。H と tree の相関 −0.843 (熊側の事前の共変量と人側の軸がほぼ同じ次元) |
