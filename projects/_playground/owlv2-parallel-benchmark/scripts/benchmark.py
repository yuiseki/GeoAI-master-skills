"""CPU OWLv2 detector-only benchmark on previously prepared 1024-pixel views."""
import argparse
import hashlib
import json
import multiprocessing as mp
import os
import time
from pathlib import Path

QUERIES = ["a utility pole", "a street light pole", "a telegraph pole"]
MODEL = "google/owlv2-base-patch16-ensemble"
ROOT = Path(__file__).resolve().parents[1]


def iou(a, b):
    inter = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = max(0, a[2] - a[0]) * max(0, a[3] - a[1]) + max(0, b[2] - b[0]) * max(0, b[3] - b[1]) - inter
    return inter / union if union else 0


def compare(a, b):
    candidates = sorted([(iou(x["box"], y["box"]), i, j) for i, x in enumerate(a) for j, y in enumerate(b)
                         if x["view"] == y["view"] and x["query"] == y["query"]], reverse=True)
    used_a, used_b, matches = set(), set(), []
    for overlap, i, j in candidates:
        if overlap >= .5 and i not in used_a and j not in used_b:
            used_a.add(i); used_b.add(j)
            matches.append((overlap, abs(a[i]["score"] - b[j]["score"]), max(abs(x-y) for x, y in zip(a[i]["box"], b[j]["box"]))))
    return {"baseline_detections": len(a), "candidate_detections": len(b), "matched": len(matches), "missing": len(a)-len(matches), "extra": len(b)-len(matches), "min_iou": min((m[0] for m in matches), default=None), "max_score_difference": max((m[1] for m in matches), default=None), "max_coordinate_difference_px": max((m[2] for m in matches), default=None)}


def worker_init(threads):
    global torch, processor, model
    import torch as torch_module
    from transformers import Owlv2ForObjectDetection, Owlv2Processor
    torch = torch_module
    torch.set_num_threads(threads)
    torch.set_num_interop_threads(1)
    processor = Owlv2Processor.from_pretrained(MODEL, local_files_only=True)
    model = Owlv2ForObjectDetection.from_pretrained(MODEL, local_files_only=True).eval()


def infer(paths):
    from PIL import Image
    imgs = [Image.open(path).convert("RGB") for path in paths]
    inputs = processor(text=[QUERIES for _ in imgs], images=imgs, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
    sizes = torch.tensor([[max(im.size), max(im.size)] for im in imgs])
    objects = processor.image_processor.post_process_object_detection(outputs, threshold=.15, target_sizes=sizes)
    rows = []
    for path, result in zip(paths, objects):
        for box, score, label in zip(result["boxes"], result["scores"], result["labels"]):
            rows.append({"view": Path(path).name, "query": QUERIES[int(label)], "box": [float(x) for x in box], "score": float(score)})
    return rows


def peak_memory():
    cgroup = next(x.split(":", 2)[2].strip() for x in Path("/proc/self/cgroup").read_text().splitlines() if x.startswith("0::"))
    return int((Path("/sys/fs/cgroup") / cgroup.lstrip("/") / "memory.peak").read_text().strip())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["sequential", "workers2", "batch2", "compare"])
    p.add_argument("--views", type=Path)
    args = p.parse_args()
    out = ROOT / "outputs"
    out.mkdir(exist_ok=True)
    if args.mode == "compare":
        baseline = json.loads((out / "sequential.json").read_text(encoding="utf-8"))
        runs = {mode: json.loads((out / f"{mode}.json").read_text(encoding="utf-8")) for mode in ("sequential", "workers2", "batch2")}
        result = {"metrics": {mode: {"seconds": v["seconds_including_model_load"], "peak_mib": v["cgroup_memory_peak_bytes"] / 1024**2, "speedup": baseline["seconds_including_model_load"] / v["seconds_including_model_load"]} for mode, v in runs.items()}, "matches": {mode: compare(baseline["detections"], runs[mode]["detections"]) for mode in ("workers2", "batch2")}}
        (out / "comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    start = time.perf_counter()
    paths = sorted(args.views.glob("*.jpg"))[:8]
    if len(paths) != 8:
        raise ValueError("8 views required")
    chunks = [[str(x) for x in paths[i:i+(2 if args.mode == 'batch2' else 1)]] for i in range(0, len(paths), (2 if args.mode == 'batch2' else 1))]
    if args.mode == "workers2":
        with mp.get_context("spawn").Pool(2, initializer=worker_init, initargs=(2,)) as pool:
            result = list(pool.map(infer, chunks))
    else:
        worker_init(4)
        result = [infer(chunk) for chunk in chunks]
    detections = [row for chunk in result for row in chunk]
    data = {"mode": args.mode, "model": MODEL, "threshold": .15, "queries": QUERIES, "views": [{"file": x.name, "sha256": hashlib.sha256(x.read_bytes()).hexdigest()} for x in paths], "seconds_including_model_load": time.perf_counter()-start, "cgroup_memory_peak_bytes": peak_memory(), "detections": detections}
    (out / f"{args.mode}.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in data.items() if k not in ("views", "detections")} | {"detection_count": len(detections)}))


if __name__ == "__main__":
    main()
