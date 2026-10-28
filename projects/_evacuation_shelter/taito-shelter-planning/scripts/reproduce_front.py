"""Recompute the pinned original shelter front and draw it with analysis-visualize."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[2]
SOURCE = ROOT / "projects/__exp/tokyo-town-types/tmp/source"
COMMIT = "6880b32c097a7c65a6bd72a38682ce1dce1c9a2b"
DRAW = ROOT / ".agents/skills/analysis-visualize/scripts/result_figures.py"


def build_front(front, weighted):
    ranks = [int(flood) for _, flood in front]
    if len(ranks) != len(set(ranks)):
        raise ValueError("duplicate flood rank")
    rows = []
    for covered, flood in sorted(front, key=lambda pair: pair[1]):
        point = (int(covered), int(flood))
        methods = ["ε 制約法"]
        if point in weighted:
            methods.append("重み付き和")
        rows.append({"x": point[1], "y": point[0], "methods": methods})
    for covered, flood in sorted(weighted - set(front), key=lambda pair: pair[1]):
        rows.append({"x": int(flood), "y": int(covered), "methods": ["重み付き和"], "front": False})
    return rows


def load_source(relative, name):
    spec = importlib.util.spec_from_file_location(name, SOURCE / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    revision = subprocess.check_output(["git", "-C", SOURCE, "rev-parse", "HEAD"], text=True).strip()
    if revision != COMMIT:
        raise RuntimeError(f"expected source commit {COMMIT}, got {revision}")
    sys.path.insert(0, str(SOURCE / "src"))
    from study_geoai import cover
    from study_geoai.db import connect

    original = load_source("src/012-B-epsilon-constraint/run.py", "original_epsilon")
    con = connect()
    pop, sets, flood, _, _ = original.step12a.instance(con)
    top = cover.solve_multi(sets, pop, flood, k=original.K)
    if top.get("status") != "Optimal":
        raise RuntimeError(f"top solve failed: {top.get('status')}")
    eps_points = []
    for epsilon in range(int(top["flood"]) + 1):
        answer = cover.solve_multi(sets, pop, flood, k=original.K, max_flood=epsilon)
        if answer.get("status") != "Optimal":
            raise RuntimeError(f"epsilon={epsilon}: {answer.get('status')}")
        eps_points.append((round(answer["covered"]), round(answer["flood"])))
    front = sorted(set(eps_points), key=lambda point: point[1])
    front = [point for point in front if not any(other[0] >= point[0] and other[1] < point[1] for other in front)]
    weighted = set()
    for weight in original.W_GRID:
        answer = cover.solve_multi(sets, pop, flood, k=original.K, w_flood=float(weight))
        if answer.get("status") != "Optimal":
            raise RuntimeError(f"weight={weight}: {answer.get('status')}")
        weighted.add((round(answer["covered"]), round(answer["flood"])))
    if len(front) != 34:
        raise RuntimeError(f"expected 34 Pareto points, got {len(front)}")
    data = {
        "kind": "pareto", "question": "浸水を抑えると、400 m 以内の人口はどう変わるか",
        "source": f"study-geoai-algo-py {COMMIT[:8]}; WorldPop 2025; KSJ A31a; OSM",
        "data_version": "WorldPop 2025; その他の版未確認; 2026-10-23再計算", "x_label": "13拠点の浸水ランクの和",
        "y_label": "400 m 以内の人口 (人)", "x_direction": "min", "y_direction": "max",
        "points": build_front(front, weighted), "total_population": float(pop.sum()),
    }
    output = PROJECT / "outputs"
    output.mkdir(exist_ok=True)
    input_path = output / "front-data.json"
    input_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    subprocess.run([sys.executable, DRAW, input_path, output / "shelter-front.png"], check=True)


if __name__ == "__main__":
    main()
