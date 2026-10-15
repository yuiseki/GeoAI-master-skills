"""Check a small causal graph (DAG) before estimating anything: is it acyclic, what role does each variable
play between the treatment and the outcome, which backdoor paths are open, and is a given adjustment set
valid by the backdoor criterion. Standard library only; meant for graphs of a few to a dozen variables.

The graph file has one edge per line, chains allowed, and a line naming the unmeasured variables:

    latent: U
    L -> T -> Y
    L -> Y
    U -> T
    # comments and blank lines are ignored

A set Z satisfies the backdoor criterion for the effect of T on Y when no member of Z is a descendant of T,
and Z blocks every path between T and Y that starts with an arrow into T. A path is blocked by Z when a
non-collider on it is in Z, or a collider on it has neither itself nor a descendant in Z. Adjusting a
descendant of T (a mediator, a collider of T and Y, anything after T) is refused for the total effect.

roles   confounder               a cause of T and, not through T, of Y
        mediator                 on a directed path T -> ... -> Y
        collider                 caused by two variables on some path between T and Y
        descendant of a collider adjusting it opens the path as the collider would
        descendant of treatment  after T, not on the way to Y (adjusting it is still refused)
        descendant of the outcome
        cause of treatment only  not needed; adjusting it can amplify bias left by an unmeasured confounder
        cause of outcome only    not needed, harmless, often narrows the interval
        (unmeasured) is added to the latent ones.

This answers whether the effect is identified by adjustment, given the graph. The graph itself is an
assumption: no data check proves that an arrow is absent. Other routes to identification (front door,
instruments) are not searched.

Usage:
    python dag_check.py GRAPH TREATMENT OUTCOME [--adjust Z1 Z2 ...]
"""

import argparse
from itertools import combinations


def parse(lines):
    edges, latent = [], set()
    for raw in lines:
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("latent:"):
            latent |= set(line[len("latent:"):].split())
            continue
        nodes = [n.strip() for n in line.split("->")]
        if len(nodes) < 2 or not all(nodes):
            raise ValueError(f"not an edge: {raw!r}")
        edges += list(zip(nodes, nodes[1:]))
    return Dag(edges, latent)


