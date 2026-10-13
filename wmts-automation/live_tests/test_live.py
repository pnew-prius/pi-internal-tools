import io
import re
import subprocess
import sys
import threading
import time

import pytest
import requests

import add_cog as add_cog_mod
import app as app_mod
from add_cog import add_cog, group_state
from conftest import HERE, blob, tiles_in_cache
from gs_client import call
from jobs import JobManager
from probe import get_tile, tile_bbox, tile_of, wms_nonblank
from remove_service import remove_service
from store import JsonlStore

pytestmark = pytest.mark.live
UA = {"User-Agent": "wmts-automation/1.0"}
HOST = "https://devimageservices.priusintelli.com"


def tile_layers(ws):
    return [n for n in call("dev", "GET", "/gwc/rest/layers.json")[1] if n.startswith(ws + ":")]


def caps_layers(ws, kind):
    url = (f"{HOST}/{ws}/gwc/service/wmts?REQUEST=GetCapabilities" if kind == "wmts"
           else f"{HOST}/{ws}/ows?service=WMS&request=GetCapabilities&version=1.3.0")
    x = requests.get(url, headers=UA, timeout=90).text
    if kind == "wms":
        return re.findall(r"<Layer[^>]*>\s*<Name>([^<]+)</Name>", x)
    return re.findall(r"<Layer>\s*(?:<ows:Title>[^<]*</ows:Title>)?(?:(?!</Layer>).)*?<ows:Identifier>([^<]+)</ows:Identifier>", x, re.S)


def seam_point(fp_new, fp_old, margin=100.0):
    ex = (fp_new[0] - margin, fp_new[1] - margin, fp_new[2] + margin, fp_new[3] + margin)
    ix = (max(ex[0], fp_old[0]), max(ex[1], fp_old[1]), min(ex[2], fp_old[2]), min(ex[3], fp_old[3]))
    assert ix[0] <= ix[2] and ix[1] <= ix[3], "the two test COGs are expected to adjoin"
    return (ix[0] + ix[2]) / 2, (ix[1] + ix[3]) / 2


def wait_job(c, jid, timeout=300):
    t = time.time()
    while time.time() - t < timeout:
        j = c.get(f"/api/jobs/{jid}", headers={"X-MS-CLIENT-PRINCIPAL-NAME": "live@test"}).get_json()["job"]
        if j["status"] in ("done", "partial", "failed"):
            return j
        time.sleep(1)
    raise AssertionError("job timeout")


def test_wmts_adjoining_cogs_seam_matches_live_render(ws):
    a = add_cog("dev", ws, "Svc", "ww26-01", blob(1))
    b = add_cog("dev", ws, "Svc", "ww26-02", blob(2))
    assert group_state("dev", ws, "Svc")[1] == ["ww26-01", "ww26-02"]
    assert tile_layers(ws) == [f"{ws}:Svc"]                              # only the group is tiled
    L = f"{ws}:Svc"
    px, py = seam_point(b["footprint_3857"], a["footprint_3857"])
    for z in (12, 15):
        c, r = tile_of(px, py, z)
        t = get_tile(L, z, c, r)
        truth = wms_nonblank(L, tile_bbox(c, r, z))
        assert t["http"] == "200" and t["cache"] == "HIT"
        assert abs(t["nonblank"] - truth) < 0.03, f"seam tile z{z} differs from live render ({t['nonblank']} vs {truth})"
    c, r = tile_of(px, py, 15)
    assert get_tile(L, 15, c, r, fmt="image/jpeg")["http"] == "400"      # PNG only
    assert caps_layers(ws, "wmts") == ["Svc"]


def test_wms_service_renders_live_and_never_grows_a_tile_layer(ws):
    m = add_cog("dev", ws, "Live", "ww26-01", blob(1), service="wms")
    assert tile_layers(ws) == []
    fp = m["footprint_3857"]
    r = requests.get(f"{HOST}/{ws}/wms?service=WMS&version=1.1.1&request=GetMap&layers=Live&styles=&srs=EPSG:3857&bbox={','.join(map(str, fp))}"
                     "&width=512&height=512&format=image/png&transparent=true", headers=UA, timeout=180)
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.headers.get("geowebcache-miss-reason") == "not a tile layer"
    assert tile_layers(ws) == [] and caps_layers(ws, "wmts") == [] and caps_layers(ws, "wms") == ["Live"]


