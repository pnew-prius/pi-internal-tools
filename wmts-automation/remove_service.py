"""Remove a service (layer group) cleanly.

Deleting a group/workspace in GeoServer does NOT delete its cached tiles (they stay in the shared tile container as
orphans), so the tile cache is truncated first. Member layers are deleted only when no other group in the workspace
still uses them (a layer can be shared by two groups).
"""
from add_cog import group_service_type, group_state
from gs_client import call
from gwc import seed_request, wait_seed_idle


def other_groups_members(env, ws, group):
    c, r = call(env, "GET", f"/rest/workspaces/{ws}/layergroups.json")
    lg = r.get("layerGroups") if isinstance(r, dict) else None
    names = [g["name"] for g in lg["layerGroup"]] if isinstance(lg, dict) else []
    used = set()
    for n in names:
        if n != group:
            st = group_state(env, ws, n)
            if st:
                used.update(st[1])
    return used


REMOVE_STEPS = ["tile_cache", "delete_group", "delete_layers", "workspace"]


def remove_service(env, ws, group, delete_layers=True, progress=None, delete_empty_workspace=False):
    """Returns a summary dict: tile layer id (for verifying no tiles remain), layers deleted/kept.
    progress(step, status, seconds=None, detail=None) as in add_cog."""
    import time

    def step(name, status, t0=None, detail=None):
        if progress:
            progress(name, status, round(time.time() - t0, 2) if t0 else None, detail)

    st = group_state(env, ws, group)
    if st is None:
        raise RuntimeError(f"service {ws}:{group} does not exist")
    g, members = st
    out = {"service": f"{ws}:{group}", "type": group_service_type(env, ws, group, g), "truncated": False}
    t = time.time()
    step("tile_cache", "running")
    c, r = call(env, "GET", f"/gwc/rest/layers/{ws}:{group}.json")
    if c == 200 and isinstance(r, dict):
        out["gwc_id"] = r["GeoServerLayer"].get("id")
        b = g["bounds"]
        box = [b["minx"], b["miny"], b["maxx"], b["maxy"]]
        # truncate every zoom (0-24) over the whole group, then wait: the delete must not race the truncate
        seed_request(env, f"{ws}:{group}", "truncate", box, 0, 24, threads=2)
        wait_seed_idle(env, f"{ws}:{group}")
        out["truncated"] = True
    step("tile_cache", "done", t, "cleared" if out["truncated"] else "none (WMS service)")
    t = time.time()
    step("delete_group", "running")
    c, r = call(env, "DELETE", f"/rest/workspaces/{ws}/layergroups/{group}")
    if c != 200:
        raise RuntimeError(f"could not delete group {ws}:{group}: {c} {str(r)[:200]}")
    step("delete_group", "done", t)
    deleted, kept = [], []
    t = time.time()
    step("delete_layers", "running")
    if delete_layers:
        shared = other_groups_members(env, ws, group)
        for m in members:
            if m in shared:
                kept.append(m)
                continue
            call(env, "DELETE", f"/gwc/rest/layers/{ws}:{m}.json")
            c, _ = call(env, "DELETE", f"/rest/workspaces/{ws}/coveragestores/{m}?recurse=true")
            (deleted if c == 200 else kept).append(m)
    out.update(layers_deleted=deleted, layers_kept=kept)
    step("delete_layers", "done", t, f"{len(deleted)} deleted, {len(kept)} kept")
    t = time.time()
    if delete_empty_workspace:
        step("workspace", "running")
        c, _ = call(env, "DELETE", f"/rest/workspaces/{ws}")   # without recurse: GeoServer refuses unless the workspace is empty
        out["workspace_deleted"] = c == 200
        step("workspace", "done", t, "deleted (it was empty)" if c == 200 else "kept (still has other content)")
    elif progress:
        progress("workspace", "skipped", None, "not requested")
    return out
