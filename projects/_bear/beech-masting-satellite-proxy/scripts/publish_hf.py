"""Bundle the Landsat 5 extraction (landsat.py) for Hugging Face, upload it, and check the uploaded revision.

    build   ART -> ART/hf/ (data/*.parquet, scripts/landsat.py, PROCESSING.json; README.md is written by hand)
    upload  ART -> yuiseki/landsat5-fagus-crenata-sites-jp-2026-10, prints the revision
    verify  ART REVISION -> reads every file back at the revision and compares sha256; recomputes the acquisition
            values from the uploaded pixels

From repository root:
    uvx --with rasterio --with pandas --with pyarrow --with huggingface_hub python \
      projects/_bear/beech-masting-satellite-proxy/scripts/publish_hf.py build artifacts/_bear/beech-masting-satellite-proxy
"""

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import landsat as L  # noqa: E402

REPO = "yuiseki/landsat5-fagus-crenata-sites-jp-2026-10"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build(art):
    hf = art / "hf"
    (hf / "data").mkdir(parents=True, exist_ok=True)
    (hf / "scripts").mkdir(exist_ok=True)
    items = pd.read_parquet(art / "items.parquet")
    acq = pd.read_parquet(art / "site_acquisitions.parquet")
    kept = L.dedupe(acq)[["ID", "item_id"]].assign(kept_for_site_date=True)
    acq = acq.merge(kept, on=["ID", "item_id"], how="left").fillna({"kept_for_site_date": False})
    acq = acq.sort_values(["ID", "datetime", "item_id"]).reset_index(drop=True)
    px = pd.read_parquet(art / "pixels.parquet").sort_values(["item_id", "ID", "dy", "dx"]).reset_index(drop=True)
    sites = pd.read_parquet(art / "sites.parquet")
    items.drop(columns=[c for c in items.columns if c.startswith("href_")]).to_parquet(hf / "data/items.parquet",
                                                                                     index=False)
    acq.to_parquet(hf / "data/site_acquisitions.parquet", index=False)
    px.to_parquet(hf / "data/pixels.parquet", index=False)
    sites.to_parquet(hf / "data/sites.parquet", index=False)
    shutil.copy(Path(__file__).parent / "landsat.py", hf / "scripts/landsat.py")
    shutil.copy(Path(__file__), hf / "scripts/publish_hf.py")
    import rasterio

    meta = {"source": {"stac": L.STAC, "collection": "landsat-c2-l2", "platform": "landsat-5",
                       "searched": "2026-10-28", "doi": "10.5066/P9IAXOVV"},
            "sites": {"dataset": "yuiseki/fagus-crenata-masting-jp-2026-06",
                      "revision": "db40a09e24cbc02d6f19a7180bafe5f04962f8f8", "columns": ["ID", "Location", "Latitude",
                                                                                          "Longitude"]},
            "windows": {k: list(v) for k, v in L.WINDOWS.items()}, "years": [min(L.YEARS), max(L.YEARS)],
            "radius_m": L.RADIUS_M, "scale": L.SCALE, "offset": L.OFFSET, "valid_dn": list(L.VALID_DN),
            "excluded": {"qa_pixel": {"fill": 0, "dilated_cloud": 1, "cloud": 3, "cloud_shadow": 4, "snow": 5},
                         "qa_radsat": {"band3": 2, "band4": 3, "band5": 4, "dropped": 9},
                         "dn_outside_valid_range": ["red", "nir08", "swir16"]},
            "kept_but_counted": {"qa_pixel": {"water": 7}},
            "duplicate_date_rule": "per site and date, most valid pixels, ties to the smaller item_id",
            "software": {"rasterio": rasterio.__version__, "gdal": rasterio.__gdal_version__,
                         "pandas": pd.__version__},
            "counts": {"items": len(items), "items_by_tier": items.tier.value_counts().to_dict(),
                       "site_acquisitions": len(acq), "kept_for_site_date": int(acq.kept_for_site_date.sum()),
                       "pixels": len(px)},
            "sha256": {}}
    for p in sorted((hf / "data").glob("*.parquet")):
        meta["sha256"][f"data/{p.name}"] = sha(p)
    (hf / "PROCESSING.json").write_text(json.dumps(meta, indent=1, default=str) + "\n")
    print(json.dumps(meta["counts"], indent=1, default=str))


def upload(art):
    from huggingface_hub import HfApi

    api = HfApi()
    api.create_repo(REPO, repo_type="dataset", exist_ok=True)
    info = api.upload_folder(folder_path=str(art / "hf"), repo_id=REPO, repo_type="dataset",
                             commit_message="Landsat 5 TM C2 L2 around the 102 Dryad beech sites")
    print(info.oid)


def verify(art, rev):
    from huggingface_hub import hf_hub_download

    hf = art / "hf"
    out = {}
    for p in sorted(x for x in hf.rglob("*") if x.is_file()):
        rel = p.relative_to(hf).as_posix()
        got = hf_hub_download(REPO, rel, repo_type="dataset", revision=rev)
        out[rel] = sha(got) == sha(p)
    px = pd.read_parquet(hf_hub_download(REPO, "data/pixels.parquet", repo_type="dataset", revision=rev))
    acq = pd.read_parquet(hf_hub_download(REPO, "data/site_acquisitions.parquet", repo_type="dataset",
                                          revision=rev)).set_index(["item_id", "ID"])
    bad = 0
    for (iid, sid), g in px.groupby(["item_id", "ID"]):
        a = L.aggregate(g.red.to_numpy(), g.nir08.to_numpy(), g.swir16.to_numpy(), g.qa_pixel.to_numpy(),
                        g.qa_radsat.to_numpy())
        r = acq.loc[(iid, sid)]
        for k, v in a.items():
            if not (v == r[k] or (pd.isna(v) and pd.isna(r[k]))):
                bad += 1
    res = {"revision": rev, "files_match": out, "all_files_match": all(out.values()),
           "acquisitions_recomputed": len(acq), "mismatched_values": bad}
    print(json.dumps(res, indent=1))
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=["build", "upload", "verify"])
    ap.add_argument("art", type=Path)
    ap.add_argument("revision", nargs="?")
    a = ap.parse_args()
    if a.stage == "build":
        build(a.art)
    elif a.stage == "upload":
        upload(a.art)
    else:
        res = verify(a.art, a.revision)
        (a.art / "hf_verify.json").write_text(json.dumps(res, indent=1) + "\n")


if __name__ == "__main__":
    main()
