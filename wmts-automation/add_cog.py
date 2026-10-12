"""Add ONE COG to a WMTS service (a GWC-tiled GeoServer layer group).

Stateless: everything is read from GeoServer, so it can run now, later, or resume after a failure.
Order matters: publish -> add to group -> group bounds -> tile extent -> bbox truncate -> bbox seed -> stray sweep.
"""
import os
import random
import time
import urllib.parse

from gs_client import call
from gwc import bbox_to_3857, seed_request, set_tile_layer_xml, wait_seed_idle

ACCT = "cog://https://pigeoserverprod.blob.core.windows.net/sourceimagery/"
# Existing store whose Azure credential block (encrypted account key + Azure range reader) is copied to new stores.
TEMPLATE_STORE = tuple(os.environ.get("WMTS_TEMPLATE_STORE", "COPE-S26/codes26-01").split("/", 1))
SEED_ZOOM = (0, 15)       # pre-seed range
TRUNCATE_ZOOM = (0, 24)   # truncate must cover EVERY zoom: live-rendered z16+ tiles go stale at seams too
EXPIRE_CLIENTS = int(os.environ.get("WMTS_EXPIRE_CLIENTS", "600"))  # seconds browsers may reuse a tile (0 = no-cache); short because tiles change when COGs are added
STEPS = ["workspace", "publish", "group_update", "tile_config", "truncate", "seed", "reconcile"]
SERVICE_TYPES = ("wmts", "wms")   # wmts = cached tiles (seeded z0-15); wms = live render, no tile cache
TYPE_KEY = "wmtsbuilder.service_type"
TILE_STEPS = ("tile_config", "truncate", "seed")


def group_marker(g):
    """The service type recorded by this app on the group, or None for groups not created by it."""
    entries = ((g.get("metadata") or {}).get("entry")) or []
    entries = entries if isinstance(entries, list) else [entries]
    for e in entries:
        if e.get("@key") == TYPE_KEY:
            return e.get("$")
    return None


def group_service_type(env, ws, group, g):
    """Type recorded on the group when it was created; for groups made by hand, WMTS if it has a tile layer else WMS."""
    entries = ((g.get("metadata") or {}).get("entry")) or []
    entries = entries if isinstance(entries, list) else [entries]
    for e in entries:
        if e.get("@key") == TYPE_KEY:
            return e.get("$")
    return "wmts" if call(env, "GET", f"/gwc/rest/layers/{ws}:{group}.json")[0] == 200 else "wms"


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


def _covers(bounds, fp, tol=1.0):
    return (bounds["minx"] <= fp[0] + tol and bounds["miny"] <= fp[1] + tol and bounds["maxx"] >= fp[2] - tol and bounds["maxy"] >= fp[3] - tol)


def _group_bounds_json(b):
    return {"minx": b[0], "miny": b[1], "maxx": b[2], "maxy": b[3], "crs": {"@class": "projected", "$": "EPSG:3857"}}


def put_member_in_group(env, ws, group, tile, fp, service, attempts=6):
    """Add `tile` to the group (creating it if needed) safely against a concurrent writer (another app instance).
    GeoServer has no compare-and-swap, so: re-read before every write, retry a lost creation race as an update, and
    VERIFY afterwards that our member is still there and the bounds still cover our footprint (a concurrent PUT of a
    stale copy can drop it). Returns (action, bounds[minx,miny,maxx,maxy], member_count)."""
    last = None
    for _ in range(attempts):
        state = group_state(env, ws, group)
        if state is None:
            bounds, action = list(fp), "created"
            body = {"layerGroup": {"name": group, "title": group, "mode": "SINGLE", "workspace": {"name": ws},
                                   "publishables": {"published": [{"@type": "layer", "name": f"{ws}:{tile}"}]},
                                   "styles": {"style": [{"name": "raster"}]},
                                   "metadata": {"entry": [{"@key": TYPE_KEY, "$": service}]}, "bounds": _group_bounds_json(bounds)}}
            c, r = call(env, "POST", f"/rest/workspaces/{ws}/layergroups", body)
            ok = c == 201
        else:
            g, members = state
            b = g["bounds"]
            bounds = [min(b["minx"], fp[0]), min(b["miny"], fp[1]), max(b["maxx"], fp[2]), max(b["maxy"], fp[3])]
            new = members if tile in members else members + [tile]
            action = "refreshed (already a member)" if tile in members else f"updated ({len(members)}->{len(new)} members)"
            g["publishables"] = {"published": [{"@type": "layer", "name": f"{ws}:{x}"} for x in new]}
            g["styles"] = {"style": [{"name": "raster"} for _ in new]}
            g["bounds"] = _group_bounds_json(bounds)
            c, r = call(env, "PUT", f"/rest/workspaces/{ws}/layergroups/{group}", {"layerGroup": g})
            ok = c == 200
        if ok:
            chk = group_state(env, ws, group)
            if chk and tile in chk[1] and _covers(chk[0]["bounds"], fp):
                b = chk[0]["bounds"]
                return action, [b["minx"], b["miny"], b["maxx"], b["maxy"]], len(chk[1])
            last = "our COG was overwritten by a concurrent update"
        else:
            last = f"HTTP {c} {str(r)[:160]}"
        time.sleep(random.uniform(0.2, 0.8))  # back off a little, then re-read and try again
    raise RuntimeError(f"could not add {tile} to {ws}:{group} after {attempts} attempts ({last})")


