"""Add COGs to one layer group SEQUENTIALLY (one at a time, same steps each time) and record per-step metrics.

  python run_sequential_test.py --workspace WMTSTEST --group WW26-All --blobs blobs.json --out results/<run>
blobs.json = JSON list of blob paths inside the sourceimagery container (az storage blob list ... --query "[].name").
Seam checks compare the cached tile where a new COG meets earlier ones with an uncached live render.
Dev only. Needs `az login` (Key Vault credential) or GEOSERVER_PASS.
"""
import argparse
import json
import os
import re
import time

from add_cog import add_cog
from probe import get_tile, tile_bbox, tile_of, wms_nonblank

ap = argparse.ArgumentParser()
ap.add_argument("--workspace", required=True)
ap.add_argument("--group", required=True)
ap.add_argument("--blobs", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--margin", type=float, default=100.0, help="metres: COGs this close count as adjoining")
a = ap.parse_args()
WS, G, ENV = a.workspace, a.group, "dev"
L = f"{WS}:{G}"
os.makedirs(a.out, exist_ok=True)
OUT = os.path.join(a.out, "metrics_seq.json")


def key(n):
    m = re.search(r"-(\d+)([a-z]?)-RGB", n)
    return (int(m.group(1)), m.group(2)) if m else (10**9, n)


order = sorted(json.load(open(a.blobs)), key=key)
M = {"start": time.time(), "adds": [], "order": [re.search(r"/([^/]+)-RGB\.tif$", n).group(1) for n in order]}
fps = {}


def log(s):
    print(time.strftime("%H:%M:%S"), s, flush=True)


def seams_for(fp):
    out = []
    for n, f in fps.items():
        ex = (fp[0] - a.margin, fp[1] - a.margin, fp[2] + a.margin, fp[3] + a.margin)
        ix = (max(ex[0], f[0]), max(ex[1], f[1]), min(ex[2], f[2]), min(ex[3], f[3]))
        if ix[0] <= ix[2] and ix[1] <= ix[3]:
            overlap = min(fp[2], f[2]) > max(fp[0], f[0]) and min(fp[3], f[3]) > max(fp[1], f[1])
            out.append({"neighbor": n, "kind": "overlap" if overlap else "touch", "pt": ((ix[0] + ix[2]) / 2, (ix[1] + ix[3]) / 2)})
    return out


def probe(pt, zooms, truth=False):
    r = {}
    for z in zooms:
        c, rw = tile_of(pt[0], pt[1], z)
        t = get_tile(L, z, c, rw)
        r[f"z{z}"] = {"http": t["http"], "cache": t["cache"], "nonblank": t["nonblank"]}
        if truth:
            tn = wms_nonblank(L, tile_bbox(c, rw, z))
            r[f"z{z}"].update(truth_nonblank=tn, match=t["nonblank"] is not None and tn is not None and abs(t["nonblank"] - tn) < 0.03)
    return r


for i, blob in enumerate(order, 1):
    tile = re.search(r"/([^/]+)-RGB\.tif$", blob).group(1)
    try:
        t0 = time.time()
        m = add_cog(ENV, WS, G, tile, blob)
        fp = m["footprint_3857"]
        seams = seams_for(fp)
        m["adjoining"] = [{"neighbor": s["neighbor"], "kind": s["kind"]} for s in seams]
        m["check_new_center"] = probe(((fp[0] + fp[2]) / 2, (fp[1] + fp[3]) / 2), (10, 15))
        m["seam_post"] = {s["neighbor"]: probe(s["pt"], (12, 15), truth=True) for s in seams[:2]}
        fps[tile] = fp
        m["wall_sec"] = round(time.time() - t0, 1)
        M["adds"].append(m)
        log(f"[{i}/{len(order)}] {tile}: {m['group_action']} | tiles~{m.get('tiles_job_total')} | seed {m['steps']['seed']}s | "
            f"total {m['wall_sec']}s | adjoining {len(seams)} | strays removed {len(m['stray_tile_layers_removed'])}")
    except Exception as e:  # keep going: the add is idempotent, a failed COG can be re-run later
        M["adds"].append({"tile": tile, "error": str(e)[:300]})
        log(f"[{i}/{len(order)}] {tile} FAILED: {str(e)[:200]}")
    json.dump(M, open(OUT, "w"))
M["end"] = time.time()
M["elapsed_sec"] = round(M["end"] - M["start"], 1)
json.dump(M, open(OUT, "w"))
log(f"SEQ DONE {M['elapsed_sec']}s")
