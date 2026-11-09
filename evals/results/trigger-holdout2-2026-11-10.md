# 発火テスト: 手順の後ろの reference を読ませる (2 つ目の取っておいたケースで、2026-11-10)

## 問い

Gemini 3.8 Flash low は、A と B の後も dcrnn.md と ripley.md をほとんど開かなかった (最初の 25 ケースの e1、i5、取っておいたケースの h1、h2 で 0/16)。ログでは、SKILL.md を読むと答えるか、表の上の 2 本 (graph.md、evaluation.md) まで読んで止まる。手順を決める依頼を「まだ手順の初め」と読み、手順 6、7 で読むとされた dcrnn.md を今の段階に入れていない、と仮定した。point-pattern-analysis には「読むとき」の列が無く、どの手順も ripley.md を名指ししていなかった。

## 変えたこと (ce8a4e3)

- AGENTS.md に 1 文: 手順を決める依頼では、決める手順のどこかで読むとされる reference は全て今の段階に入る。spatial-gnn の SKILL.md は変えていないので、dcrnn.md のケースはこの 1 文だけの効果になる。
- point-pattern-analysis の reference の表に「読むとき」の列を足し、手順 4 で ripley.md を名指しした。ripley.md のケースは、この 2 つと上の 1 文を合わせた効果になる。

## 測り方

直す前に、dcrnn.md と ripley.md を狙う 6 ケースを新しく書いてコミットした (`evals/trigger_holdout2.yaml`、23bf06b、sha256 10915d8d)。外れを見たケースでは測らない。同じケースを直す前 (23bf06b) と直した後 (ce8a4e3) で各 5 回流した。条件は Gemini CLI 1.3.5、gemini-3.8-flash-low、上限 10 分。ERROR は 0。ログは `~/Workspaces/tmp/trigger-holdout2-{before,after}-gemini/`。

## 結果

| ケース | 狙う reference | 23bf06b | ce8a4e3 |
|---|---|---:|---:|
| h8-river-dcrnn | dcrnn.md | 2/5 | 5/5 |
| h9-diffusion-conv | dcrnn.md | 0/5 | 5/5 |
| h10-pems-reproduce | dcrnn.md | 5/5 | 5/5 |
| h11-l-function | ripley.md | 5/5 | 5/5 |
| h12-pair-counts | ripley.md | 1/5 | 5/5 |
| h13-ambulance-calls | ripley.md | 0/5 | 5/5 |
| 計 | | 13/30 | 30/30 |

- 直す前の点は言い方で大きく変わった。「再現」(h10) や「L 関数」(h11) と書くと開き、名前を出さない h9、h13 は 1 回も開かなかった。直した後は 6 ケースとも 5/5。
- 最初の 25 ケースを ce8a4e3 で各 3 回流し直すと、Gemini は 65/75 (68ca7f2) から 73/75 になった。e1-dcrnn と i5-clustered-points は 0/3 から 3/3。発火してはいけない 3 ケースは 3/3 のまま。残る外れは e3-spatial-lag の 2 回で、spatial-weights-design の reference を 4 本読んで spatial-data-modeling を開かなかった (68ca7f2 でも 2/3)。ログは `~/Workspaces/tmp/trigger-ce8a4e3-gemini/`。
- Codex gpt-6-luna medium は ce8a4e3 で 6 ケース各 5 回、29/30 (h9 の 1 回が dcrnn.md を開かず)。直す前の Codex は流していないので、Codex への効果は言えない。

## 確かめていないこと

- 1 ケース 5 回で、差の区間は出していない。13/30 から 30/30 は大きいが、ケースの書き手は直した本人で、直し方を知る前に書いたとはいえ、言い方の幅は 6 通りしかない。
- AGENTS.md の 1 文が、読む reference を増やしすぎていないか。e3 の外れでは、関係の薄いスキルの reference を 4 本読んでいた。読んだ reference の数は数えていない。
- 「読むとき」の列は 59 スキルのうち 4 つにしか無い。ほかのスキルで後ろの手順の reference が開かれるかは測っていない。
