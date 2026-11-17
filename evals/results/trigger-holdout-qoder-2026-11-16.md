# 発火テスト: Qoder CLI (Auto) で取っておいた 7 ケース (2026-11-16)

[trigger-holdout-2026-11-09](trigger-holdout-2026-11-09.md) の 7 ケースを、Codex と Gemini の A + B と同じ版で、Qoder CLI に 5 回ずつ解かせた。

## 条件

- スキルとケース: 68ca7f2 の `evals/trigger_holdout.yaml` (sha256 d0ebe9d2)。Codex と Gemini の A + B と同じ版。
- qodercli 1.1.86 を Docker で (`evals/run_qoder_docker.sh`、イメージ geoai-master-skills-evals-qoder、sha256:73d115bb)。モデルは Auto、effort は CLI の既定、上限 10 分。
- 記録: [trigger-holdout-qoder-2026-11-16/](trigger-holdout-qoder-2026-11-16/) に全部置いた。manifest.json (条件)、summary.tsv (1 回 1 行)、cases.tsv (ケースごと)、ケースと回ごとのフォルダ (prompt.md、agent.json、log は qodercli の stream-json、stderr、exit)。採点し直すときは、リポジトリの外に写してから `python3 evals/trigger.py judge <写した先>` (trigger.py はリポジトリの中の OUT_DIR を受け付けない)。
- コマンド: `python3 evals/trigger.py run ~/Workspaces/tmp/trigger-holdout-ab-qoder --rev 68ca7f2 --cases evals/trigger_holdout.yaml --repeats 5 --agent qoder`

## 結果

| ケース (狙う reference) | Qoder Auto | Codex A+B | Gemini A+B | Claude サブエージェント |
|---|---:|---:|---:|---:|
| h1、h2 (dcrnn.md) | 10/10 | 10/10 | 0/10 | 10/10 |
| h3、h4 (failure-modes.md) | 10/10 | 10/10 | 10/10 | 10/10 |
| h5〜h7 (対照) | 15/15 | 10/15 | 10/15 | 15/15 |

- 35 回全て合格、ERROR は 0。
- 1 回の時間の中央値は 17 秒 (9〜88 秒)、道具の呼び出しの往復は中央値 8。
- 結果の欄の credits は 35 回で 21.6 (1 回 0.28〜2.08)。ドル換算はどの回も 0。
- 35 回のうち 24 回で AGENTS.md を開くか grep した。Skill の道具は使わず、どの回もファイルを直接読んだ。

## 言えること、言えないこと

- Auto は、中で選ばれたモデルが記録に出ない (model の欄も modelUsage も "auto")。回ごとに違うモデルだった可能性があり、「Qoder の或るモデルの成績」とは読めない。
- 1 ケース 5 回では、外れの率が 0 なのか 10〜20% なのかは区別できない。Codex と Gemini で差がついたのは dcrnn.md (Gemini) と対照で、Qoder は Claude と同じく、どちらも外さなかった。
