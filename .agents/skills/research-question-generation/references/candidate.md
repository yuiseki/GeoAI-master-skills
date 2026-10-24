# Candidate の記録形式

候補は UTF-8 JSON にする。検査スクリプトが読む欄と、人が批評する欄を分ける。

| 欄 | 意味 |
|---|---|
| `mode` | `exploration` または `digging`。後者は `history_anchor` に既存の報告と、意外だった観測を記す |
| `social_problem`, `working_hypothesis` | 誰のどの不利益を、誰の判断で減らしたいか。仮説は観測できる差や方向と反証条件を書く。形式検査の必須欄ではないが、Critic で中身を確認する |
| `question`, `decision_use` | 世界について問う文と、誰が何に使うか。方法名だけの文にはしない |
| `target_quantity`, `unit`, `time_alignment` | estimand に相当する対象量、1行の意味、入力の時点差と主期間 |
| `datasets` | 利用するデータセット ID の配列。データを名だけ並べず、各データが答えに何を供給するかも検討する |
| `joins` | `left`, `right`, `how`, `why` の配列。全データがつながるようにし、結合の不一致と重複を pilot で数える |
| `single_source_design` | 単一データの観測過程・測定誤差監査に限る例外。`measurement_problem`, `comparison`, `decision_consequence`, `why_simple_summary_fails` を具体的に記し、`joins=[]` とする。形式検査を通っても Critic が実質を判断する |
| `required_variables` | `dataset`, `table`, `column` の配列。frontmatter に無い列には、再現可能な既存コードの `evidence_file` を付ける。存在を証明するだけで意味の正しさは保証しない |
| `methodological_decisions`, `failure_modes`, `robustness_checks` | 答えを変えうる選択、既知の破綻、比較する別設定 |
| `simplest_solver` | `method`, `why_insufficient`。単純解法で十分なら候補を落とす |
| `unknowns` | データから答えられない部分。問いの真実として暗黙に要求しない |
| `novelty` | `closest_task`, `difference_dimension`, `substantive_difference`。地名だけの差は不可 |
| `prediction` | `main_result`, `difficulty`, `fragile_assumption`, `needed_capabilities`。探索前に固定し、実行後に照合できる形にする |
| `rubric` | 良い分析と悪い分析を分ける採点観点。手法名を強制せず、失敗の扱いを含む |
| `claim_type`, `causal_design` | 因果効果を問う場合は `claim_type=causal` とし、処置、結果、estimand、時点、識別仮定を明記する。埋められなければ関連の問いへ書き直すか棄却する |

スクリプトが返す棄却理由は形式的な警報であり、通過しても以下は批評が必要。列の名前と実際の意味、同じ場所を表す別 ID、複数年の境界、列にはあるが測っていない量、近い課題と異なる対象名だけの焼き直し、pilot での対象の空集合などは、文章と実データで確かめる。

pilot を添えるときは、対象量と pilot の測定量、両者が一致しない場合の用途、未検証の主要仮定を明記する。代理指標だけで課題の中心的な主張が実証されたように書かない。

JSON は proposal の根拠として保存できる。正式課題のファイルへ自動転記する処理は持たない。
