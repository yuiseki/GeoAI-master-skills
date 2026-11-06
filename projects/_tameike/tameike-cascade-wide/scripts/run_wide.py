"""B1 of EXPERIMENT_PLAN.md: tameike-cascade-breach's screen with the flow computed over each box widened by PAD
degrees on every side, and chains started only from ponds inside the original box.

  env -u GDAL_DATA -u PROJ_LIB -u PROJ_DATA systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 \
    -p CPUQuota=400% -- uvx --python 3.12 --with pyflwdir --with numpy --with rasterio --with pyproj --with scipy \
    --with duckdb --with matplotlib python -u scripts/run_wide.py

Writes outputs/<box>_ponds.csv, <box>_chains.csv, <box>_chain_lines.geojson, fig_chains_<box>.png and summary.csv.
DEM5A tiles missing from tameike-cascade-pairs' cache are fetched from GSI into the same cache.
"""

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT.parent / "tameike-cascade-breach/scripts"))
from run_breach import BOXES, rain_200, run_box, write  # noqa: E402

OUT = PROJECT / "outputs"
PAD = 0.04


def widened(box, pad=PAD):
    return (round(box[0] - pad, 4), round(box[1] - pad, 4), round(box[2] + pad, 4), round(box[3] + pad, 4))


def main():
    rain = rain_200()
    summary = []
    for key in sys.argv[1:] or list(BOXES):
        summary += [dict(r, flow_box=" ".join(map(str, widened(BOXES[key])))) for r in
                    run_box(key, rain, box=widened(BOXES[key]), start_box=BOXES[key], out=OUT, lines=True)]
    write(OUT / "summary.csv", summary)


if __name__ == "__main__":
    main()
