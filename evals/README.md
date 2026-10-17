# evals: スキルの効きを測る

このディレクトリは、人間が、スキルが効いているかを測るためのもの。エージェントに渡す作業場所には入れない (理由と方法は下)。スキルを削るためのものではない。

## 何のために

エージェントの実行で、スキルがあるときに、落とし穴を拾えるかを見る。見たものは 2 種類に分けて書く。

- ギャップ: スキルなしで落ちて、スキルありで拾えたこと。スキルの効き。
- 教科書: スキルなしでも、モデルが既に知っていること。モデルには要らないが、このリポジトリは人間向けの体系的な教科書でもあるので、消さない。印を付けるだけ。

スキルや節が教科書だと分かっても、削除の理由にしない。削るのは、書いてあることが間違っているときだけ。

## 構成

| 場所 | 中身 |
|---|---|
| `tasks/tasks.md` | 教科書的な課題 (問いと使い道だけ)。課題 1〜8 は、スキルを直すために結果を読んだので、評価としては汚染済み。課題 9〜11 は、直す前の保留 |
| `tasks/rubric.md` | 課題ごとの、拾うべき落とし穴と実測値 (解答) |
| `prompts/agent-task.md` | エージェントへの指示の雛形 (`{{WORKDIR}}`、`{{SHA}}`、`{{TASK}}`) |
| `run_gemini_docker.sh` | 同じ条件で、Gemini を流す (中で使う CLI は Antigravity CLI の `agy`)。イメージは `../Dockerfile.evals.gemini` |
| `run_codex_docker.sh` | 作業場所を Docker (`../Dockerfile.evals.codex`) に閉じ込めて Codex を流す。CPU、メモリ、プロセス数の上限はここで強制する (テスト付き) |
| `prepare_workdir.py` | エージェントの作業場所を、`evals/` なしで用意する (テスト付き) |
| `score_points.py` | 予測の点と正解の点を、半径 (m) の中で 1 対 1 に組にして、適合率、再現率、F1 を出す。課題 28 (アンダーパス) の採点に使う (テスト付き) |
| `tasks/underpass28-truth.csv` | 課題 28 の正解 (23 区の 99 点)。作業場所は `--hide mlit-underpass` で作り、データカードを消す |
| `results/agent-runs.md` | これまでの実行の一覧 (成果物の本体は、リポジトリの外) |
| `results/overview.md` | 設計、結果、直したこと、残った隙のまとめ |

## 評価の流れ

1. エージェントの作業場所を用意する。エージェントに clone させない。clone すると `evals/` が入る。

   ```sh
   python evals/prepare_workdir.py <rev> <作業場所> --task evals/tasks/tasks.md --number 9 \
     --template evals/prompts/agent-task.md > <指示文>
   ```

   スキルなしの基準 (baseline) は `--baseline` を付ける。作業場所は `projects/` だけの空のディレクトリになる。

2. 指示文を、エージェント (Codex や Claude など) に渡す。作業場所の外、特に `evals/` を含む元のリポジトリを読ませない (指示文に書いてある)。
3. 成果物を回収し、`tasks/rubric.md` で採点する。同じ課題を 2 回流し、再現を確かめる (コピーして流し直し、出力を比べる)。
4. 禁止パスのコマンドの読み取りが 0 件かを、エージェントのログで確かめる。
5. 結果を `results/` に書く。スキルあり、なし、の両方を同じ表に並べる。

## Docker で流す

エージェントの計算量を、プロンプトのお願いでなく、Docker (cgroup) で強制する。上限は eval の条件の一部で、スキルあり、なし (baseline) で同じにする。違ってよいのは、`prepare_workdir.py` が作る作業場所の中身と、指示文の「スキルを読め」の段落だけ (baseline にはその資料が無いので、`{{#SKILLS}}` の段落を除く。課題とそれ以外の指示は同じ)。

