# 記録: B_env の bear-side、human-side、interface への分解

流すたびに 1 行足す。行を消さない。失敗した実行も残す。計画と違うことをしたら deviation に書く。

| run_id | block_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|
| R001 | labels | sanity | interface_labels.py: 4〜9 月のセルのラベルと通報の行 (2023〜2026) | akita-kumadas c7047ab、reports_by_year b7f5d77e | done | outputs/labels_check.json | - | 熊の年度の数を reports_by_year と照合。4〜9 月の陽性セル 1,586 / 1,132 / 3,657 / 3,036 が R036 と一致。通報の行 22,442 (県外 8) から季節のセルの数を作り直して一致 |
| R002 | B1 | development | interface_models.py --train 2023 --test 2024 --boot 500 --check-full | 入力 sha は JSON | done | outputs/b1_dev_2023_to_2024.json | - | 28 特徴量の学習し直しが保存済み B1 B_env と完全一致 (最大差 0.0)。capture@5%: M_B 0.358、M_H 0.505、M_I 0.200、M_BH 0.548、M_BHI 0.553、M_FULL 0.534。M_B − M_H −0.147 (−0.185〜−0.113)。良い方の単独モデルは M_H に固定 (B2、B3 の C の比較に使う)。M_BH − M_H +0.043 (+0.024〜+0.058)、M_BHI − M_BH +0.005 (−0.011〜+0.017)、M_FULL − M_BHI −0.019 (−0.033〜+0.001)。Shapley: B 0.144、H 0.304、I 0.055 |
| R003 | B2 | confirmation | interface_models.py --train 2023 2024 --test 2025 --boot 1000 | 入力 sha は JSON | done | outputs/b2_confirm_2023-2024_to_2025.json | - | capture@5%: M_B 0.403、M_H 0.530、M_I 0.199、M_BH 0.547、M_BHI 0.547、M_FULL 0.552 (保存済みと同じ)。M_B − M_H −0.127 (−0.154〜−0.104)。M_BH − M_H +0.016 (+0.010〜+0.027)。M_BHI − M_BH +0.001 (−0.005〜+0.005)。M_FULL − M_BHI +0.005 (−0.003〜+0.007)。M_H の割合 0.957。Shapley: B 0.157、H 0.290、I 0.050 |
| R004 | B3 | confirmation | interface_models.py --train 2023 2024 2025 --test 2026 --boot 1000 | 入力 sha は JSON | done | outputs/b3_confirm_2023-2025_to_2026.json | - | capture@5%: M_B 0.370、M_H 0.529、M_I 0.187、M_BH 0.538、M_BHI 0.532、M_FULL 0.539。M_B − M_H −0.159 (−0.180〜−0.134)。M_BH − M_H +0.009 (−0.002〜+0.024)。M_BHI − M_BH −0.006 (−0.011〜+0.005)。M_FULL − M_BHI +0.007 (−0.007〜+0.014)。M_H の割合 0.978。判定 (B2 と B3 の両方): Pattern B (M_H ≫ M_B、両方で差 0.10 以上)。C は B3 で下限が 0 を下回り不支持。D、E も不支持 |