def test_batch_via_app_carries_on_past_a_missing_file(ws, tmp_path):
    mgr = JobManager(JsonlStore(str(tmp_path / "h.jsonl")))
    c = app_mod.create_app(mgr).test_client()
    H = {"X-MS-CLIENT-PRINCIPAL-NAME": "live@test"}
    text = "\n".join([blob(1), "Prius Intelli/automation-test/wmts/ww26-99-RGB.tif", blob(2)])
    r = c.post("/api/jobs", json={"workspace": ws, "group": "Svc", "blob_text": text, "service_type": "wms"}, headers=H)
    assert r.status_code == 202
    j = wait_job(c, r.get_json()["job"]["id"])
    assert j["status"] == "partial" and [i["status"] for i in j["items"]] == ["done", "failed", "done"]
    stores = {s["name"] for s in call("dev", "GET", f"/rest/workspaces/{ws}/coveragestores.json")[1]["coverageStores"]["coverageStore"]}
    assert stores == {"ww26-01", "ww26-02"}                              # the failed COG left nothing behind
    assert group_state("dev", ws, "Svc")[1] == ["ww26-01", "ww26-02"]


def test_refresh_repairs_a_failed_add(ws, monkeypatch):
    real = add_cog_mod.seed_request

    def boom(env, layer, kind, *a, **k):
        if kind == "seed":
            raise RuntimeError("simulated seed failure")
        return real(env, layer, kind, *a, **k)
    monkeypatch.setattr(add_cog_mod, "seed_request", boom)
    with pytest.raises(RuntimeError, match="simulated"):
        add_cog("dev", ws, "Svc", "ww26-01", blob(1))
    assert group_state("dev", ws, "Svc")[1] == ["ww26-01"]              # half-built: member present, tiles not seeded
    assert add_cog("dev", ws, "Svc", "ww26-01", blob(1))["skipped"]     # a plain re-run does not repair it
    monkeypatch.setattr(add_cog_mod, "seed_request", real)
    m = add_cog("dev", ws, "Svc", "ww26-01", blob(1), refresh=True)
    assert "refreshed" in m["group_action"] and m["tiles_job_total"] > 0
    fp = m["footprint_3857"]
    c, r = tile_of((fp[0] + fp[2]) / 2, (fp[1] + fp[3]) / 2, 15)
    t = get_tile(f"{ws}:Svc", 15, c, r)
    assert t["cache"] == "HIT" and (t["nonblank"] or 0) > 0 and tile_layers(ws) == [f"{ws}:Svc"]


def test_two_services_built_at_the_same_time_in_one_workspace(ws):
    errs = []

    def run(group, n):
        try:
            add_cog("dev", ws, group, f"ww26-{n:02d}", blob(n))
        except Exception as e:
            errs.append((group, str(e)))
    ts = [threading.Thread(target=run, args=("A", 1)), threading.Thread(target=run, args=("B", 2))]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errs, errs
    assert group_state("dev", ws, "A")[1] == ["ww26-01"] and group_state("dev", ws, "B")[1] == ["ww26-02"]
    assert sorted(tile_layers(ws)) == [f"{ws}:A", f"{ws}:B"]             # neither sweep deleted the other service's tiles


def test_two_app_instances_adding_to_the_same_service_do_not_lose_a_cog(ws):
    """Simulates two App Service instances (no shared in-memory lock) adding different COGs to one new group at once."""
    errs = []

    def run(n):
        try:
            add_cog("dev", ws, "Svc", f"ww26-{n:02d}", blob(n))
        except Exception as e:
            errs.append(str(e))
    ts = [threading.Thread(target=run, args=(1,)), threading.Thread(target=run, args=(2,))]
    [t.start() for t in ts]
    [t.join() for t in ts]
    members = group_state("dev", ws, "Svc")[1] if group_state("dev", ws, "Svc") else []
    assert not errs and sorted(members) == ["ww26-01", "ww26-02"], f"lost update: members={members} errors={errs}"


def test_killing_the_process_midway_then_refresh_recovers(ws):
    code = (f"import sys; sys.path.insert(0, r'{HERE}'); from add_cog import add_cog; "
            f"add_cog('dev', '{ws}', 'Svc', 'ww26-01', '{blob(1)}')")
    p = subprocess.Popen([sys.executable, "-c", code])
    t0 = time.time()
    while time.time() - t0 < 120 and not (group_state("dev", ws, "Svc") and "ww26-01" in group_state("dev", ws, "Svc")[1]):
        time.sleep(0.3)
    p.kill()
    p.wait()
    from gwc import wait_seed_idle
    wait_seed_idle("dev", f"{ws}:Svc")                                   # server-side tasks keep running after the client dies
    m = add_cog("dev", ws, "Svc", "ww26-01", blob(1), refresh=True)
    fp = m["footprint_3857"]
    c, r = tile_of((fp[0] + fp[2]) / 2, (fp[1] + fp[3]) / 2, 15)
    t = get_tile(f"{ws}:Svc", 15, c, r)
    assert group_state("dev", ws, "Svc")[1] == ["ww26-01"] and t["cache"] == "HIT" and (t["nonblank"] or 0) > 0
    assert tile_layers(ws) == [f"{ws}:Svc"]


