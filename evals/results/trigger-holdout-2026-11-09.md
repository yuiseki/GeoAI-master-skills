# 発火テスト: reference の渡し方を直した効果 (取っておいたケースで、2026-11-09)

最初の発火テスト ([trigger-2026-11-09.md](trigger-2026-11-09.md)) で 3 つのモデル全てが開かなかった reference は、analysis-reporting の failure-modes.md と spatial-gnn の dcrnn.md だった。この 2 つへの渡し方を直し、効果を、直す前に書いて取っておいた 7 ケース (`evals/trigger_holdout.yaml`) で測った。外れを見て直したケースで測ると、効果が大きく見える。

| 版 | リビジョン | 変えたこと |
|---|---|---|
| 前 | 20f88c1 | なし (取っておくケースを足しただけ) |
| A | a49000f | 2 つの SKILL.md の reference の表に「読むとき」の欄を足し、手順の段からも指した |
| A + B | 68ca7f2 | A に加え、AGENTS.md の冒頭に「スキルの名前だけから手順を答えない。使うスキルの SKILL.md を開き、表の『読むとき』が今の段階なら reference も開く」 |

変えるのは 1 つずつ。直さなかった 3 つの reference (cross-validation-design の spatial.md、spatial-data-modeling の spatial-regression.md、point-pattern-analysis の ripley.md) を狙う h5〜h7 は対照。それぞれの版を、manifest.json で条件を固定し、ケースごとに 5 回流した。ログは `~/Workspaces/tmp/trigger-holdout-{before,a,ab}-{codex,gemini}/`。ERROR は 0。

| ケース (狙う reference) | Codex 前 | Codex A | Codex A+B | Gemini 前 | Gemini A | Gemini A+B |
|---|---:|---:|---:|---:|---:|---:|
| h1、h2 (dcrnn.md) | 8/10 | 10/10 | 10/10 | 0/10 | 0/10 | 0/10 |
| h3、h4 (failure-modes.md) | 4/10 | 5/10 | 10/10 | 4/10 | 7/10 | 10/10 |
| h5〜h7 (対照、直していない) | 11/15 | 11/15 | 10/15 | 4/15 | 1/15 | 10/15 |

モデルは Codex gpt-6-luna、effort medium (codex-cli 0.162.1) と Gemini CLI gemini-3.8-flash-low (agy 1.3.5)、上限 10 分。

## 読み方

- 効いたのは B (AGENTS.md) だった。failure-modes.md は 2 つのモデルとも 10 回のうち 10 回開くようになった。Gemini では、直していない対照の 3 つも 4/15 から 10/15 に上がった。B はどのスキルにも当たる決まりなので、対照にも効くのは筋が通る。
- A だけでは、はっきりした効果は見えない。Codex の dcrnn.md は 8/10 から 10/10、Gemini の failure-modes.md は 4/10 から 7/10 に上がったが、1 群 10 回では揺れと区別できない。Gemini の対照は A で 4/15 から 1/15 に下がっており、この版で直していないものが 3 回分動く揺れがある。
- Gemini は、どの版でも dcrnn.md を開かなかった (30 回のうち 0 回)。spatial-gnn の SKILL.md は毎回開き、2 回は graph.md と evaluation.md も開いたが、dcrnn.md には進まない。表の「読むとき」に学習を挙げても、学習の手順を答えるところで reference を開かずに答えている。原因は確かめていない。
- Codex の対照は 11/15 から 10/15 で、B で悪くはなっていない。

## 確かめていないこと

- 1 群 10 回 (対照は 15 回) で、差の区間は出していない。前から A + B への failure-modes.md の 4/10 から 10/10 は大きいが、A だけの差は揺れの内にある。
- B が最初の 25 ケースの点を変えるかは、流していない。
- Gemini が dcrnn.md を開かない理由。
