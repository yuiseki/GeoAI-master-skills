"""Training and evaluation of EXPERIMENT_PLAN.md.

  python3 scripts/run.py prepare                      # windows, split, adjacency, scaler: artifacts/.../prepared.npz
  python3 scripts/run.py baselines                    # M0 historical average and M1 last value on the test split
  python3 scripts/run.py time --k 2                   # seconds per epoch, before fixing the budget
  python3 scripts/run.py train --k 2|0 --seed S [--epochs 100] [--max-batches N]
  python3 scripts/run.py evaluate                     # every trained model, horizons 3, 6, 12, with day intervals
"""

import argparse
import csv
import json
import math
import time
from pathlib import Path

import numpy as np

from pems import (adjacency, historical_average, make_xy, masked_metrics, random_walk, read_h5, split_counts,
                  time_in_day, window_starts)

ROOT = Path(__file__).resolve().parents[4]
ART = ROOT / "artifacts/_benchmark/pems-bay-dcrnn"
RAW = ART / "raw"
OUT = Path(__file__).resolve().parent.parent / "outputs"
HORIZONS = (3, 6, 12)


def prepare():
    v, t, ids = read_h5(RAW / "gdrive/pems-bay.h5")
    starts = window_starts(len(t))
    tr, va, te = split_counts(len(starts))
    rows = [r for r in csv.reader(open(RAW / "distances_bay_2017.csv", encoding="utf-8"))]
    w = adjacency([(int(a), int(b), float(d)) for a, b, d in rows], [int(i) for i in ids])
    x_tr, _ = make_xy(v, time_in_day(t), starts[:tr])
    mean, sd = float(x_tr[..., 0].mean()), float(x_tr[..., 0].std())
    np.savez(ART / "prepared.npz", values=v, t=t, ids=ids, starts=starts, w=w, mean=mean, sd=sd,
             split=np.array([tr, va, te]))
    info = dict(times=len(t), sensors=len(ids), samples=len(starts), train=tr, val=va, test=te,
                adjacency_nonzero=int((w > 0).sum()), adjacency_nonzero_offdiag=int(((w > 0) & ~np.eye(len(w), dtype=bool)).sum()),
                distance_rows=len(rows), scaler_mean=round(mean, 4), scaler_sd=round(sd, 4),
                zeros_share=round(float((v == 0).mean()), 6))
    with open(OUT / "prepared.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(info))
        wr.writeheader()
        wr.writerow(info)
    print(info)


def load():
    p = dict(np.load(ART / "prepared.npz"))
    p["mean"], p["sd"] = float(p["mean"]), float(p["sd"])
    tr, va, te = p["split"]
    s = p["starts"]
    p["sets"] = dict(train=s[:tr], val=s[tr:tr + va], test=s[tr + va:])
    p["tod"] = time_in_day(p["t"])
    return p


def day_of(p, starts, h):
    return (p["t"][starts + h] // (86400 * 10**9)).astype("int64")


def boot_days(err_by_day_sum, cnt_by_day, reps=2000, seed=0):
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(cnt_by_day), (reps, len(cnt_by_day)))
    return np.percentile(err_by_day_sum[idx].sum(1) / cnt_by_day[idx].sum(1), [2.5, 97.5])


def per_day(err, truth, days):
    """err, truth (b, n); sums of |err| over the non-missing points per day, and counts."""
    ok = truth != 0
    u, inv = np.unique(days, return_inverse=True)
    s = np.bincount(inv, (np.abs(err) * ok).sum(1))
    c = np.bincount(inv, ok.sum(1))
    return u, s, c


def baselines():
    p = load()
    te = p["sets"]["test"]
    rows = []
    for h in HORIZONS:
        truth = p["values"][te + h]
        preds = {"M0_historical_average": historical_average(p["values"], te + h, weeks=4),
                 "M1_last_value": p["values"][te]}
        for name, pr in preds.items():
            m = masked_metrics(pr, truth)
            u, s, c = per_day(pr - truth, truth, day_of(p, te, h))
            lo, hi = boot_days(s, c)
            np.save(ART / f"pred_{name}_h{h}.npy", pr.astype("float32"))
            rows.append(dict(model=name, horizon_steps=h, minutes=5 * h, mae=round(m["mae"], 4), rmse=round(m["rmse"], 4),
                             mape=round(m["mape"], 4), mae_ci_low=round(lo, 4), mae_ci_high=round(hi, 4), days=len(u)))
            print(rows[-1], flush=True)
    write(OUT / "baselines.csv", rows)


def write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def supports(p, device):
    import torch
    w = p["w"]
    return [torch.tensor(random_walk(w).T, dtype=torch.float32, device=device),
            torch.tensor(random_walk(w.T).T, dtype=torch.float32, device=device)]


def batches(p, starts, bs, rng=None):
    order = rng.permutation(len(starts)) if rng is not None else np.arange(len(starts))
    for i in range(0, len(order), bs):
        s = starts[order[i:i + bs]]
        x, y = make_xy(p["values"], p["tod"], s)
        x = x.copy()
        x[..., 0] = (x[..., 0] - p["mean"]) / p["sd"]
        yield s, x.astype("float32"), y.astype("float32")


def predict(net, p, starts, device, bs=64):
    import torch
    net.eval()
    out = []
    with torch.no_grad():
        for _, x, _ in batches(p, starts, bs):
            o = net(torch.from_numpy(x).to(device)).cpu().numpy()
            out.append(o * p["sd"] + p["mean"])
    net.train()
    return np.concatenate(out)


def masked_mae_t(pred, truth):
    import torch
    ok = (truth != 0).float()
    return (torch.abs(pred - truth) * ok).sum() / ok.sum().clamp(min=1)


def build(p, k, device):
    from model import DCRNN
    return DCRNN(supports(p, device), num_nodes=len(p["ids"]), in_dim=2, units=64, layers=2, k=k, horizon=12).to(device)


def train(a):
    import torch
    torch.manual_seed(a.seed)
    rng = np.random.default_rng(a.seed)
    device = a.device
    p = load()
    net = build(p, a.k, device)
    opt = torch.optim.Adam(net.parameters(), lr=0.01, eps=1e-3)
    sched = torch.optim.lr_scheduler.MultiStepLR(opt, milestones=[20, 30, 40, 50], gamma=0.1)
    tag = f"k{a.k}_s{a.seed}"
    log = open(OUT / f"train_{tag}.csv", "w", newline="", encoding="utf-8")
    wr = csv.writer(log)
    wr.writerow(["epoch", "seconds", "lr", "train_mae", "val_mae", "teacher_prob_end"])
    best, best_ep, step, t0 = float("inf"), 0, 0, time.time()
    va = p["sets"]["val"]
    for ep in range(1, a.epochs + 1):
        losses = []
        for nb, (_, x, y) in enumerate(batches(p, p["sets"]["train"], 64, rng)):
            if a.max_batches and nb >= a.max_batches:
                break
            tp = 2000 / (2000 + math.exp(step / 2000))
            xt, yt = torch.from_numpy(x).to(device), torch.from_numpy(y).to(device)
            ys = (yt - p["mean"]) / p["sd"]
            out = net(xt, ys, teacher_prob=tp) * p["sd"] + p["mean"]
            loss = masked_mae_t(out, yt)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 5.0)
            opt.step()
            losses.append(loss.item())
            step += 1
        pv = predict(net, p, va if not a.max_batches else va[:640], device)
        vy = p["values"][(va if not a.max_batches else va[:640])[:, None] + np.arange(1, 13)[None, :]]
        v = masked_metrics(pv, vy)["mae"]
        lr = opt.param_groups[0]["lr"]
        sched.step()
        for g in opt.param_groups:
            g["lr"] = max(g["lr"], 2e-6)
        wr.writerow([ep, round(time.time() - t0), lr, round(float(np.mean(losses)), 4), round(v, 4), round(tp, 4)])
        log.flush()
        print(f"{tag} epoch {ep} {time.time() - t0:.0f}s train {np.mean(losses):.4f} val {v:.4f} tp {tp:.3f}", flush=True)
        if v < best:
            best, best_ep = v, ep
            torch.save(net.state_dict(), ART / f"model_{tag}.pt")
        if ep - best_ep >= 50:
            break
    net.load_state_dict(torch.load(ART / f"model_{tag}.pt", map_location=device))
    pt = predict(net, p, p["sets"]["test"], device)
    for h in HORIZONS:
        np.save(ART / f"pred_{'M2' if a.k > 0 else 'M3'}_{tag}_h{h}.npy", pt[:, h - 1].astype("float32"))
    json.dump(dict(k=a.k, seed=a.seed, epochs_run=ep, best_epoch=best_ep, best_val_mae=best,
                   seconds=round(time.time() - t0), device=device, torch=torch.__version__),
              open(OUT / f"train_{tag}.json", "w", encoding="utf-8"), indent=1)