def test_remove_service_leaves_no_tiles_in_the_shared_cache(ws):
    add_cog("dev", ws, "Svc", "ww26-01", blob(1))
    gid = call("dev", "GET", f"/gwc/rest/layers/{ws}:Svc.json")[1]["GeoServerLayer"]["id"]
    assert tiles_in_cache(gid) > 500
    out = remove_service("dev", ws, "Svc")
    assert out["truncated"] and group_state("dev", ws, "Svc") is None
    assert tiles_in_cache(gid) == 0 and out["layers_deleted"] == ["ww26-01"]


def test_prod_cannot_be_written_from_the_client():
    with pytest.raises(PermissionError):
        call("prod", "POST", "/rest/workspaces", {"workspace": {"name": "NOPE"}})
    c, r = call("prod", "GET", "/rest/workspaces.json", allow_prod=True)   # read-only listing is what the safety guard uses
    assert c == 200


@pytest.mark.slow
def test_scale_54_cogs_as_one_wms_batch_via_the_app(ws, tmp_path):
    import json
    blobs = json.load(open(f"{HERE}/results/2026-10-13-sequential-ww26/blobs.json"))
    mgr = JobManager(JsonlStore(str(tmp_path / "h.jsonl")))
    c = app_mod.create_app(mgr).test_client()
    r = c.post("/api/jobs", json={"workspace": ws, "group": "All", "blob_text": "\n".join(blobs), "service_type": "wms"},
               headers={"X-MS-CLIENT-PRINCIPAL-NAME": "live@test"})
    assert r.status_code == 202
    j = wait_job(c, r.get_json()["job"]["id"], timeout=1800)
    secs = [i["seconds"] for i in j["items"]]
    print(f"\nSCALE: {j['counts']} first10 mean {sum(secs[:10])/10:.1f}s last10 mean {sum(secs[-10:])/10:.1f}s max {max(secs)}s")
    assert j["counts"]["failed"] == 0 and len(group_state("dev", ws, "All")[1]) == len(blobs)
    assert sum(secs[-10:]) / 10 < 4 * sum(secs[:10]) / 10                 # no runaway slowdown as the group grows


def test_remove_via_the_app_clears_tiles_and_deletes_the_empty_workspace(ws, tmp_path):
    add_cog("dev", ws, "Svc", "ww26-01", blob(1))
    gid = call("dev", "GET", f"/gwc/rest/layers/{ws}:Svc.json")[1]["GeoServerLayer"]["id"]
    assert tiles_in_cache(gid) > 500
    mgr = JobManager(JsonlStore(str(tmp_path / "h.jsonl")))
    c = app_mod.create_app(mgr).test_client()
    H = {"X-MS-CLIENT-PRINCIPAL-NAME": "live@test"}
    assert c.post("/api/remove", json={"workspace": ws, "group": "Svc", "confirm": "wrong"}, headers=H).status_code == 400
    r = c.post("/api/remove", json={"workspace": ws, "group": "Svc", "confirm": "Svc"}, headers=H)
    assert r.status_code == 202
    j = wait_job(c, r.get_json()["job"]["id"])
    assert j["status"] == "done" and j["items"][0]["result"]["workspace_deleted"] is True
    assert tiles_in_cache(gid) == 0
    assert ws not in {w["name"] for w in call("dev", "GET", "/rest/workspaces.json")[1]["workspaces"]["workspace"]}


def test_prod_through_the_app_is_read_only_here_and_refuses_unconfirmed_writes(tmp_path, monkeypatch):
    """Real PROD, READ-ONLY: lists work for an authorized user; every write path is refused before anything is sent.
    This suite never writes to prod."""
    monkeypatch.setenv("WMTS_ENVS", "dev,prod")
    monkeypatch.setenv("WMTS_PROD_USERS", "live@test")
    mgr = JobManager(JsonlStore(str(tmp_path / "h.jsonl")))
    c = app_mod.create_app(mgr).test_client()
    ok, other = {"X-MS-CLIENT-PRINCIPAL-NAME": "live@test"}, {"X-MS-CLIENT-PRINCIPAL-NAME": "intruder@test"}
    assert c.get("/api/me", headers=ok).get_json()["envs"] == ["dev", "prod"]
    assert c.get("/api/me", headers=other).get_json()["envs"] == ["dev"]
    names = c.get("/api/workspaces?env=prod", headers=ok).get_json()["workspaces"]
    assert "COPE-S26" in names and len(names) > 50
    assert c.get("/api/groups?env=prod&workspace=COPE-S26", headers=ok).status_code == 200
    assert c.get("/api/workspaces?env=prod", headers=other).status_code == 403
    body = {"env": "prod", "workspace": "NOPE-LIVE", "group": "X", "blob_text": blob(1)}
    assert c.post("/api/jobs", json=body, headers=ok).status_code == 400                       # no confirm_prod
    assert c.post("/api/jobs", json=dict(body, confirm_prod=True), headers=other).status_code == 403
    assert c.post("/api/remove", json={"env": "prod", "workspace": "COPE-S26", "group": "x", "confirm": "x"}, headers=ok).status_code == 400
    assert not mgr.jobs                                                                          # nothing was ever started
