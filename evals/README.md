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
| `tasks/<suite>/<id>.md` | 1 ファイル 1 課題。YAML frontmatter に `task_id`、難易度、状態、タイトルなどを記録 |
| `tasks/<suite>/rubrics/<id>.md` | 同じ `task_id` を持つ採点基準。`visibility: evaluator-only`。作業場所には渡さない |
| `tasks/foundational/` | 教科書的な課題 1〜11。1〜8 は開発に使った汚染済み、9〜11 は保留 |
| `tasks/small/` | 小さい課題 12〜17、19〜22、27〜29。`28-truth.csv` は採点用の正解データ |
| `tasks/medium/` | 中難易度課題。分析判断を絞り、現地確認候補を作る |
| `tasks/hard/` | 高難易度の正式課題 30〜44 |
| `tasks/raster/`, `tasks/areal/`, `tasks/interpolation/`, `tasks/observation/`, `tasks/experiment/` | 手法・落とし穴別の課題 18、23〜26 |
| `tasks/world-visualize/` | 世界規模の可視化候補 W1〜W7 |
| `curriculum/task-cards/` | 提案・レビュー履歴。正式課題と混同しない |
| `curriculum/incoming/` | 外部から受け取った候補の原文。検証・採用を意味しない |
| `curriculum/reviews/` | 候補の採否と修正理由。元の pilot 数値は再検証まで答えにしない |
| `prompts/agent-task.md` | エージェントへの指示の雛形 (`{{WORKDIR}}`、`{{SHA}}`、`{{TASK}}`) |
| `run_gemini_docker.sh` | 同じ条件で、Gemini を流す (中で使う CLI は Antigravity CLI の `agy`)。イメージは `Dockerfile.gemini` |
| `run_codex_docker.sh` | 作業場所を Docker (`Dockerfile.codex`) に閉じ込めて Codex を流す。CPU、メモリ、プロセス数の上限はここで強制する (テスト付き) |
| `prepare_workdir.py` | エージェントの作業場所を、`evals/` なしで用意する (テスト付き) |
| `score_points.py` | 予測の点と正解の点を、半径 (m) の中で 1 対 1 に組にして、適合率、再現率、F1 を出す。課題 28 (アンダーパス) の採点に使う (テスト付き) |
| `tasks/small/28-truth.csv` | 課題 28 の正解 (23 区の 99 点)。作業場所は `--hide mlit-underpass` で作り、データカードを消す |
| `results/agent-runs.md` | これまでの実行の一覧 (成果物の本体は、リポジトリの外) |
| `results/overview.md` | 設計、結果、直したこと、残った隙のまとめ |

## 評価の流れ

1. エージェントの作業場所を用意する。エージェントに clone させない。clone すると `evals/` が入る。

   ```sh
   python evals/prepare_workdir.py <rev> <作業場所> --task evals/tasks/foundational/09.md \
     --template evals/prompts/agent-task.md > <指示文>
   ```

   スキルなしの基準 (baseline) は `--baseline` を付ける。作業場所は `projects/` だけの空のディレクトリになる。
   スキルありの作業場所には、リポジトリの `projects/sample-project/` と `artifacts/sample-project/` (構成の例の README だけ) も入る。採点では、この 2 つを成果物として数えない。エージェントが `artifacts/<名前>/` に置いた生成物は、報告から指されていれば見る。

2. 指示文を、エージェント (Codex や Claude など) に渡す。作業場所の外、特に `evals/` を含む元のリポジトリを読ませない (指示文に書いてある)。
3. 成果物を回収し、課題と同じ番号の `rubrics/<id>.md` で採点する。同じ課題を 2 回流し、再現を確かめる (コピーして流し直し、出力を比べる)。
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
docker build -f evals/Dockerfile.codex -t geoai-master-skills-evals-codex .

# 初回だけ: ログイン (認証は ~/.codex-evals に保存。イメージには入れない。普段の ~/.codex とは別)
evals/run_codex_docker.sh --login

# 作業場所と、/work を書いた指示文を作って流す (baseline は --baseline を付けるだけ)
python evals/prepare_workdir.py <rev> <作業場所> --task evals/tasks/foundational/09.md \
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
docker build -f evals/Dockerfile.gemini -t geoai-master-skills-evals-gemini .

