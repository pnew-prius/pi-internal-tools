"""Live tests against the real DEV GeoServer. Opt in:   set WMTS_LIVE=1 ; python -m pytest live_tests -m live -v
Each test gets a brand-new throwaway workspace (name never on prod) that is removed afterwards with remove_service,
and the shared tile cache is checked for leftover tiles."""
import json
import os
import subprocess
import sys
import tempfile
import uuid

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.environ.setdefault("AZURE_EXTENSION_DIR", os.path.join(tempfile.gettempdir(), "azext_empty"))
os.makedirs(os.environ["AZURE_EXTENSION_DIR"], exist_ok=True)

from add_cog import group_state  # noqa: E402
from gs_client import call  # noqa: E402
from remove_service import remove_service  # noqa: E402


def pytest_collection_modifyitems(config, items):
    if os.environ.get("WMTS_LIVE") == "1":
        return
    skip = pytest.mark.skip(reason="live tests are opt-in: set WMTS_LIVE=1")
    for it in items:
        it.add_marker(skip)


def blob(n):
    """The staged test COGs: Prius Intelli/automation-test/wmts/ww26-NN-RGB.tif"""
    return f"Prius Intelli/automation-test/wmts/ww26-{n:02d}-RGB.tif"


def tiles_in_cache(gwc_id):
    p = subprocess.run(f'az storage blob list --account-name pigeoserverprod --container-name tilecache --prefix "{gwc_id}/" '
                       '--auth-mode login --num-results 500000 --query "length(@)" -o tsv', capture_output=True, text=True, shell=True)
    return int((p.stdout or "0").strip() or 0)


@pytest.fixture
def ws():
    name = "LT" + uuid.uuid4().hex[:7].upper()
    prod = {w["name"] for w in call("prod", "GET", "/rest/workspaces.json", allow_prod=True)[1]["workspaces"]["workspace"]}
    assert name not in prod
    assert call("dev", "POST", "/rest/workspaces", {"workspace": {"name": name}})[0] == 201
    yield name
    # teardown: remove every service properly (truncate, delete), then the workspace, then prove no tiles were left
    leaks = {}
    ids = {}
    c, r = call("dev", "GET", f"/rest/workspaces/{name}/layergroups.json")
    lg = r.get("layerGroups") if isinstance(r, dict) else None
    for g in ([x["name"] for x in lg["layerGroup"]] if isinstance(lg, dict) else []):
        try:
            ids[g] = remove_service("dev", name, g).get("gwc_id")
        except Exception as e:  # keep cleaning even if one service is broken
            ids[g] = None
            leaks[g] = f"remove_service failed: {e}"
    call("dev", "DELETE", f"/rest/workspaces/{name}?recurse=true", timeout=300)
    for g, gid in ids.items():
        if gid and tiles_in_cache(gid):
            leaks[g] = f"{tiles_in_cache(gid)} tiles left in the shared cache"
    assert not leaks, f"cleanup problems in {name}: {leaks}"
