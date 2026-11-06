"""Splits, destination clusters, training and evaluation of EXPERIMENT_PLAN.md.

  python3 scripts/run.py split   --variant rand|late          # writes the split and its counts
  python3 scripts/run.py cluster --variant rand|late          # mean-shift on the training destinations
  python3 scripts/run.py time    --variant rand               # seconds per step, before fixing the budget
  python3 scripts/run.py train   --variant rand --model mlp|noemb --steps N --seed S
  python3 scripts/run.py eval    --variant rand|late          # M0, M1 and every trained model of the variant

variant rand: S_rand (500 uniform cuts in the whole period, seed 42), V_rand (seed 1337), the 320 Kaggle prefixes.
variant late: train before 2014-04-01; S_early (cuts before, seed 42), V (cuts before, seed 1337), S_late (cuts from
2014-04-01, seed 7).
"""

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np

from porto import batch_first_last, haversine, sample_prefixes, snapshot_cut, time_features, uniform_cuts

ROOT = Path(__file__).resolve().parents[4]
ART = ROOT / "artifacts/_benchmark/taxi-destination-porto"
OUT = Path(__file__).resolve().parent.parent / "outputs"
K = 5
LATE = 1396310400          # 2014-04-01 00:00 UTC
META = ("origin_call", "origin_stand", "week", "dow", "qhour", "day_type", "taxi")


def load():
    return dict(np.load(ART / "trips.npz", allow_pickle=True))


def dest(t, idx):
    last = t["off"][idx + 1] - 1
    return np.stack([t["lat"][last], t["lon"][last]], 1).astype("float64")


def split(t, variant):
    path = ART / f"split_{variant}.npz"
    if path.exists():
        return dict(np.load(path))
    ts, lens = t["timestamp"], t["lens"]
    begin, end = int(ts.min()), int(ts.max())
    sets = {}
    free = np.ones(len(ts), dtype=bool)

    def cut(name, lo, hi, seed, eligible):
        nonlocal free
        ok = np.flatnonzero(free & eligible)
        trip, n, at = snapshot_cut(ts[ok], lens[ok], uniform_cuts(lo, hi, 500, seed), return_cut=True)
        sets[name + "_trip"], sets[name + "_n"], sets[name + "_cut"] = ok[trip], n, at
        free[ok[trip]] = False

    every = np.ones(len(ts), dtype=bool)
    if variant == "rand":
        cut("test", begin, end, 42, every)
        cut("valid", begin, end, 1337, every)
        sets["train"] = np.flatnonzero(free)
    elif variant == "late":
        cut("late", LATE, end, 7, every)
        cut("test", begin, LATE, 42, every)
        cut("valid", begin, LATE, 1337, every)
        sets["train"] = np.flatnonzero(free & (ts < LATE))
    else:
        raise ValueError(variant)
    np.savez(path, **sets)
    return sets


def meta_maps(t, train):
    calls = np.unique(t["origin_call"][train])
    calls = calls[calls > 0]
    taxis = np.unique(t["taxi_id"][train])
    return dict(calls=calls, taxis=taxis)


def meta_of(t, idx, maps, ts=None):
    """Metadata indices; unseen clients and taxis map to 0. ts: the time of the start (default the trip's start)."""
    ts = t["timestamp"][idx] if ts is None else ts
    q, dow, week = time_features(ts)
    oc = t["origin_call"][idx]
    pos = np.searchsorted(maps["calls"], oc)
    hit = (pos < len(maps["calls"])) & (maps["calls"][np.minimum(pos, len(maps["calls"]) - 1)] == oc) & (oc > 0)
    tx = t["taxi_id"][idx]
    tpos = np.searchsorted(maps["taxis"], tx)
    thit = (tpos < len(maps["taxis"])) & (maps["taxis"][np.minimum(tpos, len(maps["taxis"]) - 1)] == tx)
    return dict(origin_call=np.where(hit, pos + 1, 0), origin_stand=np.clip(t["origin_stand"][idx], 0, 63),
                week=week, dow=dow, qhour=q, day_type=t["day_type"][idx].astype(np.int64),
                taxi=np.where(thit, tpos + 1, 0))


def emb_sizes(maps):
    return dict(origin_call=len(maps["calls"]) + 1, origin_stand=64, week=52, dow=7, qhour=96, day_type=3,
                taxi=len(maps["taxis"]) + 1)


