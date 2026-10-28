"""Re-run the pinned national PCA and climate-type analyses into this project.

uvx --with duckdb --with numpy --with pandas --with pyarrow --with rasterio \
  --with scikit-learn --with scipy --with matplotlib \
  python projects/__exp/japan-climate-analysis/scripts/reproduce_national.py

Use --source to point to a separate clone of study-geoai-algo-py at the pinned commit.
The source reads FAO FERSPAS COGs and caches downloaded windows in /tmp/study-geoai.
"""

import argparse
import contextlib
import importlib.util
import io
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[2]
DEFAULT_SOURCE = ROOT / "projects/__exp/tokyo-town-types/tmp/source"
SOURCE_COMMIT = "6880b32c097a7c65a6bd72a38682ce1dce1c9a2b"


def check_source_revision(source):
    actual = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if actual != SOURCE_COMMIT:
        raise RuntimeError(f"expected source commit {SOURCE_COMMIT}, got {actual}")


def run_step(source, output, relative_script, figure_name, log_name):
    script = source / "src" / relative_script
    spec = importlib.util.spec_from_file_location(relative_script.parent.name.replace("-", "_"), script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUT = output
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        module.main()
    figure = output / figure_name
    if not figure.is_file():
        raise RuntimeError(f"missing expected figure: {figure}")
    (output / log_name).write_text(buffer.getvalue(), encoding="utf-8")
    print(f"saved {figure_name} and {log_name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()
    source = args.source.resolve()
    check_source_revision(source)
    sys.path.insert(0, str(source / "src"))
    output = PROJECT / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    run_step(source, output, Path("006-C-pca-climate/run.py"), "pc-maps.png", "national-pca.log")
    run_step(source, output, Path("005-E-climate-types/run.py"), "types.png", "national-types.log")


if __name__ == "__main__":
    main()
