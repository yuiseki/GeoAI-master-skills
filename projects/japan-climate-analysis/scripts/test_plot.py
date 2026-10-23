import json
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def test_plot_writes_png_and_provenance():
    subprocess.run([sys.executable, PROJECT / "scripts" / "plot.py"], check=True)
    png = PROJECT / "outputs" / "interval-coverage.png"
    metadata = json.loads((PROJECT / "outputs" / "interval-coverage.json").read_text())
    assert png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert metadata["source_commit"] == "6880b32c097a7c65a6bd72a38682ce1dce1c9a2b"
    assert metadata["source_rows"] == 6
    assert metadata["font"]
    assert metadata["question"]
    assert metadata["axes"] == {"x": "予測区間の作り方", "y": "試験期間の被覆率 (%)"}
