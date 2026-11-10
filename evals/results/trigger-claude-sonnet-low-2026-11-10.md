# Claude Code (Sonnet 5.5、effort low) で h1 と h2、CLAUDE.md の有無、2026-11-10

問い: [trigger-holdout-2026-11-09](trigger-holdout-2026-11-09.md) で Sonnet がサブエージェントとして h2 の reference を 5 回中 2 回読み落としたのは、モデルの性質か、それが走った普段のセッション (利用者の CLAUDE.md、メモリ、フック) のせいか。また、Gemini low が最も外す軽い設定 (effort low) で、Sonnet も外すようになるか。

## 条件

- スキルとケース: 68ca7f2 の evals/trigger_holdout.yaml から、Sonnet が外したか外しかけた 2 ケース (h1-diffusion-rnn、h2-station-dcrnn) を 5 回ずつ。
- Claude Code 2.1.321 を Docker で (evals/run_claude_docker.sh、イメージ geoai-master-skills-evals-claude)。Codex と Gemini と同じ上限と作業場所。`--model claude-sonnet-5-5 --effort low`。
- OUT_DIR は 2 つで、違いは `--context` だけ。
  - none: 作業場所の AGENTS.md だけ。
  - ctx: /Workspaces/CLAUDE.md (sha256 fc9afc93...) を /CLAUDE.md として渡す。利用者のセッションの全体の規則。
- コマンド:
  `python3 evals/trigger.py run ~/Workspaces/tmp/trigger-claude-low-{none,ctx} --rev 68ca7f2 --cases evals/trigger_holdout.yaml --only h1-diffusion-rnn h2-station-dcrnn --repeats 5 --agent claude --model claude-sonnet-5-5 --effort low [--context /Workspaces/CLAUDE.md]`

## 結果

| ケース | none | ctx |
|---|---|---|
| h1-diffusion-rnn | 5/5 | 5/5 |
| h2-station-dcrnn | 5/5 | 5/5 |

- 最初の採点は 19/20 で、ctx の h2 の 1 回が dcrnn.md の不足で不合格だった。記録では `cd /work/.agents/skills; cat spatial-gnn/references/{graph,evaluation,dcrnn}.md; ...` で 3 本とも読んでいた。採点の括弧の展開が `;` を展開後の語すべてに付けたため、cd の後で graph.md しか数えなかった。trigger.py を直し (括弧の語はシェルの区切りで止まる)、テストを足した。保存した記録をすべて数え直し、この修正で変わったのはこの 1 回だけだった。
- どの回も spatial-gnn の SKILL.md と reference 3 本を全部読んだ。多くは 1 回の `cat` で 3 本まとめて。1 回あたりの中央値は道具の呼び出し 2〜2.5 回、12 秒、出力約 1,180 トークン。
- Claude Code の既定の effort (medium) で流した h2 の試走 1 回ずつは、どちらの条件でも合格だった。

## 言えること、言えないこと

- 余計なもののないコンテナでは、effort low の Sonnet は 20 回とも外さなかった。普段のセッションのサブエージェントでは 5 回中 2 回外していた。変わったのは effort を上げたことではなく、セッションの周りを取り除いたこと。周りのどれ (サブエージェントへの依頼文、AGENTS.md が作業場所の規則として読まれないこと、メモリ、フック) が外れの元かは分けていない。CLAUDE.md だけを戻しても (ctx) 外れは戻らなかった。
- 1 ケース 5 回では、外れの率が 0 なのか 10〜20% なのかは区別できない。
- 流していないもの: 残りの held-out 33 ケースを Docker の Claude Code で流すこと、試走 1 回を超える medium での実行。