| 固定するもの | 値 |
|---|---|
| イメージ | `geoai-master-skills-evals-codex` (Codex CLI は `CODEX_VERSION` で固定、既定 0.162.1。結果と一緒に版を記録する) |
| CPU | `--cpuset-cpus=0-7 --cpus=8` (`EVAL_CPUSET` で、別の 8 論理 CPU に変えられる。並列に流すときに分ける) |
| メモリ | `--memory=16g --memory-swap=16g` (swap に逃げない) |
| プロセス数 | `--pids-limit=512` |
| 権限 | `--cap-drop=ALL --security-opt=no-new-privileges`。非 root (`geo`) |
| 環境変数 | `OMP_NUM_THREADS` など 4 つを 8 (協調の上限)。DuckDB は課題の指示で `SET threads=8` |
| mount | 作業場所 → `/work` と、Codex の状態 `~/.codex-evals` → `/home/geo/.codex` だけ。元のリポジトリ、`evals/`、docker.sock、ホームは渡さない |
| 自動で読むもの | 作業場所の `AGENTS.md` の本文と、`.agents/skills/*/SKILL.md` の名前、description、場所 (スキルの一覧として)。作業場所に `.git` が無くても読む (0.162.1、`codex debug prompt-input` で 2026-10-17 に確かめた。baseline の作業場所では、このリポジトリのスキルは 0)。Codex に付いているスキル (`~/.codex/skills/.system` の imagegen など) は両方の条件に見える |

```sh
docker build -f Dockerfile.evals.codex -t geoai-master-skills-evals-codex .

# 初回だけ: ログイン (認証は ~/.codex-evals に保存。イメージには入れない。普段の ~/.codex とは別)
evals/run_codex_docker.sh --login

# 作業場所と、/work を書いた指示文を作って流す (baseline は --baseline を付けるだけ)
python evals/prepare_workdir.py <rev> <作業場所> --task evals/tasks/tasks.md --number 9 \
  --template evals/prompts/agent-task.md --prompt-workdir /work > <指示文>
evals/run_codex_docker.sh --prompt <指示文> <作業場所> -m gpt-6-luna -c model_reasoning_effort=medium
```

