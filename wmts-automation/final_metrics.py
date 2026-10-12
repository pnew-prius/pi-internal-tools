"""Summarize a sequential run: step timings, tiles stored per zoom (from blob storage), seam checks, VM CPU.
  python final_metrics.py --workspace WMTSTEST --group WW26-All --out results/<run>   (needs GEOSERVER_PASS and az login)
"""
import argparse, json, os, re, subprocess, statistics, collections, datetime
from gs_client import call

_ap = argparse.ArgumentParser(); _ap.add_argument("--workspace", required=True); _ap.add_argument("--group", required=True); _ap.add_argument("--out", required=True)
_a = _ap.parse_args()

os.environ["AZURE_EXTENSION_DIR"] = os.path.join(os.environ["TEMP"], "azext_empty")
M = json.load(open(os.path.join(_a.out, "metrics_seq.json")))
L = f"{_a.workspace}:{_a.group}"
out = {}
adds = [a for a in M["adds"] if "steps" in a]
out["adds_ok"] = len(adds)
out["adds_failed"] = [a["tile"] for a in M["adds"] if "error" in a]
out["elapsed_sec"] = M.get("elapsed_sec")
for st in ("publish", "group_update", "tile_config", "truncate", "seed"):
    v = [a["steps"][st] for a in adds]
    out[f"step_{st}"] = {"mean": round(statistics.mean(v), 2), "median": round(statistics.median(v), 2), "max": max(v), "total": round(sum(v), 1)}
tot = [a["wall_sec"] for a in adds]
out["per_add_wall"] = {"mean": round(statistics.mean(tot), 1), "median": round(statistics.median(tot), 1), "min": min(tot), "max": max(tot)}
first, last = adds[:10], adds[-10:]
out["trend_first10_vs_last10"] = {
    "seed_mean": [round(statistics.mean(a["steps"]["seed"] for a in g), 1) for g in (first, last)],
    "group_update_mean": [round(statistics.mean(a["steps"]["group_update"] for a in g), 2) for g in (first, last)],
    "total_mean": [round(statistics.mean(a["wall_sec"] for a in g), 1) for g in (first, last)]}
out["tiles_job_total_sum"] = sum(a.get("tiles_job_total", 0) for a in adds)
adj = [a for a in adds if a["adjoining"]]
out["adds_with_adjoining_neighbors"] = len(adj)
out["adjoining_pairs"] = sum(len(a["adjoining"]) for a in adds)
out["kinds"] = dict(collections.Counter(x["kind"] for a in adds for x in a["adjoining"]))
seam = [(a["tile"], n, z, v) for a in adds for n, d in a.get("seam_post", {}).items() for z, v in d.items()]
out["seam_checks"] = {"total": len(seam), "match_truth": sum(1 for s in seam if s[3].get("match")), "mismatch": [(s[0], s[1], s[2], s[3]) for s in seam if not s[3].get("match")][:8]}
chk = [a["check_new_center"] for a in adds]
out["new_center_checks"] = {"total": len(chk) * 2, "http200_hit": sum(1 for c in chk for z in c.values() if z["http"] == "200" and z["cache"] == "HIT"),
                            "nonblank_gt0": sum(1 for c in chk for z in c.values() if (z["nonblank"] or 0) > 0)}
# tiles in blob storage under the group's internal GWC id
c, r = call("dev", "GET", f"/gwc/rest/layers/{L}.json")
gid = r["GeoServerLayer"]["id"]; out["gwc_layer_id"] = gid
p = subprocess.run(["az", "storage", "blob", "list", "--account-name", "pigeoserverprod", "--container-name", "tilecache", "--prefix", gid + "/",
                    "--auth-mode", "login", "--num-results", "500000", "--query", "[].{n:name,b:properties.contentLength}", "-o", "json"], capture_output=True, text=True, shell=True)
blobs = json.loads(p.stdout) if p.stdout.strip() else []
bz = collections.defaultdict(lambda: [0, 0])
fmts = collections.Counter(); grids = collections.Counter()
for b in blobs:
    parts = b["n"].split("/")  # id/gridset/format/style/z/x/y.ext
    if len(parts) >= 7:
        z = int(parts[4]); bz[z][0] += 1; bz[z][1] += b["b"]; fmts[parts[2]] += 1; grids[parts[1]] += 1
out["tiles_stored"] = {"total_tiles": sum(v[0] for v in bz.values()), "total_MB": round(sum(v[1] for v in bz.values()) / 1e6, 1),
                       "formats": dict(fmts), "gridsets": dict(grids),
                       "by_zoom": {z: {"tiles": v[0], "MB": round(v[1] / 1e6, 2)} for z, v in sorted(bz.items())}}
# VM CPU over the run window
start = datetime.datetime.fromtimestamp(M["start"], datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
end = datetime.datetime.fromtimestamp(M.get("end", M["start"]), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
_vms = json.loads(subprocess.run("az vm list -o json", capture_output=True, text=True, shell=True).stdout or "[]")
vm = [v["id"] for v in _vms if "geosvrd" in v["name"].lower()]
out["dev_vm"] = vm
if vm:
    q = subprocess.run(f'az monitor metrics list --resource {vm[0]} --metric "Percentage CPU" --interval PT1M --start-time {start} --end-time {end} --aggregation Average Maximum -o json', capture_output=True, text=True, shell=True)
    try:
        pts = json.loads(q.stdout)["value"][0]["timeseries"][0]["data"]
        avg = [x["average"] for x in pts if x.get("average") is not None]; mx = [x["maximum"] for x in pts if x.get("maximum") is not None]
        out["vm_cpu"] = {"minutes": len(avg), "avg_of_avg": round(statistics.mean(avg), 1), "peak": round(max(mx), 1)}
    except Exception as e:
        out["vm_cpu"] = {"error": (q.stderr or q.stdout)[:200]}
json.dump(out, open(os.path.join(_a.out, "final_metrics.json"), "w"), indent=1, default=str)
print(json.dumps(out, indent=1, default=str)[:6000])
