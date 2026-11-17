# 発火テストの条件と採点の表

`evals/trigger.py` の各実行 (OUT_DIR) から、条件と採点の表だけを写した。記録の本体 (ケースと回ごとの prompt.md、log、stderr、exit) は入れていない。読み方と結論は、右の欄の結果の文書にある。全部の記録を入れたのは Qoder の回だけ ([../trigger-holdout-qoder-2026-11-16/](../trigger-holdout-qoder-2026-11-16/))。

- manifest.json: 版 (revision)、ケースのファイルと sha256、エージェント、モデル、effort、Docker のイメージ、CLI の版、上限の分。これを書くようになる前の実行には無い。
- summary.tsv: 1 回 1 行 (判定、足りなかったもの、読んではいけないのに読んだもの、読んだもの)。
- cases.tsv: ケースごとの合格の数、採点した数、ERROR の数。

| フォルダ | 版 | エージェント、モデル | 結果の文書 |
|---|---|---|---|
| trigger-2026-11-09 | 1ffb40b〜0380d88 (混在) | OpenCode deepseek-v4.1-flash-free | [trigger-2026-11-09.md](../trigger-2026-11-09.md) |
| trigger-2026-11-09r | 固定の前 (混在) | OpenCode deepseek-v4.1-flash-free | 同上 |
| trigger-2026-11-09-codex | 6473806 | Codex gpt-6-luna medium | 同上 |
| trigger-2026-11-09-gemini | 6473806 | Gemini 3.8 Flash low | 同上 |
| trigger-holdout-before-codex、-gemini | 20f88c1 | Codex、Gemini | [trigger-holdout-2026-11-09.md](../trigger-holdout-2026-11-09.md) |
| trigger-holdout-a-codex、-gemini | a49000f | Codex、Gemini | 同上 |
| trigger-holdout-ab-codex、-gemini | 68ca7f2 | Codex、Gemini | 同上 |
| trigger-ab-codex、-gemini | 68ca7f2 (最初の 25 ケース) | Codex、Gemini | 同上 |
| trigger-subagent-2026-11-10 | 68ca7f2 | Claude Code のサブエージェント Opus 5.5 (manifest なし) | 同上 |
| trigger-subagent-sonnet-2026-11-10 | 68ca7f2 | Claude Code のサブエージェント Sonnet 5.5 (manifest なし) | 同上 |
| trigger-claude-low-none、-ctx | 68ca7f2 | Claude Code Sonnet 5.5 low (Docker) | [trigger-claude-sonnet-low-2026-11-10.md](../trigger-claude-sonnet-low-2026-11-10.md) |
| trigger-holdout2-before-gemini | 23bf06b | Gemini | [trigger-holdout2-2026-11-10.md](../trigger-holdout2-2026-11-10.md) |
| trigger-holdout2-after-gemini、-codex | ce8a4e3 | Gemini、Codex | 同上 |
| trigger-ce8a4e3-gemini | ce8a4e3 | Gemini | 同上 |
| trigger-holdout3-before-codex、-gemini | 5018773 | Codex、Gemini | [trigger-holdout3-2026-11-10.md](../trigger-holdout3-2026-11-10.md) |
| trigger-holdout3-after-codex、-gemini | 54ca9f9 | Codex、Gemini | 同上 |
| trigger-playground-claude、-codex、-gemini | a176925 | Claude Code Sonnet 5.5、Codex、Gemini | [playground-e2e-2026-11-12.md](../playground-e2e-2026-11-12.md) |

入れなかったもの: 試走 (smoke、probe、pilot) と、どの結果の文書も使っていない trigger-2026-11-09b。サブエージェントの回の runs.tsv は、手元の機械のパスを含むので入れていない。
