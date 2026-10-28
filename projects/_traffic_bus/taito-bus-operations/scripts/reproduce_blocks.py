"""Recompute the pinned original bus blocks and draw them with analysis-visualize."""

import json
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[2]
SOURCE = ROOT / "projects/__exp/tokyo-town-types/tmp/source"
COMMIT = "6880b32c097a7c65a6bd72a38682ce1dce1c9a2b"
DRAW = ROOT / ".agents/skills/analysis-visualize/scripts/result_figures.py"


def intervals(trips, blocks):
    used = [int(index) for block in blocks for index in block]
    if len(used) != len(set(used)):
        raise ValueError("duplicate trip in blocks")
    if set(used) != set(range(len(trips.start))):
        raise ValueError("missing trip in blocks")
    return [
        {"group": f"車両{number}", "start": int(trips.start[index]),
         "end": int(trips.end[index]), "kind": "運行"}
        for number, block in enumerate(blocks, 1) for index in block
    ]


def main():
    revision = subprocess.check_output(["git", "-C", SOURCE, "rev-parse", "HEAD"], text=True).strip()
    if revision != COMMIT:
        raise RuntimeError(f"expected source commit {COMMIT}, got {revision}")
    sys.path.insert(0, str(SOURCE / "src"))
    from study_geoai import schedule
    from study_geoai.db import connect

    con = connect()
    trips = schedule.gtfs_trips(con, "megurin", ["平日"])
    arcs = schedule.connections(trips, layover=3 * 60, speed_kmh=15.0)
    answer = schedule.min_fleet_cpsat(trips, arcs, second_stage=True)
    if answer["status"] != "OPTIMAL" or answer["vehicles"] != 17:
        raise RuntimeError(f"unexpected schedule: {answer['status']}, {answer['vehicles']} vehicles")
    blocks = sorted(answer["blocks"], key=lambda block: trips.start[block[0]])
    data = {
        "kind": "schedule", "question": "めぐりん171便を17台で回す割当",
        "source": f"study-geoai-algo-py {COMMIT[:8]}; めぐりん GTFS-JP",
        "data_version": "公開GTFSの版未確認; 2026-10-23再計算", "x_label": "時刻",
        "y_label": "車両", "time_unit": "seconds", "intervals": intervals(trips, blocks),
    }
    output = PROJECT / "outputs"
    output.mkdir(exist_ok=True)
    input_path = output / "blocks-data.json"
    input_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    subprocess.run([sys.executable, DRAW, input_path, output / "blocks-megurin.png"], check=True)


if __name__ == "__main__":
    main()
