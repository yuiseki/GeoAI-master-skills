# 発火テスト: 後ろの手順の reference と「読むとき」の列 (2026-11-10)

## 問い

[trigger-holdout2](trigger-holdout2-2026-11-10.md) の後、「読むとき」の列は 59 スキルのうち 4 つにしか無かった。ほかのスキルでも、後ろの手順でだけ名指しされる reference を、手順を決める依頼で開くか。列を足すと開くようになるか。

## 変えたこと

- 列を足す前に、[trigger_holdout3.yaml](../trigger_holdout3.yaml) に 10 ケースを書いた (5018773)。8 スキルの、手順 6〜9 でだけ名指しされる reference を狙う (cox.md、history-and-level.md、controls.md、time-aggregation.md、validation.md、sensitivity.md、destination-mlp.md、training.md)。
- 30 スキルの reference の表に「読むとき」の列を足した (54ca9f9)。どの手順の前に読むかを書いた。1 つの方法に 1 つの reference が対応する表では、どの選び方のときに読むかを書いた。目録の形のスキル (dataset-discovery など) と、表の形が違うスキル (cross-validation-design、spatial-autocorrelation、spatial-data-integration) には足していない。

## 測り方

trigger.py で、5018773 (前) と 54ca9f9 (後) を、各ケース 5 回、同じ時間帯に並べて流した。Gemini CLI gemini-3.8-flash-low (agy 1.3.5) と Codex gpt-6-luna medium (codex-cli 0.162.1)、上限 10 分。ERROR は 0。ログは `~/Workspaces/tmp/trigger-holdout3-{before,after}-{gemini,codex}/`。

## 結果

| | 前 (5018773) | 後 (54ca9f9) |
|---|---:|---:|
| Gemini | 45/50 | 48/50 |
| Codex | 50/50 | 50/50 |
| Gemini、1 回あたりに読んだ reference の数 | 1.88 | 1.80 |
| Codex、1 回あたりに読んだ reference の数 | 4.08 | 4.14 |

- 列を足す前から、ほとんど開いていた。手順を決める依頼で後ろの手順の reference も読む、という AGENTS.md の 1 文 (ce8a4e3) が、既にこの 10 ケースの多くを支えていると読める (この版の前は測っていないので、確かめてはいない)。
- Gemini の外れは、前が h16-bear-grid の 4 回と h23-building-unet の 1 回。h16 の 4 回は grid-risk-mapping の SKILL.md を開いたが reference を 1 本も開かず、「確率として読んでよいか」という言葉から uncertainty-estimation を開いていた。後は h16 が 1/5 から 4/5 になり、外れは h16 と h17 の 1 回ずつ。どちらも SKILL.md だけを開いて答えた。
- 読む reference の数は増えていない。列が読みすぎを生んだ様子は無い。

## 確かめていないこと

- 1 ケース 5 回で、区間は出していない。前の 45/50 から後の 48/50 の差は揺れと区別できない。はっきり動いたのは h16 の 1/5 から 4/5 だけ。
- 最初の 25 ケース (trigger_cases.yaml) は 54ca9f9 で流し直していない。列は description を変えないので、開いてはいけないケースへの影響は小さいと考えるが、測っていない。
- ケースの書き手は列を書いた本人で、言い方の幅は 10 通り。
