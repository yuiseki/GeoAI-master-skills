# 記録: 範囲の端で止まった連鎖を先まで追い、指定されていない候補を空中写真で確かめる

流すたびに 1 行足す。行を消さない。失敗した実行、捨てた実行も残す。計画と違うことをしたら deviation に書く (何を見た後に、何を、なぜ)。計画どおりなら `-`。

| run_id | block_id | claim_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|---|
| R001 | B1 | C1 | confirmatory | pad-0.04 | DEM5A z15 (地理院、2026-11-07 に足りないタイルを取得)、maff-tameike ee87755、WorldPop R2025A 2020 100 m、気象庁の雨は tameike-cascade-breach と同じ | failed | - | - | 福山のタイルの取得で地理院の接続が切れた (Connection reset by peer)。香川は流れた |
| R002 | B1 | C1 | confirmatory | pad-0.04 | 同上 | failed | - | - | 淡路のタイルの取得で同じ切断。取得に再試行 (5 回、待ちを倍に) を足した (tameike-cascade-pairs の run_boxes.py)。結果の計算は変えていない |
| R003 | B0, B1 | C0, C1 | confirmatory | pad-0.04 | 同上 | done | outputs/summary.csv, outputs/b0.csv, outputs/b1.csv | - | C0: 「範囲の外へ出た」以外で止まった初めの池で、あふれる池の並びが元と同じ割合は 1.0、0.9878、0.9932 (支持)。C1: 2 段以上で人口のある連鎖は 30 → 29、33 → 33、149 → 152。香川で 1 つ減ったのは、元の計算で範囲の端にかかっていた休場池の連鎖が 2 池から 1 池になったため (元の範囲の端が水面か流れを切っていた)。香川は「元以上」を満たさない。計算の範囲の端で終わる連鎖は 6 (0.207)、0、3 (0.02) で、香川は「まだ下限」。福山の nodes_without_cells 220 は、広げた範囲の南 (元の範囲の外) の 1 点に台帳の池が多数重なっているため (消滅、廃止の池)。初めの池には関わらない |
| R004 | B2 | C2 | confirmatory | pad-0.04 | 上と、香川の全 17 市町の PDF、広島と兵庫の一覧の全体 | done | outputs/b2_match.csv, outputs/b2.csv, outputs/candidates.csv | - | 照合 0.9951、0.9944、0.992。一覧の無い県の池は無かった。指定されていない連鎖の初めの池は 23、10、73 (多めに数えても 18、9、64)。前の候補から香川の休場池が外れ、淡路に 3 つ入った |
| R005 | B3 | C3 | exploratory | visual | 地理院 seamlessphoto と std、z16 と z17 (2026-11-07 取得) | done | outputs/fig_visual_kagawa.jpg, outputs/fig_visual_fukuyama.jpg, outputs/fig_visual_awaji.jpg, outputs/visual_verdicts.csv | 計画の変更 1 (池の近くの図と「判断できない」) | 判定は Claude が図を見て手で書いた。9 つの全てで、流れの線の 100 m の帯に 10 棟以上の建物。池が全て写っていたのは東池だけ。林の中の池は写真に水面が写らない。(非)空の裏池の 0 は裸地、西池の 2 は造成地 |
