"""Add ONE COG to a WMTS service (a GWC-tiled GeoServer layer group).

Stateless: everything is read from GeoServer, so it can run now, later, or resume after a failure.
Order matters: publish -> add to group -> group bounds -> tile extent -> bbox truncate -> bbox seed -> stray sweep.
"""
import time
import urllib.parse

from gs_client import call
from gwc import bbox_to_3857, seed_request, set_tile_layer_xml, wait_seed_idle

ACCT = "cog://https://pigeoserverprod.blob.core.windows.net/sourceimagery/"
# Existing store whose Azure credential block (encrypted account key + Azure range reader) is copied to new stores.
TEMPLATE_STORE = ("COPE-S26", "codes26-01")
SEED_ZOOM = (0, 15)       # pre-seed range
TRUNCATE_ZOOM = (0, 24)   # truncate must cover EVERY zoom: live-rendered z16+ tiles go stale at seams too
EXPIRE_CLIENTS = 0        # seconds; 0 sends no-cache to browsers (consider raising, e.g. 86400)
STEPS = ["workspace", "publish", "group_update", "tile_config", "truncate", "seed", "reconcile"]


def group_state(env, ws, group):
    """Returns (group_json, member_names) or None when the group does not exist."""
    c, r = call(env, "GET", f"/rest/workspaces/{ws}/layergroups/{group}.json")
    if c != 200 or not isinstance(r, dict):
        return None
    pubs = r["layerGroup"]["publishables"]["published"]
    pubs = pubs if isinstance(pubs, list) else [pubs]
    return r["layerGroup"], [p["name"].split(":", 1)[-1] for p in pubs]


def workspace_exists(env, ws):
    c, r = call(env, "GET", f"/rest/workspaces/{ws}.json")
    return c == 200


def reconcile_stray_tile_layers(env, ws, group, settle_sec=3):
    """GeoServer re-creates a per-layer tile layer in the background after a layer is published. Only the group
    should be tiled/advertised, so delete the others. Run after every add, and as a periodic sweep.
    Returns the list of deleted tile layers."""
    time.sleep(settle_sec)
    deleted = []
    for _ in range(2):  # second pass catches entries created while the first pass ran
        # Never touch other services: a workspace can hold several layer groups, each with its own tile layer.
        c, g = call(env, "GET", f"/rest/workspaces/{ws}/layergroups.json")
        lg = g.get("layerGroups") if isinstance(g, dict) else None
        if c != 200 or lg is None:
            raise RuntimeError(f"cannot list layer groups for {ws} (HTTP {c}); refusing to sweep tile layers blindly")
        groups = {x["name"] for x in lg["layerGroup"]} if isinstance(lg, dict) else set()
        r = call(env, "GET", "/gwc/rest/layers.json")[1]
        names = [x if isinstance(x, str) else x.get("name") for x in (r if isinstance(r, list) else [])]
        stray = [n for n in names if n and n.startswith(f"{ws}:") and n.split(":", 1)[1] not in groups]
        for n in stray:
            call(env, "DELETE", f"/gwc/rest/layers/{n}.json")
            deleted.append(n)
        if not stray:
            break
        time.sleep(settle_sec)
    return deleted


