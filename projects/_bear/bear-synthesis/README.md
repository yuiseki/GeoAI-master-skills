# bear-synthesis

`projects/_bear/` の 9 プロジェクトの総括。何が予測でき、何ができなかったかを [report.md](report.md) にまとめた。新しくデータは読まず、各プロジェクトの出力を並べ直している。

図 2 (B_env に足したものの差) だけは、各プロジェクトの JSON から差と区間を読んで描いた。コマンドはリポジトリの直下から流す。

```sh
uvx --with matplotlib --with pandas python projects/_bear/bear-synthesis/scripts/added_predictors.py \
  projects/_bear projects/_bear/bear-synthesis/outputs
uvx --with pytest --with pandas python -m pytest -q projects/_bear/bear-synthesis/scripts
```
