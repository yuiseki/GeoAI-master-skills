"""Directed, turn-aware routes on a small road graph: one-way streets, banned turns, U-turns, and travel time.

This is not a routing engine. It is a reference to check what a graph built without directions, turns or
speeds gets wrong, on a study area of up to some tens of thousands of edges.

Edges are dicts: id, u, v, length_m, class, oneway, maxspeed (OSM-style text). arcs_for turns them into arcs
(directed edges) for a mode:
    drive  respects oneway (yes, true, 1: u -> v; -1, reverse: v -> u); no footway, steps, path, pedestrian,
           cycleway, bridleway, track
    bike   respects oneway; no motorway, motorway_link, steps
    walk   ignores oneway; no motorway, motorway_link
The class lists are assumptions to state, not facts about every country's law.

travel_times sets time_s = length_m / speed on each arc. A speed comes from maxspeed (km/h, or mph converted)
or, only when given, from assumed_kmh by class; arcs with neither stop the run, so a missing speed never
silently becomes a number. The counts of tagged and assumed arcs are returned for the report.

route runs Dijkstra over arcs (the state is the arc just used), so a banned turn (from edge, via node, to
edge) and a U-turn (leaving a node by the edge just arrived on) can be refused. Unreachable is infinite.

Usage (as a module):
    arcs = arcs_for(edges, "drive"); travel_times(arcs, assumed_kmh={"residential": 20})
    route(arcs, "A", "B", weight="time_s", restrictions=[("e1", "n5", "e2")])
"""

import heapq
import math
import re

EXCLUDE = {
    "drive": {"footway", "steps", "path", "pedestrian", "cycleway", "bridleway", "track"},
    "bike": {"motorway", "motorway_link", "steps"},
    "walk": {"motorway", "motorway_link"},
}
FORWARD = {"yes", "true", "1"}
BACKWARD = {"-1", "reverse"}
MPH = 1.609344


def parse_speed(text):
    """km/h from an OSM-style maxspeed ('50', '50 km/h', '30 mph'); None for anything else."""
    if text is None:
        return None
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(km/h|kmh|kph|mph)?\s*", str(text).lower())
    if not m:
        return None
    v = float(m.group(1))
    return v * MPH if m.group(2) == "mph" else v


def arcs_for(edges, mode, respect_oneway=True):
    if mode not in EXCLUDE:
        raise ValueError(f"mode must be one of {sorted(EXCLUDE)}")
    arcs = []
    for e in edges:
        if e.get("class") in EXCLUDE[mode]:
            continue
        ow = str(e.get("oneway") or "no").lower()
        directed = respect_oneway and mode != "walk"
        ends = []
        if not directed or ow not in BACKWARD:
            ends.append((e["u"], e["v"]))
        if not directed or ow not in FORWARD:
            ends.append((e["v"], e["u"]))
        for tail, head in ends:
            arcs.append({"edge": e["id"], "tail": tail, "head": head, "length_m": float(e["length_m"]),
                         "class": e.get("class"), "maxspeed": e.get("maxspeed")})
    return arcs


def travel_times(arcs, assumed_kmh=None):
    counts = {"tagged": 0, "assumed": 0}
    missing = []
    for a in arcs:
        v = parse_speed(a.get("maxspeed"))
        src = "tagged"
        if v is None and assumed_kmh and a.get("class") in assumed_kmh:
            v, src = float(assumed_kmh[a["class"]]), "assumed"
        if v is None or v <= 0:
            missing.append(a)
            continue
        a["speed_kmh"], a["speed_source"] = v, src
        a["time_s"] = a["length_m"] / (v / 3.6)
        counts[src] += 1
    if missing:
        classes = sorted({str(a.get("class")) for a in missing})
        raise ValueError(f"{len(missing)} arcs have no speed and no assumed speed for their class: {classes}")
    return counts


def route(arcs, origin, destination, weight="length_m", restrictions=(), u_turns=False):
    """Least-cost route from origin to destination node; cost is inf and nodes empty when unreachable."""
    if origin == destination:
        return {"cost": 0.0, "nodes": [origin], "edges": []}
    banned = set(restrictions)
    out = {}
    for i, a in enumerate(arcs):
        if weight not in a:
            raise ValueError(f"arc {a['edge']} has no {weight}")
        out.setdefault(a["tail"], []).append(i)
    best = {}
    prev = {}
    heap = []
    for i in out.get(origin, []):
        best[i] = arcs[i][weight]
        heapq.heappush(heap, (best[i], i))
    while heap:
        c, i = heapq.heappop(heap)
        if c > best.get(i, math.inf):
            continue
        a = arcs[i]
        if a["head"] == destination:
            path = [i]
            while path[-1] in prev:
                path.append(prev[path[-1]])
            path.reverse()
            return {"cost": c, "nodes": [origin] + [arcs[j]["head"] for j in path],
                    "edges": [arcs[j]["edge"] for j in path]}
        for j in out.get(a["head"], []):
            b = arcs[j]
            if (a["edge"], a["head"], b["edge"]) in banned:
                continue
            if not u_turns and b["edge"] == a["edge"] and b["head"] == a["tail"]:
                continue
            nc = c + b[weight]
            if nc < best.get(j, math.inf):
                best[j], prev[j] = nc, i
                heapq.heappush(heap, (nc, j))
    return {"cost": math.inf, "nodes": [], "edges": []}


def snap(points, nodes, max_m):
    """Nearest node to each point (projected metres), with the distance and whether it is within max_m."""
    ids = list(nodes)
    res = []
    for x, y in points:
        d, n = min((math.hypot(x - nodes[k][0], y - nodes[k][1]), k) for k in ids)
        res.append({"node": n, "distance_m": d, "ok": d <= max_m})
    return res
