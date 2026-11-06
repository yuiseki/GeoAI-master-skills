# 記録: ため池の上下流の組と、上流の貯水量を足した順位

流すたびに 1 行足す。行を消さない。失敗した実行、捨てた実行も残す。計画と違うことをしたら deviation に書く (何を見た後に、何を、なぜ)。計画どおりなら `-`。

status: `planned`、`running`、`done`、`failed` (止まった、数字が出ない)、`skipped` (理由を notes に)、`abandoned` (途中でやめた、理由を notes に)。

notes には、判断の規則を当てた結果 (支持、退ける、判断できない) を書く。

| run_id | block_id | claim_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|---|
| R001 | B0, B1, B2 | C0, C1, C2 | confirmatory | awaji | DEM5A z15 と dem z14 (2026-11-06 取得)、maff-tameike ee87755 | done | outputs/awaji_summary.json | - | 既知の 2 組のうち、上那木池から下那木新池が「再現しない」と出た。検査が直下の池だけを見ていたため (間に台帳の小さな池が 2 つある)。この時点で awaji の決め手の数も表示された |
| R002 | B0, B1, B2 | C0, C1, C2 | confirmatory | kagawa, fukuyama, awaji | 同上 | done | outputs/summary.csv | R001 を見た後に、B0 の既知の組の検査を「直下」から「下流のどこか」に直した (計画の「再現すること」の読み方を、前のプロジェクトの検算と同じにした)。決め手の計算は変えていない | C0: 穴に対応づいた割合 36.6% (香川)、56.8% (福山)、46.9% (淡路)。既知の 2 組は再現。C1: 3 つの範囲の全てで、V_cum だけで上位 10% に入る池がある (32、28、128)。支持。5%、20%、60 m でも 0 にならない。C2: Jaccard 0.546、0.679、0.519 (記述) |
| R003 | B1 | C1 | confirmatory | visual-check | 同上 | done | outputs/fig_check_nodes.csv, outputs/fig_check_verdicts.csv, outputs/fig_check_kagawa.png, outputs/fig_check_fukuyama.png, outputs/fig_check_awaji.png | 目視する 10 件の選び方 (範囲ごとに V_cum の大きい順に 4、3、3) は、上位の池の一覧を見た後に決めた | 7 件は谷筋の連鎖。1 件 (吉田池) は平地の田の中の流れで疑わしい。2 件 (淡路の淡-714、常盤池) は川の本流に沿って数 km 上流の池まで足していて、連鎖より流域の合計に近い。計画は距離の上限を決めていなかった |
| R004 | B1 | C1 | exploratory | within-distance | 同上 | done | outputs/summary.csv | R003 の目視の後に足した。上流の池を、流れの距離が 500、1,000、2,000 m 以内のものだけ足す。決め手の計算 (距離の上限なし) は変えていない | 500 m 以内に限っても、V_cum だけで上位 10% に入る池は 27 (香川)、24 (福山)、119 (淡路)。上下の池の間の流れの距離の中央値は 235、209、130 m。探索なので主張の証拠には数えない |