def evaluate():
    p = load()
    te = p["sets"]["test"]
    rows = []
    for h in HORIZONS:
        truth = p["values"][te + h]
        days = day_of(p, te, h)
        for f in sorted(ART.glob(f"pred_*_h{h}.npy")):
            name = f.stem.replace("pred_", "").rsplit("_h", 1)[0]
            pr = np.load(f).astype("float64")
            m = masked_metrics(pr, truth)
            u, s, c = per_day(pr - truth, truth, days)
            lo, hi = boot_days(s, c)
            rows.append(dict(model=name, horizon_steps=h, minutes=5 * h, mae=round(m["mae"], 4), rmse=round(m["rmse"], 4),
                             mape=round(m["mape"], 4), mae_ci_low=round(lo, 4), mae_ci_high=round(hi, 4), days=len(u)))
            print(rows[-1], flush=True)
    write(OUT / "evaluate.csv", rows)


def compare():
    """Paired MAE differences on the same test points, with the day bootstrap."""
    from pems import boot_ratio, paired_day_sums
    p = load()
    te = p["sets"]["test"]
    pairs = [("M3_k0_s1", "M2_k2_s1"), ("M1_last_value", "M2_k2_s1"), ("M0_historical_average", "M2_k2_s1"),
             ("M1_last_value", "M3_k0_s1")]
    rows = []
    for h in HORIZONS:
        truth = p["values"][te + h]
        days = day_of(p, te, h)
        for a, b in pairs:
            pa = np.load(ART / f"pred_{a}_h{h}.npy").astype("float64")
            pb = np.load(ART / f"pred_{b}_h{h}.npy").astype("float64")
            u, s, c = paired_day_sums(pa, pb, truth, days)
            lo, hi = boot_ratio(s, c)
            rows.append(dict(a=a, b=b, horizon_steps=h, minutes=5 * h, mae_a_minus_b=round(s.sum() / c.sum(), 4),
                             ci_low=round(lo, 4), ci_high=round(hi, 4), days=len(u)))
            print(rows[-1], flush=True)
    write(OUT / "compare.csv", rows)


