import json
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def test_plot_writes_png_and_provenance():
    subprocess.run([sys.executable, PROJECT / "scripts" / "plot.py"], check=True)
    png = PROJECT / "outputs" / "shelter-tradeoff.png"
    metadata = json.loads((PROJECT / "outputs" / "shelter-tradeoff.json").read_text())
    assert png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert metadata["source_commit"] == "6880b32c097a7c65a6bd72a38682ce1dce1c9a2b"
    assert metadata["source_rows"] == 4
    assert metadata["font"]
    assert metadata["question"]
    assert metadata["axes"] == {
        "x": "浸水ランク合計の上限",
        "y": "400 m 以内の人口割合 (%)",
    }
