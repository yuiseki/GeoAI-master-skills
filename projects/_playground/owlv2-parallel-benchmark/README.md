# OWLv2 推論のCPU並列化試走

パリ画像E2Eで保存した同じ水平ビューを用いて、OWLv2の逐次推論、2ワーカー、バッチ2を比較します。画像は再配布せず、元の実行環境から読みます。

環境変数 `HF_HOME` を使用可能なモデルキャッシュへ設定し、実行前に `google/owlv2-base-patch16-ensemble` を取得します。計測時のモデルリビジョンは `cfd3195ba4ea9592eec887ded089f4c08eff231d`、Python 3.13.3、torch 2.15.0+cpu、transformers 5.22.2、Pillow 13.0.0です。モデルの版と画像のハッシュは再実行時に照合してください。元のビューは `/Workspaces/tmp/playground-nl-e2e/imagery/work/artifacts/paris11-street-imagery/views` にあります。

各条件を**別々に、順番に**実行します。`MODE` は `sequential`、`workers2`、`batch2` のいずれかです。workers2は実行時に各ワーカーを2スレッドに設定します。

```sh
systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  env HF_HOME=/tmp/owlv2-bench-cache-X7bVlQfq OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false \
  uvx --index https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match \
  --with 'torch==2.15.0+cpu' --with torchvision --with 'transformers==5.22.2' --with 'pillow==13.0.0' \
  python projects/_playground/owlv2-parallel-benchmark/scripts/benchmark.py MODE \
  --views /Workspaces/tmp/playground-nl-e2e/imagery/work/artifacts/paris11-street-imagery/views
systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 -p CPUQuota=400% -- \
  python3 projects/_playground/owlv2-parallel-benchmark/scripts/benchmark.py compare
```

計測は既存のE2E全体ではなく、切出し済みビューのOWLv2検出のみです。各プロセスでキャッシュ済みモデルを読み込む時間を含み、初回ダウンロード・画像切出し・傾きや植生の解析・報告生成は含みません。cgroup v2の `memory.peak` は子プロセスを含みます。
