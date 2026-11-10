"""The eval images are built from pinned inputs only, so a rebuild later gives the same toolchain and the agents
are compared on the same one: the base images by digest, the CLI by version, every Python package by exact
version from evals/requirements-evals.lock (no >= or bare names). Only the Debian packages come from apt."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
CLI = {"qoder": "ARG QODER_VERSION=1.1.86", "claude": "ARG CLAUDE_VERSION=2.1.321"}
# Not yet Dockerfile.evals.gemini: the agy installer serves only the latest build, and its download URL carries a
# build id that is not known for the 1.3.5 the Gemini evals ran on.


@pytest.mark.parametrize("agent", sorted(CLI))
def test_the_image_is_built_from_pinned_inputs_only(agent):
    d = (ROOT / f"Dockerfile.evals.{agent}").read_text()
    froms = [l for l in d.splitlines() if l.startswith(("FROM", "COPY --from"))]
    assert froms and all("@sha256:" in l for l in froms), froms
    assert CLI[agent] in d
    assert "uv pip install --no-cache --no-deps -r /tmp/requirements-evals.lock" in d
    assert ">=" not in d, [l for l in d.splitlines() if ">=" in l]


def test_the_lock_names_exact_versions():
    lock = [l for l in (ROOT / "evals" / "requirements-evals.lock").read_text().splitlines()
            if l.strip() and not l.startswith("#")]
    assert lock and all(re.fullmatch(r"[A-Za-z0-9_.-]+==[A-Za-z0-9_.+-]+", l) for l in lock), lock
    assert "duckdb==1.5.6" in lock and "rasterio==1.4.1" in lock
