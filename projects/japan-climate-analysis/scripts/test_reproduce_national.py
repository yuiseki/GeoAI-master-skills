"""uvx --with pytest pytest projects/japan-climate-analysis/scripts/test_reproduce_national.py"""

from pathlib import Path

import pytest

from reproduce_national import check_source_revision, run_step


def test_rejects_unpinned_source(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "reproduce_national.subprocess.check_output",
        lambda *args, **kwargs: "wrong-commit\n",
    )
    with pytest.raises(RuntimeError, match="expected source commit"):
        check_source_revision(tmp_path)


def test_step_saves_log_and_figure(tmp_path):
    source = tmp_path / "source"
    script = source / "src" / "example" / "run.py"
    script.parent.mkdir(parents=True)
    script.write_text(
        "from pathlib import Path\n"
        "OUT = Path('unused')\n"
        "def main():\n"
        "    OUT.mkdir(parents=True, exist_ok=True)\n"
        "    (OUT / 'figure.png').write_bytes(b'PNG')\n"
        "    print('3,845 cells')\n",
        encoding="utf-8",
    )
    output = tmp_path / "output"
    run_step(source, output, Path("example/run.py"), "figure.png", "example.log")
    assert (output / "figure.png").read_bytes() == b"PNG"
    assert (output / "example.log").read_text(encoding="utf-8") == "3,845 cells\n"


def test_step_requires_figure(tmp_path):
    source = tmp_path / "source"
    script = source / "src" / "example" / "run.py"
    script.parent.mkdir(parents=True)
    script.write_text("def main():\n    print('no figure')\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="missing expected figure"):
        run_step(source, tmp_path / "output", Path("example/run.py"), "figure.png", "example.log")
