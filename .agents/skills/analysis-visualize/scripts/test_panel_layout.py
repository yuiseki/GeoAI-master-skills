"""uvx --with numpy --with matplotlib --with pillow --with pytest pytest test_panel_layout.py"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from PIL import Image  # noqa: E402

import panel_layout as pl  # noqa: E402

VIEW = (0.0, 0.0, 2000.0, 1000.0)     # x0, y0, x1, y1 in metres: twice as wide as tall


def test_the_map_size_is_fixed_first_and_the_decorations_are_added_around_it():
    p = pl.plan(VIEW, 1.0, map_h_in=3.0, left=0.2, right=1.5, bottom=0.4, top=0.5)
    assert p["map"][2:] == pytest.approx((6.0, 3.0))           # width from the extent's aspect
    assert p["fig"] == pytest.approx((0.2 + 6.0 + 1.5, 0.4 + 3.0 + 0.5))
    # longitude and latitude: y / x display ratio stretches the height, so the same map height is narrower
    q = pl.plan(VIEW, 2.0, map_h_in=3.0)
    assert q["map"][2] == pytest.approx(3.0)


def test_a_reserved_colorbar_takes_the_same_room_as_a_shown_one():
    shown = pl.plan(VIEW, 1.0, 3.0, cbar="shown")
    hidden = pl.plan(VIEW, 1.0, 3.0, cbar="reserved")
    none = pl.plan(VIEW, 1.0, 3.0)
    assert shown["fig"] == hidden["fig"] and shown["map"] == hidden["map"] and shown["cbar"] == hidden["cbar"]
    assert none["fig"][0] < shown["fig"][0] and none["map"] == shown["map"]
    # the colorbar runs exactly along the map's height
    assert shown["cbar"][1] == shown["map"][1] and shown["cbar"][3] == shown["map"][3]


def draw(tmp_path, name, legend_labels, cbar, dpi=100, right=3.0):
    fig, ax, cax = pl.map_frame(VIEW, 1.0, 2.0, right=right, cbar=cbar, dpi=dpi)
    ax.plot([0, 2000], [0, 1000], label=legend_labels[0])
    for lab in legend_labels[1:]:
        ax.plot([], [], label=lab)
    leg = ax.legend(loc="upper left", bbox_to_anchor=(pl.right_anchor(fig), 1), frameon=False)
    if cbar == "shown":
        im = ax.imshow(np.arange(4).reshape(2, 2), extent=(0, 2000, 0, 1000))
        fig.colorbar(im, cax=cax)
    out = tmp_path / f"{name}.png"
    rec = pl.save(fig, out, [leg])
    plt.close(fig)
    return out, rec


def test_saved_panels_keep_the_planned_canvas_and_map_in_pixels(tmp_path):
    png, rec = draw(tmp_path, "a", ["short"], "shown")
    p = pl.plan(VIEW, 1.0, 2.0, right=3.0, cbar="shown")
    w, h = Image.open(png).size
    assert (w, h) == tuple(round(x * 100) for x in p["fig"]) == tuple(rec["canvas_px"])
    x0, y0, x1, y1 = rec["map_px"]
    assert (x1 - x0, y1 - y0) == (200 * 2, 200)                 # 4 in x 2 in at 100 dpi, aspect kept
    cx0, cy0, cx1, cy1 = rec["cbar_px"]
    assert (cy0, cy1) == (y0, y1)                               # colorbar ends meet the map's top and bottom


def test_two_panels_with_different_legends_keep_the_same_map_rectangle(tmp_path):
    _, a = draw(tmp_path, "a", ["short"], "shown")
    _, b = draw(tmp_path, "b", ["a much longer legend entry", "another"], "reserved")
    assert a["canvas_px"] == b["canvas_px"] and a["map_px"] == b["map_px"]
    assert pl.check_panels([a, b]) == []


def test_a_tight_bounding_box_moves_the_map_when_the_legends_differ(tmp_path):
    """Why save() does not use bbox_inches="tight": each panel would be cropped to its own decorations."""
    sizes = []
    for labs in (["short"], ["a much longer legend entry"]):
        fig, ax, _ = pl.map_frame(VIEW, 1.0, 2.0, right=3.0)
        ax.plot([0, 1], [0, 1], label=labs[0])
        ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1))
        out = tmp_path / f"t{len(sizes)}.png"
        fig.savefig(out, dpi=100, bbox_inches="tight")
        plt.close(fig)
        sizes.append(Image.open(out).size)
    assert sizes[0] != sizes[1]


def test_the_reserved_colorbar_space_is_blank(tmp_path):
    png, rec = draw(tmp_path, "r", ["x"], "reserved")
    cx0, cy0, cx1, cy1 = rec["cbar_px"]
    a = np.asarray(Image.open(png).convert("RGB"))[cy0:cy1, cx0:cx1]
    assert (a == 255).all()


def test_a_legend_that_does_not_fit_the_margin_stops_the_save(tmp_path):
    with pytest.raises(SystemExit, match="outside the canvas"):
        draw(tmp_path, "o", ["a legend entry far too long for a narrow right margin of the figure"], None,
             right=0.5)


def test_check_panels_names_what_differs():
    base = {"canvas_px": [800, 400], "map_px": [20, 50, 420, 250], "cbar_px": [440, 50, 458, 250],
            "cbar": "shown", "view": list(VIEW), "dpi": 100}
    assert pl.check_panels([base, dict(base, cbar="reserved")]) == []
    probs = pl.check_panels([base, dict(base, view=[0, 0, 1000, 1000]), dict(base, map_px=[20, 50, 421, 250]),
                             dict(base, cbar=None, cbar_px=None)])
    assert any("view" in p for p in probs) and any("map_px" in p for p in probs) and any("cbar" in p for p in probs)
    # a shown colorbar shorter than its map
    assert any("colorbar" in p for p in pl.check_panels([dict(base, cbar_px=[440, 60, 458, 250])]))


def test_assemble_places_panels_without_scaling_and_aligns_the_maps(tmp_path):
    pa, a = draw(tmp_path, "a", ["short"], "shown")
    pb, b = draw(tmp_path, "b", ["longer legend"], "reserved")
    out = tmp_path / "ab.png"
    rec = pl.assemble([pa, pb], [a, b], out, cols=2, gap_px=10)
    w, h = a["canvas_px"]
    assert Image.open(out).size == (2 * w + 10, h)
    assert rec["panels"][1]["map_px"] == [a["map_px"][0] + w + 10, a["map_px"][1], a["map_px"][2] + w + 10,
                                          a["map_px"][3]]
    # the right half is panel b, pixel for pixel
    big = np.asarray(Image.open(out).convert("RGB"))
    assert (big[:, w + 10:] == np.asarray(Image.open(pb).convert("RGB"))).all()


def test_assemble_refuses_panels_whose_maps_differ(tmp_path):
    pa, a = draw(tmp_path, "a", ["x"], "shown")
    fig, ax, _ = pl.map_frame(VIEW, 1.0, 2.5)
    pc = tmp_path / "c.png"
    c = pl.save(fig, pc, [])
    plt.close(fig)
    with pytest.raises(SystemExit, match="map_px|canvas"):
        pl.assemble([pa, pc], [a, c], tmp_path / "x.png", cols=2)


def test_the_command_line_checks_and_assembles_from_the_json_records(tmp_path):
    pa, a = draw(tmp_path, "a", ["x"], "shown")
    pb, b = draw(tmp_path, "b", ["y"], "reserved")
    for p, r in ((pa, a), (pb, b)):
        p.with_suffix(".json").write_text(json.dumps({"layout": r}))
    run = lambda *x: subprocess.run([sys.executable, str(HERE / "panel_layout.py"), *map(str, x)],  # noqa: E731
                                    capture_output=True, text=True)
    r = run("check", pa.with_suffix(".json"), pb.with_suffix(".json"))
    assert r.returncode == 0, r.stderr
    r = run("assemble", "--cols", 2, "--out", tmp_path / "ab.png", pa, pb)
    assert r.returncode == 0, r.stderr
    assert json.loads((tmp_path / "ab.json").read_text())["panels"][1]["source"].endswith("b.png")


def test_a_fractional_canvas_is_rounded_up_to_whole_pixels(tmp_path):
    """3.65 in at 150 dpi is 547.5 px; matplotlib would save 547 and the record would say 548."""
    fig, ax, _ = pl.map_frame(VIEW, 1.0, 1.0, bottom=0.45, top=0.2, dpi=150)
    rec = pl.save(fig, tmp_path / "f.png", [])
    plt.close(fig)
    assert list(Image.open(tmp_path / "f.png").size) == rec["canvas_px"]
