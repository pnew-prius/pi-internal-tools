"""Guards against the shared-tile-cache hazard: dev and prod write to the SAME GWC blob container, so a dev job on a
workspace name that also exists on prod could truncate/seed prod's tiles."""
import time

from gs_client import call

_cache = {"at": 0.0, "names": set()}
TTL = 300


def prod_workspaces():
    """Names of prod workspaces (read-only listing, cached 5 min). Raises if prod cannot be read: fail closed."""
    if time.time() - _cache["at"] < TTL and _cache["names"]:
        return _cache["names"]
    c, r = call("prod", "GET", "/rest/workspaces.json", allow_prod=True)
    if c != 200 or not isinstance(r, dict):
        raise RuntimeError(f"cannot read prod workspaces to run the safety check (HTTP {c})")
    ws = r.get("workspaces")
    names = {w["name"] for w in ws["workspace"]} if isinstance(ws, dict) else set()
    _cache.update(at=time.time(), names=names)
    return names


def assert_not_on_prod(env, workspace):
    if env == "prod":
        return
    if workspace in prod_workspaces():
        raise PermissionError(f"Workspace '{workspace}' also exists on prod, and dev and prod share one tile cache. "
                              "Use a different workspace name for dev work.")
