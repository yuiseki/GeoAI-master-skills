# 記録: 年のブナの豊凶 × 場所のブナ・ナラ類の exposure と、秋田県のクマ出没の 100 m セルの順位

流すたびに 1 行足す。行を消さない。失敗した実行、捨てた実行も残す。計画と違うことをしたら deviation に書く (何を見た後に、何を、なぜ)。計画どおりなら `-`。データの取得と QA の問題、仕様の不明は、補わずにここに書く。

| run_id | block_id | claim_id | mode | variant | data_version | status | result_path | deviation | notes |
|---|---|---|---|---|---|---|---|---|---|
| R001 | - | - | plan | 雛形と計画の固定 | 植生 b3b36a0、メッシュ 1cad01a、クマの格子と B_env の面 (sha256 は計画)、豊凶指数 ca2709b9 | done | EXPERIMENT_PLAN.md | - | exposure と通報の関係はまだ計算していない。秋田の豊凶指数 F: 2023 0.1、2024 2.6、2025 0.0、2026 3.2。FL: 0.3、2.6、0.4、3.6 |
| R002 | B0 | - | sanity | 凡例の分類 (`mapping.py`) とテスト | 植生 b3b36a0 の docs/legend_akita.tsv (sha256 b02079c5…) | done | outputs/vegetation_mapping.csv | - | 134 凡例: beech 3、beech_mizunara 1、mizunara 4、konara 2、none 124。凡例の一覧の面積で beech 1,319.5 km²、beech_mizunara 535.1、mizunara 1,323.1、konara 960.3 (合計 4,138.0、秋田の 35.6%)。分類した 10 凡例は、コードごとに期待する名前と照合した。190100 (ミヤマナラ) とカシワの 3 凡例は理由を付けて入れない。テスト 4 件 |
