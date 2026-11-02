# 課題カタログ

課題は `suite/<id>.md`、採点基準は `suite/rubrics/<id>.md` に置きます。1 ファイルにつき 1 課題です。課題と採点基準は YAML frontmatter の `task_id` で対応し、採点基準には `visibility: "evaluator-only"` を付けます。

## 区分

| ディレクトリ | 内容 |
|---|---|
| `foundational/` | 教科書的な課題 1〜11。状態は frontmatter の `status` を参照 |
| `small/` | 小さい課題 12〜17、19〜22、27〜29。課題 28 の正解 CSV もここに置く |
| `raster/`, `areal/`, `interpolation/`, `observation/`, `experiment/` | 特定の分析課題 18、23〜26 |
| `medium/` | 中難易度課題 1〜3 |
| `hard/` | 高難易度の正式課題 30〜44 |
| `world-visualize/` | 世界規模の可視化候補 W1〜W7。`status: candidate` は正式課題化を意味しない |

## frontmatter

課題ファイルには `task_id`、`kind: "task"`、`suite`、`difficulty`、`status`、`number`、`title` を記録します。採点基準には同じ `task_id` と `kind: "rubric"`、`visibility: "evaluator-only"` を記録します。値はスクリプトで扱いやすい YAML の文字列スカラーに統一します。

## 1件を作業場所へ渡す

```sh
python evals/prepare_workdir.py <rev> <作業場所> \
  --task evals/tasks/hard/39.md \
  --template evals/prompts/agent-task.md > <指示文>
```

`prepare_workdir.py` は frontmatter を除いた本文だけを渡します。過去の一括ファイルを使う場合の `--number` は互換用として残していますが、新しい課題では個別ファイルを使います。
