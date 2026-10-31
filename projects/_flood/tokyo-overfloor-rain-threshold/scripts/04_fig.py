"""Overfloor share by rain band, all years and each period (23 wards, pluvial), from outputs/blocks.json.

uvx --with matplotlib python scripts/04_fig.py
Writes outputs/overfloor_by_band.png.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "outputs"


def main():
    b = json.loads((OUT / "blocks.json").read_text())["B1"]
    series = [("all years", b["bands"], "#555555", "-"), ("1974-1996", b["bands_by_period"]["first"], "#1f77b4", "--"),
              ("1997-2019", b["bands_by_period"]["second"], "#d62728", "--")]
    labels = ["<30", "30-49", "50-69", ">=70"]
    fig, ax = plt.subplots(figsize=(6.4, 4.2), dpi=150)
    for name, bands, colour, ls in series:
        ax.plot(labels, [x["share"] for x in bands], marker="o", color=colour, ls=ls, label=name)
        for i, x in enumerate(bands):
            ax.annotate(f"{x['units']}u/{x['days']}d", (i, x["share"]), textcoords="offset points", xytext=(4, 4),
                        fontsize=7, color=colour)
    ax.set_xlabel("nearest Tokyo gauge, max hourly rain (mm/h)")
    ax.set_ylabel("overfloor / (overfloor + underfloor) buildings")
    ax.set_ylim(0, 0.75)
    ax.set_title("23 wards, pluvial flood records (units / disaster days)", fontsize=10)
    ax.legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT / "overfloor_by_band.png")


if __name__ == "__main__":
    main()
