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
| イメージ | `geoai-skills-evals-codex` (Codex CLI は `CODEX_VERSION` で固定、既定 0.162.1。結果と一緒に版を記録する) |
| CPU | `--cpuset-cpus=0-7 --cpus=8` (`EVAL_CPUSET` で、別の 8 論理 CPU に変えられる。並列に流すときに分ける) |
| メモリ | `--memory=16g --memory-swap=16g` (swap に逃げない) |
| プロセス数 | `--pids-limit=512` |
| 権限 | `--cap-drop=ALL --security-opt=no-new-privileges`。非 root (`geo`) |
| 環境変数 | `OMP_NUM_THREADS` など 4 つを 8 (協調の上限)。DuckDB は課題の指示で `SET threads=8` |
| mount | 作業場所 → `/work` と、Codex の状態 `~/.codex-evals` → `/home/geo/.codex` だけ。元のリポジトリ、`evals/`、docker.sock、ホームは渡さない |

```sh
docker build -f Dockerfile.evals.codex -t geoai-skills-evals-codex .

# 初回だけ: ログイン (認証は ~/.codex-evals に保存。イメージには入れない。普段の ~/.codex とは別)
evals/run_codex_docker.sh --login

# 作業場所と、/work を書いた指示文を作って流す (baseline は --baseline を付けるだけ)
python evals/prepare_workdir.py <rev> <作業場所> --task evals/tasks/tasks.md --number 9 \
  --template evals/prompts/agent-task.md --prompt-workdir /work > <指示文>
evals/run_codex_docker.sh --prompt <指示文> <作業場所> -m gpt-6-luna -c model_reasoning_effort=medium
```

`--prompt` を付けないと、対話の Codex が `/work` で起動する。`--dry-run` で、実行する `docker run` を表示する。Codex の自前の sandbox は、`--cap-drop=ALL` では動かないので、`--dangerously-bypass-approvals-and-sandbox` で流す。コンテナが sandbox。ネットワークは開いている (データの取得とモデルの API に必要)。

## Gemini で流す (Gemini eval)

Codex と同じ課題、同じ作業場所、同じ CPU とメモリの条件で、Gemini を流して比べる。中で動かす CLI は Antigravity CLI (`agy`) だが、評価の名前は「Gemini eval」にそろえる。Codex 用と同じ分析ライブラリの版 (rasterio 1.4.1 を含む) なので、違うのはモデルと CLI だけ。

| 固定するもの | 値 |
|---|---|
| イメージ | `geoai-skills-evals-gemini`。`agy` の版は `AGY_VERSION` で固定 (既定 1.3.5)。公式のインストーラは最新を入れ、`agy` は自己更新もするので、版が違うとビルドが失敗する。上げるときは `--build-arg AGY_VERSION=...` で意図して上げ、結果と一緒に版を記録する。root で入れるので、実行中の自己更新はできない |
| 認証 | OAuth (Google アカウント) か API キー。baseline とスキルありで同じにする。下を参照 |
| モデルと effort | OAuth: `gemini-3.8-flash-low` (effort はモデル名の末尾。3.6 Flash は一覧に無い)。API キー: `gemini-3.6-flash` と `--effort low`。`EVAL_MODEL`、`EVAL_EFFORT` で変える。一覧は `agy models` (認証方式で違う) |
| CPU、メモリ、プロセス数、権限、mount | Codex と同じ (上の表) |
| ログ | `--prompt` で、構造化ログ (stream-json) が標準出力に出る。ツール実行の各段階が見える |

```sh
docker build -f Dockerfile.evals.gemini -t geoai-skills-evals-gemini .

# 認証 (どちらか)
evals/run_gemini_docker.sh --login      # OAuth: 表示された URL でサインインし、認可コードを貼る。トークンは ~/.gemini-evals に保存
cp .env.example .env                     # API キー: 値を書く (.env は git に入れない)

python evals/prepare_workdir.py <rev> <作業場所> --task evals/tasks/tasks.md --number 9 \
  --template evals/prompts/agent-task.md --prompt-workdir /work > <指示文>
evals/run_gemini_docker.sh --prompt <指示文> <作業場所> > <ログ.jsonl>
```

`--auth oauth|api-key` で認証を選ぶ。省略すると、`~/.gemini-evals` にトークンがあれば OAuth、無ければ API キー。OAuth のときはキーを渡さない。API キーは、名前だけを読み (`GEMINI_API_KEY`、`GOOGLE_GENERATIVE_AI_API_KEY`。`.env` の、ほかの値は読まない)、`docker run -e GEMINI_API_KEY` で渡す。イメージ、`/work`、コマンドラインには入らない。ただし、エージェントはコンテナの中で、そのキーを環境変数として見られる。使用量の上限を付けたキーを使うこと。キーのプロジェクトに課金の残高が無いと `Error 402 (prepayment credits are depleted)` で止まる。

`~/.gemini-evals` に、OAuth のトークンが入る。普段の `~/.gemini` とは別。設定は、実行のたびに書き直す。`--dry-run` で、実行する `docker run` を表示する。

## なぜ `evals/` を渡さないか

rubric には答えが書いてある。エージェントが clone して、リポジトリの中を読むと、答えが見える。`prepare_workdir.py` は、`git archive` (`.gitattributes` の `evals/ export-ignore` を守る) で用意し、さらに `evals/` を自分で消す。属性が抜けても漏れない。maplibre-agent-skills は、モデルに SKILL.md だけをシステムプロンプトとして渡す方式 (promptfoo) なので、そもそもモデルが `evals/` を読めない。ここは、エージェントが作業場所を歩くので、作業場所から消す。

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
