import json
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def test_plot_writes_png_and_provenance():
    subprocess.run([sys.executable, PROJECT / "scripts" / "plot.py"], check=True)
    png = PROJECT / "outputs" / "auc-by-split.png"
    metadata = json.loads((PROJECT / "outputs" / "auc-by-split.json").read_text())
    assert png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert metadata["source_commit"] == "6880b32c097a7c65a6bd72a38682ce1dce1c9a2b"
    assert metadata["source_rows"] == 9
    assert metadata["font"]
    assert metadata["question"]
    assert metadata["axes"] == {"x": "評価の分け方", "y": "AUC"}