def explore():
    """Exploratory (after the main results): where does the graph help? Split the test points by the
    true speed (congested < 40 mph) and by the change over the horizon (|truth - last input| >= 10 mph)."""
    p = load()
    te = p["sets"]["test"]
    rows = []
    for h in HORIZONS:
        truth = p["values"][te + h]
        last = p["values"][te]
        a = np.abs(np.load(ART / f"pred_M3_k0_s1_h{h}.npy").astype("float64") - truth)
        b = np.abs(np.load(ART / f"pred_M2_k2_s1_h{h}.npy").astype("float64") - truth)
        ok = (truth != 0) & (last != 0)
        groups = {"free_flow_ge_40": truth >= 40, "congested_lt_40": truth < 40,
                  "steady_change_lt_10": np.abs(truth - last) < 10, "changing_ge_10": np.abs(truth - last) >= 10}
        for g, m in groups.items():
            m = m & ok
            rows.append(dict(group=g, horizon_steps=h, minutes=5 * h, share=round(m.sum() / ok.sum(), 4),
                             mae_M3=round(a[m].mean(), 4), mae_M2=round(b[m].mean(), 4),
                             M3_minus_M2=round((a[m] - b[m]).mean(), 4),
                             share_of_total_gain=round((a[m] - b[m]).sum() / (a[ok] - b[ok]).sum(), 4)))
            print(rows[-1], flush=True)
    write(OUT / "explore_where_graph_helps.csv", rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--max-batches", type=int, default=0)
    ap.add_argument("--device", default="cuda")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    {"prepare": prepare, "baselines": baselines, "train": lambda: train(a), "evaluate": evaluate, "compare": compare, "explore": explore}[a.cmd]()


if __name__ == "__main__":
    main()