def add_cog(env, ws, group, tile, blob_path, template=TEMPLATE_STORE, progress=None, create_workspace=False, refresh=False):
    """blob_path: path inside the sourceimagery container, e.g. 'Customer/project/tile-RGB.tif'.
    A COG already in the group is skipped, unless refresh=True: then its extent/truncate/seed are redone (repairs a failed add
    or picks up a replaced file).
    progress(step, status, seconds=None, detail=None) is called as each step starts ('running') and ends ('done').
    Returns a metrics dict."""
    L = f"{ws}:{group}"
    m = {"tile": tile, "steps": {}}
    T = time.time()
    clock = {}

    def start(name):
        clock[name] = time.time()
        if progress:
            progress(name, "running")

    def done(name, detail=None):
        m["steps"][name] = round(time.time() - clock[name], 2)
        if progress:
            progress(name, "done", m["steps"][name], detail)

    # 0. workspace
    start("workspace")
    if not workspace_exists(env, ws):
        if not create_workspace:
            raise RuntimeError(f"workspace '{ws}' does not exist (tick 'create workspace' to create it)")
        c, r = call(env, "POST", "/rest/workspaces", {"workspace": {"name": ws}})
        if c != 201:
            raise RuntimeError(f"could not create workspace {ws}: {c} {str(r)[:200]}")
        m["workspace_created"] = True
    done("workspace", "created" if m.get("workspace_created") else "exists")

    state = group_state(env, ws, group)
    already = bool(state and tile in state[1])
    if already and not refresh:
        m["skipped"] = "already a member"
        return m

    # 1. publish (store, coverage, layer), hidden from WMS listings
    start("publish")
    src = call(env, "GET", f"/rest/workspaces/{template[0]}/coveragestores/{template[1]}.json")[1]["coverageStore"]
    stem = blob_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    if call(env, "GET", f"/rest/workspaces/{ws}/coveragestores/{tile}.json")[0] != 200:
        sc, _ = call(env, "POST", f"/rest/workspaces/{ws}/coveragestores", {"coverageStore": {
            "name": tile, "type": "GeoTIFF", "enabled": True, "workspace": {"name": ws},
            "connectionParameters": src["connectionParameters"], "metadata": src["metadata"],
            "url": ACCT + urllib.parse.quote(blob_path)}})  # the path MUST be URL-encoded (spaces break the reader)
        cc, cr = call(env, "POST", f"/rest/workspaces/{ws}/coveragestores/{tile}/coverages", {"coverage": {
            "name": tile, "nativeName": stem, "nativeCoverageName": stem, "title": tile,
            "projectionPolicy": "FORCE_DECLARED", "advertised": False}})
        if sc != 201 or cc != 201:
            if sc == 201:  # we created the store, but the file is unreadable: leave nothing half-built
                call(env, "DELETE", f"/rest/workspaces/{ws}/coveragestores/{tile}?recurse=true")
            raise RuntimeError(f"publish failed (store {sc}, coverage {cc}): {str(cr)[:200]} - is the blob path readable?")
    cov = call(env, "GET", f"/rest/workspaces/{ws}/coveragestores/{tile}/coverages/{tile}.json")[1]["coverage"]
    fp = bbox_to_3857(cov["nativeBoundingBox"], int(cov["srs"].split(":")[1]))
    m["footprint_3857"], m["srs"] = fp, cov["srs"]
    done("publish", cov["srs"])

    # 2. add to the group; GeoServer does NOT recompute bounds, so set them = union(existing, footprint) in EPSG:3857
    start("group_update")
    if already:  # refresh: membership is unchanged; make sure the bounds still cover this COG
        g, members = state
        b = g["bounds"]
        bounds = [min(b["minx"], fp[0]), min(b["miny"], fp[1]), max(b["maxx"], fp[2]), max(b["maxy"], fp[3])]
        if bounds != [b["minx"], b["miny"], b["maxx"], b["maxy"]]:
            g["bounds"] = {"minx": bounds[0], "miny": bounds[1], "maxx": bounds[2], "maxy": bounds[3],
                           "crs": {"@class": "projected", "$": "EPSG:3857"}}
            call(env, "PUT", f"/rest/workspaces/{ws}/layergroups/{group}", {"layerGroup": g})
        m["group_action"], ok = "refreshed (already a member)", True
    elif state is None:
        bounds = fp
        body = {"layerGroup": {"name": group, "title": group, "mode": "SINGLE", "workspace": {"name": ws},
                               "publishables": {"published": [{"@type": "layer", "name": f"{ws}:{tile}"}]},
                               "styles": {"style": [{"name": "raster"}]},
                               "bounds": {"minx": bounds[0], "miny": bounds[1], "maxx": bounds[2], "maxy": bounds[3],
                                          "crs": {"@class": "projected", "$": "EPSG:3857"}}}}
        c, r = call(env, "POST", f"/rest/workspaces/{ws}/layergroups", body)
        ok, m["group_action"] = c == 201, "created"
    else:
        g, members = state
        b = g["bounds"]
        bounds = [min(b["minx"], fp[0]), min(b["miny"], fp[1]), max(b["maxx"], fp[2]), max(b["maxy"], fp[3])]
        g["publishables"] = {"published": [{"@type": "layer", "name": f"{ws}:{x}"} for x in members + [tile]]}
        g["styles"] = {"style": [{"name": "raster"} for _ in members + [tile]]}
        g["bounds"] = {"minx": bounds[0], "miny": bounds[1], "maxx": bounds[2], "maxy": bounds[3],
                       "crs": {"@class": "projected", "$": "EPSG:3857"}}
        c, r = call(env, "PUT", f"/rest/workspaces/{ws}/layergroups/{group}", {"layerGroup": g})
        ok, m["group_action"] = c == 200, f"updated ({len(members)}->{len(members) + 1} members)"
    if not ok:
        raise RuntimeError(f"group {m['group_action']} failed {c} {str(r)[:200]}")
    m["members_after"] = len(state[1]) if already else (len(state[1]) if state else 0) + 1
    m["group_bounds_3857"] = bounds
    done("group_update", m["group_action"])

    # 3. tile layer: EPSG:3857 only, PNG only, extent = group bounds (not auto-updated when members are added)
    start("tile_config")
    c, r = set_tile_layer_xml(env, L, bounds, formats=("image/png",), gridset="EPSG:3857", expire_clients=EXPIRE_CLIENTS)
    if c != 200:
        raise RuntimeError(f"tile layer config failed {c} {str(r)[:200]}")
    done("tile_config")

    # 4. truncate the new footprint (all zooms), 5. seed what is missing there (z0-15)
    start("truncate")
    seed_request(env, L, "truncate", fp, TRUNCATE_ZOOM[0], TRUNCATE_ZOOM[1], threads=1)
    wait_seed_idle(env, L)
    done("truncate")
    start("seed")
    seed_request(env, L, "seed", fp, SEED_ZOOM[0], SEED_ZOOM[1], threads=4)
    m["tiles_job_total"] = wait_seed_idle(env, L)
    done("seed", f"{m['tiles_job_total']} tiles")

    # 6. only the group may be tiled/advertised
    start("reconcile")
    m["stray_tile_layers_removed"] = reconcile_stray_tile_layers(env, ws, group)
    done("reconcile", f"{len(m['stray_tile_layers_removed'])} removed")

    m["total_sec"] = round(time.time() - T, 2)
    return m
