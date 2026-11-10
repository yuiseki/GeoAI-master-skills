# Claude Code (Sonnet 5.5, effort low) on h1 and h2, with and without a CLAUDE.md, 2026-11-10

Question: is Sonnet missing a reference (h2 in [trigger-holdout-2026-11-09](trigger-holdout-2026-11-09.md), 2 of 5
runs as a subagent) a trait of the model, or of the everyday session it ran in (the user's CLAUDE.md, memory,
hooks)? And does a low effort, the setting where Gemini low misses most, make Sonnet miss too?

## Conditions

- Skills and cases: 68ca7f2, evals/trigger_holdout.yaml, the 2 cases Sonnet missed or nearly missed
  (h1-diffusion-rnn, h2-station-dcrnn), 5 runs each.
- Claude Code 2.1.321 in Docker (evals/run_claude_docker.sh, image geoai-master-skills-evals-claude), the same limits
  and workdir as the Codex and Gemini runs. `--model claude-sonnet-5-5 --effort low`.
- Two OUT_DIRs, differing only in `--context`:
  - none: only the workdir's AGENTS.md.
  - ctx: /Workspaces/CLAUDE.md (sha256 fc9afc93...) mounted as /CLAUDE.md, the global rules of the user's sessions.
- Commands:
  `python3 evals/trigger.py run ~/Workspaces/tmp/trigger-claude-low-{none,ctx} --rev 68ca7f2
  --cases evals/trigger_holdout.yaml --only h1-diffusion-rnn h2-station-dcrnn --repeats 5 --agent claude
  --model claude-sonnet-5-5 --effort low [--context /Workspaces/CLAUDE.md]`

## Results

| case | none | ctx |
|---|---|---|
| h1-diffusion-rnn | 5/5 | 5/5 |
| h2-station-dcrnn | 5/5 | 5/5 |

- First graded 19/20: one ctx run of h2 failed on dcrnn.md. Its log shows
  `cd /work/.agents/skills; cat spatial-gnn/references/{graph,evaluation,dcrnn}.md; ...`: it read all three. The
  grader's brace expansion carried the `;` into every expanded word, so after the cd only graph.md counted. Fixed in
  trigger.py (a brace word stops at shell separators) with a test; regraded, no other saved run changed by it.
- Every run read SKILL.md and all three references of spatial-gnn, most with one `cat` of the three. Median 2 to 2.5
  tool calls, 12 s, about 1,180 output tokens per run.
- The single Docker smoke runs of h2 at Claude Code's default effort (medium) passed in both conditions.

## What it says, and what it does not

- In a clean container Sonnet at low effort did not miss in 20 runs, against 2 misses in 5 runs as a subagent of an
  everyday session. Removing that session's surroundings, not raising the effort, is what changed. Which part of
  the session (the subagent's own prompt, the absence of AGENTS.md being loaded as such, memory, hooks) caused the
  misses is not separated here: the CLAUDE.md alone (ctx) did not bring them back.
- 5 runs per case cannot tell a miss rate of 0 from one of 10 to 20 %.
- Not run: the other 33 held-out cases with Claude Code in Docker, and medium effort beyond the one smoke run.
