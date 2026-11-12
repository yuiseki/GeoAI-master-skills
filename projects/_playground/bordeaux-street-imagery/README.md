# bordeaux-street-imagery

Google の Geospatial Analytics Playground の例「Inspect leaning utility poles or grade road surface PCI condition」を、オープンな通りの画像 (Panoramax、キー不要) と公開のモデルで行う。スキルは `.agents/skills/street-imagery-inspection`。

- 報告: [report.md](report.md)
- 小さな表と図: `outputs/`。画像、切り出した画像、検出の表、学習したプローブ: `artifacts/_playground/bordeaux-street-imagery/`

## 再実行

```sh
CAP="systemd-run --user --scope -q -p MemoryMax=12G -p MemorySwapMax=0 -p CPUQuota=400% -E CUDA_VISIBLE_DEVICES=0 --"
PY="uvx -q --python 3.12 --with numpy --with scipy --with pandas --with pillow --with scikit-image --with scikit-learn \
    --with torch --with torchvision --with open_clip_torch --with transformers --with h3 --with matplotlib"
cd projects/_playground/bordeaux-street-imagery
A=../../../artifacts/_playground/bordeaux-street-imagery
# RDD2022 のチェコと米国を、全体の zip から範囲指定で取り出す (remotezip)
mkdir -p $A/rdd2022 && (cd $A/rdd2022 && uvx -q --with remotezip python -c "
from remotezip import RemoteZip
with RemoteZip('https://ndownloader.figshare.com/files/38030910') as z:
    z.extract('RDD2022/Czech.zip', '.'); z.extract('RDD2022/United_States.zip', '.')")
S=../../../.agents/skills/street-imagery-inspection/scripts
$CAP $PY python $S/surface_damage.py train $A/rdd2022/RDD2022/Czech.zip $A/damage_probe --device cuda
$CAP $PY python $S/surface_damage.py evaluate $A/damage_probe/probe.npz $A/rdd2022/RDD2022/United_States.zip \
    $A/damage_probe/eval_united_states.json --device cuda
$CAP $PY python scripts/run.py fetch roadviews poles damage material osm osmpoles aggregate review_sample maps
```

- GPU が無ければ `CUDA_VISIBLE_DEVICES` を外す (CPU で流れるが、柱の検出に数時間かかる)。
- fetch は Panoramax の API で範囲の全ての画像を数える (1 区画に 1 分ほど)。同じ種でも、範囲に画像が足されると標本が変わる。2026-11-12 の取得では 3,982 枚。画像の id とハッシュは `artifacts/.../panoramax/manifest.csv`。
- review_*.csv の判定は、一覧の画像を見て付けたもの (誰が見たかは review_summary.json)。流し直しても判定は作られない。
- RDD2022 の zip の sha256: Czech `94c65a4e6cfed187b193ba967f0a2b16bd4287dfe313d0962f3711afce75bf1d`。