def sync_tile_extent(env, ws, group):
    """The tile layer's extent is not updated by GeoServer when the group grows, and two concurrent writers can leave it
    too narrow (tiles outside it return 400). Make it cover the group's CURRENT bounds. Returns True if it changed."""
    st = group_state(env, ws, group)
    c, r = call(env, "GET", f"/gwc/rest/layers/{ws}:{group}.json")
    if not st or c != 200 or not isinstance(r, dict):
        return False
    b = st[0]["bounds"]
    box = [b["minx"], b["miny"], b["maxx"], b["maxy"]]
    try:
        e = r["GeoServerLayer"]["gridSubsets"][0]["extent"]["coords"]
        if e[0] <= box[0] + 1 and e[1] <= box[1] + 1 and e[2] >= box[2] - 1 and e[3] >= box[3] - 1:
            return False
    except (KeyError, IndexError, TypeError):
        pass
    set_tile_layer_xml(env, f"{ws}:{group}", box, formats=("image/png",), gridset="EPSG:3857", expire_clients=EXPIRE_CLIENTS)
    return True


def reconcile_stray_tile_layers(env, ws, group, settle_sec=3, include_group=False):
    """GeoServer re-creates a per-layer tile layer in the background after a layer is published. Only the group
    should be tiled/advertised, so delete the others. Run after every add, and as a periodic sweep.
    include_group=True (WMS-only services) also removes the group's own tile layer, which GeoServer auto-creates.
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
        stray = [n for n in names if n and n.startswith(f"{ws}:") and (n.split(":", 1)[1] not in groups or (include_group and n == f"{ws}:{group}"))]
        for n in stray:
            call(env, "DELETE", f"/gwc/rest/layers/{n}.json")
            deleted.append(n)
        if not stray:
            break
        time.sleep(settle_sec)
    return deleted


def add_cog(env, ws, group, tile, blob_path, template=TEMPLATE_STORE, progress=None, create_workspace=False, refresh=False, service="wmts"):
    """blob_path: path inside the sourceimagery container, e.g. 'Customer/project/tile-RGB.tif'.
    A COG already in the group is skipped, unless refresh=True: then its extent/truncate/seed are redone (repairs a failed add
    or picks up a replaced file).
    progress(step, status, seconds=None, detail=None) is called as each step starts ('running') and ends ('done').
    service: "wmts" (cached tiles) or "wms" (live render, no tile cache). A group keeps the type it was created with.
    Returns a metrics dict."""
    if service not in SERVICE_TYPES:
        raise ValueError(f"service must be one of {SERVICE_TYPES}")
    L = f"{ws}:{group}"
    m = {"tile": tile, "steps": {}, "service": service}
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
    if state:
        existing = group_service_type(env, ws, group, state[0])
        if existing != service:
            raise RuntimeError(f"'{group}' is a {existing.upper()} service, so it cannot take a {service.upper()} add. "
                               "Use a different service name (a service keeps the type it was created with).")
    already = bool(state and tile in state[1])
    if already and not refresh:
        m["skipped"] = "already a member"
        return m

    # 1. publish (store, coverage, layer), hidden from WMS listings
    start("publish")
    c, tpl = call(env, "GET", f"/rest/workspaces/{template[0]}/coveragestores/{template[1]}.json")
    if c != 200 or not isinstance(tpl, dict):
        raise RuntimeError(f"credential template store {template[0]}/{template[1]} not found (HTTP {c}). New stores copy their Azure "
                           "credential block from it; set WMTS_TEMPLATE_STORE=workspace/store to another existing COG store.")
    src = tpl["coverageStore"]
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
    m["group_action"], bounds, m["members_after"] = put_member_in_group(env, ws, group, tile, fp, service)
    m["group_bounds_3857"] = bounds
    done("group_update", m["group_action"])

    if service == "wms":  # live render: nothing to configure, truncate or seed
        for s in TILE_STEPS:
            if progress:
                progress(s, "skipped", None, "not needed for WMS")
    else:
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
    if service == "wmts":
        m["tile_extent_resynced"] = sync_tile_extent(env, ws, group)
    m["stray_tile_layers_removed"] = reconcile_stray_tile_layers(env, ws, group, include_group=(service == "wms"))
    done("reconcile", f"{len(m['stray_tile_layers_removed'])} removed")

    m["total_sec"] = round(time.time() - T, 2)
    return m