課題文に表 (```csv の塊) があるなら、`--table-file <名前>.csv` で、同じ表を作業場所の `data/` に置き、指示文にその場所を足す (スキルあり、なしで同じ)。指示文の中にしか無い 300 行の表は、課題 26 の 6 回のどれでもファイルに写されず、分析が流れなかった (2026-10-17)。

`--prompt` を付けないと、対話の Codex が `/work` で起動する。`--dry-run` で、実行する `docker run` を表示する。Codex の自前の sandbox は、`--cap-drop=ALL` では動かないので、`--dangerously-bypass-approvals-and-sandbox` で流す。コンテナが sandbox。ネットワークは開いている (データの取得とモデルの API に必要)。

## Gemini で流す (Gemini eval)

Codex と同じ課題、同じ作業場所、同じ CPU とメモリの条件で、Gemini を流して比べる。中で動かす CLI は Antigravity CLI (`agy`) だが、評価の名前は「Gemini eval」にそろえる。Codex 用と同じ分析ライブラリの版 (rasterio 1.4.1 を含む) なので、違うのはモデルと CLI だけ。

| 固定するもの | 値 |
|---|---|
| イメージ | `geoai-master-skills-evals-gemini`。`agy` の版は `AGY_VERSION` で固定 (既定 1.3.5)。公式のインストーラは最新を入れ、`agy` は自己更新もするので、版が違うとビルドが失敗する。上げるときは `--build-arg AGY_VERSION=...` で意図して上げ、結果と一緒に版を記録する。root で入れるので、実行中の自己更新はできない |
| 認証 | OAuth (Google アカウント) か API キー。baseline とスキルありで同じにする。下を参照 |
| モデルと effort | OAuth: `gemini-3.8-flash-low` (effort はモデル名の末尾。3.6 Flash は一覧に無い)。API キー: `gemini-3.6-flash` と `--effort low`。`EVAL_MODEL`、`EVAL_EFFORT` で変える。一覧は `agy models` (認証方式で違う) |
| CPU、メモリ、プロセス数、権限、mount | Codex と同じ (上の表) |
| ログ | `--prompt` で、構造化ログ (stream-json) が標準出力に出る。ツール実行の各段階が見える |

```sh
docker build -f Dockerfile.evals.gemini -t geoai-master-skills-evals-gemini .

# 認証 (どちらか)
evals/run_gemini_docker.sh --login      # OAuth: 表示された URL でサインインし、認可コードを貼る。トークンは ~/.gemini-evals に保存
cp .env.example .env                     # API キー: 値を書く (.env は git に入れない)

python evals/prepare_workdir.py <rev> <作業場所> --task evals/tasks/tasks.md --number 9 \
  --template evals/prompts/agent-task.md --prompt-workdir /work > <指示文>
evals/run_gemini_docker.sh --prompt <指示文> <作業場所> > <ログ.jsonl>
```

`--auth oauth|api-key` で認証を選ぶ。省略すると、`~/.gemini-evals` にトークンがあれば OAuth、無ければ API キー。OAuth のときはキーを渡さない。API キーは、名前だけを読み (`GEMINI_API_KEY`、`GOOGLE_GENERATIVE_AI_API_KEY`。`.env` の、ほかの値は読まない)、`docker run -e GEMINI_API_KEY` で渡す。イメージ、`/work`、コマンドラインには入らない。ただし、エージェントはコンテナの中で、そのキーを環境変数として見られる。使用量の上限を付けたキーを使うこと。キーのプロジェクトに課金の残高が無いと `Error 402 (prepayment credits are depleted)` で止まる。

`~/.gemini-evals` に、OAuth のトークンが入る。普段の `~/.gemini` とは別。設定は、実行のたびに書き直す。`--dry-run` で、実行する `docker run` を表示する。

## OpenCode で流す

Codex、Gemini と同じ課題、作業場所、CPU、メモリ、プロセス数、権限、分析ライブラリの版で、OpenCode を流す。当面の eval の既定は、API キーの要らない無料のモデル (`opencode/deepseek-v4.1-flash-free`、`opencode/glm-5.3-flash-free`)。フロンティアのモデルより弱いので、スキルの効きの差が出やすい。

| 固定するもの | 値 |
|---|---|
| イメージ | `geoai-master-skills-evals-opencode`。OpenCode は公式のリリースのバイナリを `OPENCODE_VERSION` (既定 1.19.3) と sha256 で固定。公式のイメージ (`ghcr.io/anomalyco/opencode`) は Python の分析環境を持たないので、土台にしない |
| モデル | `EVAL_MODEL` (既定 `opencode/deepseek-v4.1-flash-free`)。`opencode/glm-5.3-flash-free` も同じ runner で流せる。一覧はコンテナの中で `opencode models opencode` |
| 設定、認証、状態 | 普段の `~/.config/opencode`、`~/.local/share/opencode`、`OPENCODE_*` の環境変数は持ち込まない。状態はコンテナの中に置き、`--rm` で消える (実行どうしで会話が見えない)。設定は `OPENCODE_CONFIG_CONTENT` で渡し、共有を止め (`"share": "disabled"`)、更新を確かめない |
| 許可 | `opencode run --auto`。非対話の実行では、確認を求める許可 (作業場所の外のパス、同じ呼び出しの 3 回の繰り返し) は、`--auto` が無いと全て拒否される。コンテナが sandbox。明示の拒否 (`.env` の読み取り) は残る。`--pure` で外のプラグインを読まない |
| 自動で読むもの | 作業場所の `AGENTS.md` (指示として) と `.agents/skills/*/SKILL.md` (スキルの道具として)。スキルありの作業場所にだけあるので、違いは作業場所の中身だけ。Codex も同じ 2 つを読む (上の Codex の表)。`.claude` は `OPENCODE_DISABLE_CLAUDE_CODE=1` で読まない (OpenCode 1.19.3 の文書による) |
| ログ | `--prompt` で、プロンプトを標準入力から渡し、`--format json` の 1 行 1 イベントが標準出力に出る。`effort.py` が読む |

```sh
docker build -f Dockerfile.evals.opencode -t geoai-master-skills-evals-opencode .

python evals/prepare_workdir.py <rev> <作業場所> --task evals/tasks/tasks.md --number 9 \
  --template evals/prompts/agent-task.md --prompt-workdir /work > <指示文>
EVAL_MODEL=opencode/glm-5.3-flash-free evals/run_opencode_docker.sh --prompt <指示文> <作業場所> > <ログ.jsonl>
```

無料のモデルは、混んでいると急に止まる。smoke test (2026-10-17) では、`glm-5.3-flash-free` の 1 回目が 429 (`Upstream request failed: Endpoint is unavailable.`、`isRetryable: true`) で、終了コード 1、ログは `"type": "error"` のイベント 1 行だけだった (2 回目は通った)。ログに `"type": "error"` のある実行と、stderr に `Rate limit exceeded` のある実行は、提供側の失敗として採点に数えない。matrix のスクリプトは、そこで止めるか、その実行だけ流し直す。

2026-10-17 には、4〜5 本を同時に流していた 14:25 に、全部の実行が同時に黙った。`Rate limit exceeded` は JSON のイベントには出ず、opencode はイベントを出さずに待って再試行を続ける (1 行も出ない実行になる)。runner は `--print-logs` で opencode のログを stderr に出すので、stderr をファイルに残して見る。止めて 50 分たっても、1 本だけの小さな問い合わせが同じ理由で返らなかった。制限の単位と戻るまでの時間は未確認。また、opencode を PID 1 で動かすと SIGTERM で止まらず、`timeout` が効かなかった。runner は `--init` を付ける。

時間の上限 (`timeout` で包んだときの終了コード 124) は、提供側の失敗ではなく、エージェントの振る舞いとして数える。流し直しで置き換えず、上限の時点で残っていた報告を「時間切れ」と添えて採点し、手間の表にも載せる。OpenCode の bash の道具は、呼び出しごとに `timeout` を指定しないと 120 秒で打ち切る (1.19.3 の既定。最大は 600 秒。Codex には無い)。課題 27 (2026-10-17) では、glm のスキルありの 2 回が 90 分の上限に届いた。1 回は `timeout` を一度も指定せず、打ち切りの後に処理を裏で走らせて `sleep` で待ち続け、もう 1 回は長い読み込みを何度も流し直した。2 回とも、約 167k トークンで文脈が要約された。runner の設定は変えず、この差もエージェントと道具の違いとして読む。上限をエージェントに知らせるときは、`prepare_workdir.py --time-limit MIN` で指示文に 1 行足し (baseline とスキルありで同じ文)、matrix のスクリプトで同じ分数の `timeout` をかける。

## なぜ `evals/` を渡さないか

rubric には答えが書いてある。エージェントが clone して、リポジトリの中を読むと、答えが見える。`prepare_workdir.py` は、`git archive` (`.gitattributes` の `evals/ export-ignore` を守る) で用意し、さらに `evals/` を自分で消す。属性が抜けても漏れない。`evals/` の外のファイルが `evals/results/` か `evals/tasks/` を指していたら、作業場所を作らずに止まる。結果の索引を `docs/` に置いていたとき、スキルありの作業場所に課題 27 の答えが入っていた (流す前に見つけた)。評価の索引と状況は `evals/status.md` に置く。maplibre-agent-skills は、モデルに SKILL.md だけをシステムプロンプトとして渡す方式 (promptfoo) なので、そもそもモデルが `evals/` を読めない。ここは、エージェントが作業場所を歩くので、作業場所から消す。

## 正解と手間の両方を記録する

採点 (rubric) は正解を見る。データ固有の罠や結合の鍵のように、だれかが一度はまって共有すれば済む知識は、強いエージェントなら自力でも正解にたどり着く。その場合、スキルの効き目は正解の数でなく、正解までの手間 (tokens、道具の呼び出し、失敗した呼び出し、時間) に出る。実行ごとに、次で手間も記録する。

```bash
python evals/effort.py RUN_DIR [RUN_DIR ...]   # 1 実行 1 行の TSV
```

実行のディレクトリは、`prompt.md`、`log` (エージェントの出力)、`exit` (終わったときに書く) を持つ。Codex の文字のログと、agy の stream-json の両方を読む。tokens は CLI ごとに数え方が違うので、同じエージェントの中だけで比べる。スキルありの tokens には、スキルを読む分が含まれる。

## 読むときの注意

- 直すために読んだ課題では、効果を測らない。新しい課題 (保留) で測る。
- 1 回ずつの実行の差は、偶然とスキルの効果を分けられない。同じ課題を繰り返す。
- baseline は、スキルがないエージェントの動き。モデルの強さによって、教科書とギャップの分かれ目が変わる。実行したモデルと日付を書く。