# 認証 (どちらか)
evals/run_gemini_docker.sh --login      # OAuth: 表示された URL でサインインし、認可コードを貼る。トークンは ~/.gemini-evals に保存
cp .env.example .env                     # API キー: 値を書く (.env は git に入れない)

python evals/prepare_workdir.py <rev> <作業場所> --task evals/tasks/foundational/09.md \
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
docker build -f evals/Dockerfile.opencode -t geoai-master-skills-evals-opencode .

python evals/prepare_workdir.py <rev> <作業場所> --task evals/tasks/foundational/09.md \
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

## 長い実行のハーネス

ISUCON2026 を完全自律のエージェントで解いた記録 ([準備編](https://zenn.dev/luvtechno/articles/isucon2026-preparation)、[当日編](https://zenn.dev/luvtechno/articles/isucon2026-competition-day)、2026-11) から、ここに当てはまるものを取り込んだ。その記録では、いちばん手間がかかったのは評価環境の側で (issue 927 件のうち 409 件)、評価環境の不備がエージェントの判断や構成の比較を何度も誤らせていた。

取り込んだもの:

- 時間を知らせる。打ち切る実行では `prepare_workdir.py --time-limit MIN` を必ず付ける。指示文に、上限、`date` で時計を見ること、半分の時間までに報告の初版を書くことが入る。2026-11-12 のパリの画像の実行は、これを付け忘れて 120 分で打ち切られ、報告が 1 行も残らなかった (エージェントが時計を見たのは 1 回だけ)。その記録でも、時間を知らないエージェントは時計を 2 回しか見ず、作業を残して止まった。「戻る先を常に作る」(デプロイの前に commit を強制した) と同じ考えで、報告の初版を戻る先にする。
- モデルが入れ替わっていないか確かめる。安全のための仕組みで、実行の途中にモデルが別のものに切り替わることがある (その記録で 3 回)。`trigger.py` の `model_switched(log, "claude-sonnet-5-5")` が真の実行は、頼んだモデルの測定に数えない。
- トークンは result の行から取る。Claude Code の stream-json は、1 つのメッセージを内容ごとに複数の行に書き、同じ id と usage を繰り返す。行の usage の出力トークンは書き始めの値で、合計には使えない (2026-11-12 の東京の実行で、行から 1,143、result では 50,254)。打ち切られた実行には result の行が無い。
- 評価環境と普段の環境の違いを、構成を比べる前に確かめる。その記録では、ベンチマーカーの fd の上限 (1024 のまま) をエージェントがアプリの限界と読み、本番より多くの情報を返すポータルで練習していた。ここでは、エージェントのシステムプロンプトが使えと言う `rg` が、評価のイメージに入っていなかった (2026-11-13 に追加)。
- 評価の課題は狭く、短くする。1 つの課題では 1 つのこと (1 つの指標、狭い範囲、決めた枚数や件数) を、20 分ほどで確かめる。広い課題は、確かめたいことが混ざり、1 回に 1〜2 時間かかり、反復できない。2026-11-12 のパリの画像の課題 (4 つの項目、11 区の全体) は、120 分で報告が出ず、どの段が足りなかったのかも分けられなかった。2026-11-13 に、ヴォルテール大通りの 200 m、30 枚、植生だけ、20 分に絞った。
- 1 回の差を改善と呼ばない。同じ構成を測り直したばらつきで説明できない差だけを数える (その記録では、同じ構成の 12 回が 474,987〜629,638 点に散った)。

取り込まなかったもの (理由):

- 時刻や頭打ちで差し戻す Stop フック、監査役のサブエージェント、止まったターンに continue を送る見張り。どれも Claude Code の対話のセッションの仕組みで、ここでは 4 つの CLI を同じ条件で比べる。片方にだけ足すと、比べているものがエージェントでなくハーネスになる。なお、その記録では、Stop フックが同じ理由で 9 回差し戻し、見張りが入力待ちを止まったと読んで continue を約 370 回送るという失敗も出た。
- 手順を細かく決める重いハーネス。その記録では、4 つの段階、探索の記録、観測の要約を足した構成が、ほぼ素の構成に 1 時間で抜かれた (記録に出力の 51% を使い、大きな書き直しを選ばなくなった)。ここでも、スキルの後の段の reference を開かずに最後まで行く実行があった。スキルを足すときは、素のエージェントが実際に落ちた場面に 1 つずつ足し、baseline と比べて確かめる。
