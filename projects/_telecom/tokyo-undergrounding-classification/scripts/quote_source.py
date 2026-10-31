"""Quote, from the pinned source case study, the values the report uses that source-values.csv does not hold.

The values are not typed in: each phrase is looked up in the source README at the pinned commit, and the line that
holds it is written to outputs/source-quotes.json. A phrase the README does not hold stops the script.

uv run python scripts/quote_source.py
"""

import json
import urllib.request
from pathlib import Path

OUTPUT = Path(__file__).resolve().parents[1] / "outputs"
COMMIT = "6880b32c097a7c65a6bd72a38682ce1dce1c9a2b"
PATH = "case-studies/003-undergrounding/README.md"
URL = f"https://raw.githubusercontent.com/yuiseki/study-geoai-algo-py/{COMMIT}/{PATH}"
PHRASES = ["AUC は 0.849 から 0.988 に跳ねる", "isotonic の ECE は 0.005 以下を保った"]


def quote(text, phrases):
    """{phrase: the README line that holds it}; a phrase that is not there raises."""
    lines = text.splitlines()
    out = {}
    for phrase in phrases:
        found = [line.strip() for line in lines if phrase in line]
        if not found:
            raise ValueError(f"the source does not say: {phrase}")
        out[phrase] = found[0]
    return out


def main():
    with urllib.request.urlopen(URL, timeout=60) as response:
        text = response.read().decode("utf-8")
    record = {"source": f"study-geoai-algo-py@{COMMIT}/{PATH}", "quotes": quote(text, PHRASES)}
    (OUTPUT / "source-quotes.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