class Dag:
    def __init__(self, edges, latent=()):
        self.edges = list(edges)
        self.latent = set(latent)
        self.nodes = sorted({n for e in self.edges for n in e} | self.latent)
        self.children = {n: set() for n in self.nodes}
        self.parents = {n: set() for n in self.nodes}
        for a, b in self.edges:
            self.children[a].add(b)
            self.parents[b].add(a)

    def cycle(self):
        state = {}

        def visit(n, stack):
            state[n] = "open"
            stack.append(n)
            for c in sorted(self.children[n]):
                if state.get(c) == "open":
                    return stack[stack.index(c):]
                if c not in state:
                    found = visit(c, stack)
                    if found:
                        return found
            state[n] = "done"
            stack.pop()
            return None

        for n in self.nodes:
            if n not in state:
                found = visit(n, [])
                if found:
                    return found
        return None

    def _reach(self, start, step):
        seen, todo = set(), [start]
        while todo:
            for m in step[todo.pop()]:
                if m not in seen:
                    seen.add(m)
                    todo.append(m)
        return seen

    def ancestors(self, n):
        return self._reach(n, self.parents)

    def descendants(self, n):
        return self._reach(n, self.children)

    def paths(self, a, b):
        """Every simple path between a and b ignoring direction, as [a, '->' or '<-', node, ..., b]."""
        out = []

        def walk(n, path, seen):
            if n == b:
                out.append(path)
                return
            for m in sorted(self.children[n] | self.parents[n]):
                if m not in seen:
                    arrow = "->" if m in self.children[n] else "<-"
                    walk(m, path + [arrow, m], seen | {m})

        walk(a, [a], {a})
        return out

    def _colliders(self, path):
        return [path[i] for i in range(2, len(path) - 2, 2) if path[i - 1] == "->" and path[i + 1] == "<-"]

    def blocked(self, path, z):
        z = set(z)
        for i in range(2, len(path) - 2, 2):
            n = path[i]
            if path[i - 1] == "->" and path[i + 1] == "<-":
                if n not in z and not (self.descendants(n) & z):
                    return True
            elif n in z:
                return True
        return False

    def _ready(self, t, y, z=()):
        if self.cycle():
            raise ValueError(f"the graph has a cycle: {' -> '.join(self.cycle())}")
        for n in (t, y, *z):
            if n not in self.children:
                raise ValueError(f"{n} is not in the graph")
        bad = sorted(set(z) & self.latent)
        if bad:
            raise ValueError(f"cannot adjust an unmeasured variable: {bad}")

    def roles(self, t, y):
        self._ready(t, y)
        after_t = self.descendants(t)
        # ancestors of y along paths that do not leave t
        cut = Dag([(a, b) for a, b in self.edges if a != t], self.latent)
        y_causes = cut.ancestors(y)
        colliders = {c for p in self.paths(t, y) for c in self._colliders(p)}
        near = set()
        for c in colliders:
            near |= self.descendants(c)
        out = {}
        for n in self.nodes:
            if n in (t, y):
                continue
            if n in colliders:
                role = "collider"
            elif n in after_t and n in self.ancestors(y):
                role = "mediator"
            elif n in near:
                role = "descendant of a collider"
            elif n in self.descendants(y):
                role = "descendant of the outcome"
            elif n in after_t:
                role = "descendant of treatment"
            elif n in self.ancestors(t) and n in y_causes:
                role = "confounder"
            elif n in self.ancestors(t):
                role = "cause of treatment only"
            elif n in y_causes:
                role = "cause of outcome only"
            else:
                role = "unrelated"
            out[n] = role + (" (unmeasured)" if n in self.latent else "")
        return out

    def check(self, t, y, z):
        z = list(z)
        self._ready(t, y, z)
        post = sorted(set(z) & self.descendants(t))
        backdoor = [p for p in self.paths(t, y) if p[1] == "<-"]
        open_back = [p for p in backdoor if not self.blocked(p, z)]
        opened = [p for p in self.paths(t, y) if self.blocked(p, []) and not self.blocked(p, z)]
        return {"valid": not post and not open_back, "post_treatment": post, "open_backdoor": open_back,
                "opened": opened}

    def adjustment_sets(self, t, y, limit=16):
        """Minimal valid adjustment sets among the measured variables that are not after T."""
        self._ready(t, y)
        pool = [n for n in self.nodes if n not in (t, y) and n not in self.latent
                and n not in self.descendants(t)]
        if len(pool) > limit:
            raise ValueError(f"{len(pool)} candidate variables; this checker is for small graphs")
        found = []
        for k in range(len(pool) + 1):
            for z in combinations(pool, k):
                if any(set(f) <= set(z) for f in found):
                    continue
                if self.check(t, y, z)["valid"]:
                    found.append(list(z))
        return found


def fmt(path):
    return " ".join(path)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("graph")
    p.add_argument("treatment")
    p.add_argument("outcome")
    p.add_argument("--adjust", nargs="*", default=[])
    a = p.parse_args()
    with open(a.graph) as f:
        d = parse(f)
    c = d.cycle()
    if c:
        raise SystemExit(f"the graph has a cycle: {' -> '.join(c + [c[0]])}; a DAG has none")
    print(f"{len(d.nodes)} variables, {len(d.edges)} arrows, unmeasured: {', '.join(sorted(d.latent)) or 'none'}")
    for n, role in d.roles(a.treatment, a.outcome).items():
        print(f"  {n}: {role}")
    print("paths between treatment and outcome (open with no adjustment?):")
    for path in d.paths(a.treatment, a.outcome):
        kind = "backdoor" if path[1] == "<-" else "from treatment"
        print(f"  {fmt(path)}   [{kind}, {'blocked' if d.blocked(path, []) else 'open'}]")
    r = d.check(a.treatment, a.outcome, a.adjust)
    print(f"adjusting {{{', '.join(a.adjust)}}}: {'valid' if r['valid'] else 'NOT valid'} by the backdoor criterion")
    for n in r["post_treatment"]:
        print(f"  {n} is after the treatment; adjusting it removes part of the effect or opens a path")
    for path in r["open_backdoor"]:
        print(f"  still open: {fmt(path)}")
    for path in r["opened"]:
        print(f"  opened by the adjustment: {fmt(path)}")
    sets = d.adjustment_sets(a.treatment, a.outcome)
    if sets:
        print("minimal valid sets of measured variables: " + "; ".join("{" + ", ".join(s) + "}" for s in sets))
    else:
        print("no set of measured variables is valid: the effect is not identified by adjustment in this graph")


if __name__ == "__main__":
    main()