def clusters(t, variant, train):
    path = ART / f"clusters_{variant}.npy"
    if path.exists():
        return np.load(path)
    from sklearn.cluster import MeanShift
    pts = dest(t, train)
    t0 = time.time()
    ms = MeanShift(bandwidth=0.001, bin_seeding=True, min_bin_freq=5, n_jobs=4).fit(pts)
    c = ms.cluster_centers_
    np.save(path, c)
    print(f"clusters {len(c)} in {time.time() - t0:.0f}s", flush=True)
    return c


def kaggle():
    k = dict(np.load(ART / "kaggle_test.npz", allow_pickle=True))
    return k


class Data:
    def __init__(self, variant):
        self.t = load()
        self.s = split(self.t, variant)
        self.maps = meta_maps(self.t, self.s["train"])
        tr = self.s["train"]
        pts_idx = np.concatenate([np.arange(self.t["off"][i], self.t["off"][i + 1]) for i in tr[:: max(1, len(tr) // 20000)]])
        self.mean = np.array([self.t["lat"][pts_idx].mean(), self.t["lon"][pts_idx].mean()])
        self.std = np.array([self.t["lat"][pts_idx].std(), self.t["lon"][pts_idx].std()])

    def batch(self, trip, n, src=None):
        src = self.t if src is None else src
        x = batch_first_last(src["lat"], src["lon"], src["off"], trip, n, K)
        x = ((x - self.mean) / self.std).reshape(len(trip), -1).astype("float32")
        return x, meta_of(src, trip, self.maps)

    def kaggle(self):
        k = kaggle()
        idx = np.arange(len(k["lens"]))
        ok = k["lens"] > 0
        return k, idx, ok


def torch_inputs(x, meta, names):
    import torch
    return torch.from_numpy(x), {m: torch.from_numpy(np.asarray(meta[m], dtype=np.int64)) for m in names}


def build(variant, model, d):
    from model import DestMLP
    names = META if model == "mlp" else ()
    sizes = {m: emb_sizes(d.maps)[m] for m in names}
    c = clusters(d.t, variant, d.s["train"])
    return DestMLP(c, n_points=2 * K, emb_sizes=sizes), names


def predict(net, names, d, trip, n, src=None, bs=5000):
    import torch
    out = []
    with torch.no_grad():
        for i in range(0, len(trip), bs):
            x, m = d.batch(trip[i:i + bs], n[i:i + bs], src)
            out.append(net(*torch_inputs(x, m, names)).numpy())
    return np.concatenate(out).astype("float64")


def train(args):
    import torch
    from model import equirect_loss
    torch.set_num_threads(4)
    torch.manual_seed(args.seed)
    rng = np.random.default_rng(args.seed)
    d = Data(args.variant)
    net, names = build(args.variant, args.model, d)
    opt = torch.optim.SGD(net.parameters(), lr=0.01, momentum=0.9)
    tr = d.s["train"]
    vtrip, vn = d.s["valid_trip"], d.s["valid_n"]
    vdest = dest(d.t, vtrip)
    tag = f"{args.variant}_{args.model}_s{args.seed}"
    log = open(OUT / f"train_{tag}.csv", "w", newline="", encoding="utf-8")
    w = csv.writer(log)
    w.writerow(["step", "seconds", "train_loss_km", "valid_km"])
    best, t0, run = float("inf"), time.time(), []
    for step in range(1, args.steps + 1):
        j, n = sample_prefixes(d.t["lens"][tr], 200, rng)
        trip = tr[j]
        x, m = d.batch(trip, n)
        y = torch.from_numpy(dest(d.t, trip).astype("float32"))
        loss = equirect_loss(net(*torch_inputs(x, m, names)), y)
        opt.zero_grad()
        loss.backward()
        opt.step()
        run.append(loss.item())
        if step % args.every == 0 or step == args.steps:
            p = predict(net, names, d, vtrip, vn)
            v = haversine(p[:, 0], p[:, 1], vdest[:, 0], vdest[:, 1]).mean()
            w.writerow([step, round(time.time() - t0), round(float(np.mean(run)), 4), round(float(v), 4)])
            log.flush()
            print(f"step {step} {time.time() - t0:.0f}s train {np.mean(run):.3f} valid {v:.3f}", flush=True)
            run = []
            if v < best:
                best = v
                torch.save(net.state_dict(), ART / f"model_{tag}.pt")
    json.dump(dict(variant=args.variant, model=args.model, seed=args.seed, steps=args.steps, best_valid_km=best,
                   seconds=round(time.time() - t0), torch=torch.__version__),
              open(OUT / f"train_{tag}.json", "w", encoding="utf-8"), indent=1)


def time_steps(args):
    import torch
    from model import equirect_loss
    torch.set_num_threads(4)
    d = Data(args.variant)
    rng = np.random.default_rng(0)
    for model in ("mlp", "noemb"):
        net, names = build(args.variant, model, d)
        opt = torch.optim.SGD(net.parameters(), lr=0.01, momentum=0.9)
        tr = d.s["train"]
        t0 = time.time()
        for _ in range(200):
            j, n = sample_prefixes(d.t["lens"][tr], 200, rng)
            x, m = d.batch(tr[j], n)
            loss = equirect_loss(net(*torch_inputs(x, m, names)), torch.from_numpy(dest(d.t, tr[j]).astype("float32")))
            opt.zero_grad()
            loss.backward()
            opt.step()
        print(f"{model}: {(time.time() - t0) / 200 * 1000:.1f} ms per step", flush=True)


def boot_by_cut(err, group, reps=2000, seed=0):
    """95% interval of the mean, resampling whole cut times (trips at one time share the traffic)."""
    rng = np.random.default_rng(seed)
    g = np.unique(group, return_inverse=True)[1]
    sums, cnt = np.bincount(g, err), np.bincount(g)
    m = len(sums)
    idx = rng.integers(0, m, (reps, m))
    means = sums[idx].sum(1) / cnt[idx].sum(1)
    return np.percentile(means, [2.5, 97.5])


def evaluate(args):
    import torch
    d = Data(args.variant)
    tr = d.s["train"]
    centre = np.median(dest(d.t, tr), 0)
    tests = {}
    names = ["test"] + (["late"] if args.variant == "late" else [])
    for nm in names:
        trip, n = d.s[nm + "_trip"], d.s[nm + "_n"]
        tests[nm] = dict(trip=trip, n=n, y=dest(d.t, trip), src=None, group=d.s[nm + "_cut"])
    if args.variant == "rand":
        k, idx, ok = d.kaggle()
        tests["kaggle"] = dict(trip=idx, n=k["lens"], y=np.stack([k["dest_lat"], k["dest_lon"]], 1), src=k,
                               group=np.arange(len(idx)), ok=ok)
    models = {}
    for p in sorted(ART.glob(f"model_{args.variant}_*.pt")):
        model = p.stem.split("_")[2]
        net, nms = build(args.variant, model, d)
        net.load_state_dict(torch.load(p))
        net.eval()
        models[p.stem.replace("model_", "")] = (net, nms)
    rows = []
    for nm, te in tests.items():
        src = te["src"] if te["src"] is not None else d.t
        has = te.get("ok", np.ones(len(te["n"]), dtype=bool))
        trip, n = te["trip"][has], te["n"][has]
        preds = {"M0_centre": np.tile(centre, (len(has), 1))}
        last = src["off"][trip] + n - 1
        p = np.tile(centre, (len(has), 1))
        p[has] = np.stack([src["lat"][last], src["lon"][last]], 1)
        preds["M1_last_point"] = p
        for tag, (net, nms) in models.items():
            p = np.tile(centre, (len(has), 1))
            p[has] = predict(net, nms, d, trip, n, te["src"])
            preds[("M2_" if tag.split("_")[1] == "mlp" else "M3_") + tag] = p
        for mname, p in preds.items():
            e = haversine(p[:, 0], p[:, 1], te["y"][:, 0], te["y"][:, 1])
            lo, hi = boot_by_cut(e, te["group"])
            rows.append(dict(variant=args.variant, test=nm, model=mname, n=len(e), mean_km=round(float(e.mean()), 4),
                             ci_low=round(float(lo), 4), ci_high=round(float(hi), 4),
                             groups=len(np.unique(te["group"])),
                             empty_prefixes=int((~has).sum())))
            np.save(ART / f"err_{args.variant}_{nm}_{mname}.npy", e)
            print(rows[-1], flush=True)
    with open(OUT / f"eval_{args.variant}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("--variant", default="rand")
    ap.add_argument("--model", default="mlp")
    ap.add_argument("--steps", type=int, default=1000)
    ap.add_argument("--every", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    if a.cmd == "split":
        t = load()
        s = split(t, a.variant)
        rows = [dict(variant=a.variant, set=k.replace("_trip", ""), trips=len(v)) for k, v in s.items()
                if k.endswith("_trip") or k == "train"]
        with open(OUT / f"split_{a.variant}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(rows)
    elif a.cmd == "cluster":
        t = load()
        c = clusters(t, a.variant, split(t, a.variant)["train"])
        print(len(c))
    elif a.cmd == "time":
        time_steps(a)
    elif a.cmd == "train":
        train(a)
    elif a.cmd == "eval":
        evaluate(a)


if __name__ == "__main__":
    main()
