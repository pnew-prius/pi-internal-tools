"""Make the CUSTOMER-FACING prod GeoServer instances see changes the app made on the admin node.

On prod, REST writes go to the admin VM (imageadmin); customers are served by the scale set behind imageservices. Those are different
GeoServer processes sharing a data directory, so the scale-set instances keep their old in-memory config until reloaded or restarted.
Two modes, run ONCE at the end of a job (never per COG):
  reload   (default)  per instance, zero downtime: Azure managed Run Command executes GeoServer's REST reload on the instance itself.
                      The GeoServer password travels as a PROTECTED parameter (never in the script), and the run command is deleted afterwards.
  restart             rolling restart, one instance at a time, waiting for each to report healthy (brief outage if there is one instance).
Needs Azure RBAC for the app's identity (Virtual Machine Contributor on the scale set). Config:
  WMTS_PROD_SYNC_TARGET = "vmss:<resource-group>/<scale-set-name>"   (a plain VM is accepted for testing: "vm:<rg>/<name>")
  WMTS_SUBSCRIPTION     = subscription id (default: the Prius Intelli primary subscription)
"""
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import requests

ARM = "https://management.azure.com"
API = "2024-07-01"
DEFAULT_SUBSCRIPTION = "fa7f37c0-b488-4dee-81b1-a00a4e0da4bd"
LOCATION = os.environ.get("WMTS_LOCATION", "southcentralus")
_sync_lock = threading.Lock()   # one sync/restart at a time, across all jobs
_token = {"value": None, "exp": 0}


class SyncError(RuntimeError):
    pass


RELOAD_SCRIPT = r'''
set -u
ok=""
code="000"
for base in "http://localhost:8080" "http://localhost:8080/geoserver"; do
  code=$(printf 'user = "geoadmin:%s"\n' "$GSPW" | curl -s -o /dev/null -w '%{http_code}' -K - -X POST "$base/rest/reload")
  if [ "$code" = "200" ]; then ok="$base"; break; fi
done
if [ -z "$ok" ]; then echo "reload failed on every known base URL (last HTTP $code)"; exit 3; fi
gwc=$(printf 'user = "geoadmin:%s"\n' "$GSPW" | curl -s -o /dev/null -w '%{http_code}' -K - -X POST "$ok/gwc/rest/reload")
echo "reload=200 gwc_reload=$gwc base=$ok"
'''


def _arm(method, url, body=None, timeout=60):
    """One call to Azure Resource Manager with the app's identity. Returns (status, json_or_text)."""
    if time.time() > _token["exp"] - 120:
        try:
            from azure.identity import DefaultAzureCredential
            t = DefaultAzureCredential().get_token(ARM + "/.default")
        except Exception as e:
            raise SyncError(f"could not get an Azure token for the instance sync ({type(e).__name__}): {e}") from e
        _token.update(value=t.token, exp=t.expires_on)
    r = requests.request(method, url, json=body, headers={"Authorization": "Bearer " + _token["value"]}, timeout=timeout)
    try:
        return r.status_code, (r.json() if r.text.strip() else None)
    except ValueError:
        return r.status_code, r.text


def parse_target(spec):
    m = re.fullmatch(r"(vmss|vm):([\w.-]+)/([\w.-]+)", (spec or "").strip())
    if not m:
        raise SyncError("WMTS_PROD_SYNC_TARGET is not set or malformed (expected vmss:<resource-group>/<scale-set>)")
    return m.group(1), m.group(2), m.group(3)


def _base(target):
    kind, rg, name = target
    sub = os.environ.get("WMTS_SUBSCRIPTION", DEFAULT_SUBSCRIPTION)
    root = f"{ARM}/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Compute"
    return root, (f"{root}/virtualMachineScaleSets/{name}" if kind == "vmss" else f"{root}/virtualMachines/{name}")


def list_instances(target):
    """Instance ids of the scale set (or [None] for a plain VM)."""
    kind, _, _ = target
    if kind == "vm":
        return [None]
    _, res = _base(target)
    c, r = _arm("GET", f"{res}/virtualMachines?api-version={API}")
    if c != 200 or not isinstance(r, dict):
        raise SyncError(f"could not list scale set instances (HTTP {c}): {str(r)[:200]}")
    return [v["instanceId"] for v in r.get("value", [])]


def _instance_path(target, instance):
    _, res = _base(target)
    return res if instance is None else f"{res}/virtualMachines/{instance}"


def run_reload(target, instance, password, timeout=240):
    """Reload GeoServer's configuration ON one instance. The password is a protected parameter; the run command is always deleted."""
    path = _instance_path(target, instance)
    name = "wmts-reload-" + uuid.uuid4().hex[:8]
    url = f"{path}/runCommands/{name}?api-version={API}"
    body = {"location": LOCATION, "properties": {
        "source": {"script": RELOAD_SCRIPT}, "protectedParameters": [{"name": "GSPW", "value": password}],
        "asyncExecution": False, "timeoutInSeconds": 120, "treatFailureAsDeploymentFailure": False}}
    try:
        c, r = _arm("PUT", url, body)
        if c not in (200, 201, 202):
            raise SyncError(f"Azure refused the run command on instance {instance} (HTTP {c}): {str(r)[:200]} - does the app have Virtual Machine Contributor on the scale set?")
        t0 = time.time()
        while True:
            c, r = _arm("GET", f"{url}&$expand=instanceView")
            props = (r or {}).get("properties", {}) if isinstance(r, dict) else {}
            iv = props.get("instanceView") or {}
            if props.get("provisioningState") in ("Succeeded", "Failed", "Canceled") and iv.get("executionState") in ("Succeeded", "Failed", "TimedOut", "Canceled", "Unknown"):
                break
            if time.time() - t0 > timeout:
                raise SyncError(f"reload on instance {instance} did not finish within {timeout}s")
            time.sleep(3)
        out = (iv.get("output") or "").strip()
        if iv.get("executionState") != "Succeeded" or iv.get("exitCode") not in (0, None):
            raise SyncError(f"reload failed on instance {instance}: {(out or iv.get('error') or 'no output')[:200]}")
        return out
    finally:
        try:
            _arm("DELETE", url)   # removes the script and the protected parameter from Azure
        except Exception:
            pass


def _cleanup_confirmed(target, instances, timeout=90):
    """Azure deletes run commands ASYNCHRONOUSLY. Confirm none of ours is left (the script and protected parameter live there until it is gone).
    Returns True once none remain, False if some are still listed after `timeout`."""
    t0 = time.time()
    paths = {_instance_path(target, i) for i in instances}
    while True:
        left = []
        for p in paths:
            c, r = _arm("GET", f"{p}/runCommands?api-version={API}")
            if c == 200 and isinstance(r, dict):
                left += [x["name"] for x in r.get("value", []) if x.get("name", "").startswith("wmts-reload-")]
        if not left:
            return True
        if time.time() - t0 > timeout:
            return False
        time.sleep(5)


def _healthy(target, instance):
    c, r = _arm("GET", f"{_instance_path(target, instance)}/instanceView?api-version={API}")
    if c != 200 or not isinstance(r, dict):
        return False
    health = ((r.get("vmHealth") or {}).get("status") or {}).get("code", "")
    power = [s.get("code") for s in r.get("statuses", [])]
    return "PowerState/running" in power and health == "HealthState/healthy"   # exact match: "HealthState/unhealthy" also ends in "healthy"


def rolling_restart(target, instances, progress=None, timeout=900):
    kind, rg, name = target
    for n, inst in enumerate(instances, 1):
        if progress:
            progress(f"restarting instance {inst} ({n} of {len(instances)})")
        if kind == "vmss":
            _, res = _base(target)
            c, r = _arm("POST", f"{res}/restart?api-version={API}", {"instanceIds": [inst]})
        else:
            c, r = _arm("POST", f"{_instance_path(target, None)}/restart?api-version={API}")
        if c not in (200, 202):
            raise SyncError(f"Azure refused the restart of instance {inst} (HTTP {c}): {str(r)[:200]}")
        t0 = time.time()
        time.sleep(15)   # let it actually go down before polling for healthy
        while not _healthy(target, inst):
            if time.time() - t0 > timeout:
                raise SyncError(f"instance {inst} was not healthy {timeout}s after the restart; the remaining instances were NOT restarted")
            time.sleep(10)


def sync(mode, password, target_spec=None, progress=None):
    """Run the chosen sync. Returns {'mode','instances','detail','seconds'}; raises SyncError on any failure."""
    if mode == "none":
        return {"mode": "none", "instances": 0, "detail": "skipped by choice", "seconds": 0}
    target = parse_target(target_spec if target_spec is not None else os.environ.get("WMTS_PROD_SYNC_TARGET"))
    t0 = time.time()
    with _sync_lock:
        instances = list_instances(target)
        if not instances:
            return {"mode": mode, "instances": 0, "detail": "no running instances, nothing to update (new instances read the shared config when they start)", "seconds": round(time.time() - t0, 1)}
        notes = []
        if mode == "reload":
            # reloading is zero-downtime and independent per instance, so do them in parallel (each Run Command takes ~1 min in Azure)
            if progress:
                progress(f"reloading {len(instances)} instance(s) in parallel")
            errors = {}
            with ThreadPoolExecutor(max_workers=len(instances)) as ex:
                futures = {inst: ex.submit(run_reload, target, inst, password) for inst in instances}
                for inst, f in futures.items():
                    try:
                        notes.append(f.result())
                    except SyncError as e:
                        errors[inst] = str(e)
            if errors:
                raise SyncError(f"reload failed on {len(errors)} of {len(instances)} instance(s): " + " | ".join(errors.values()))
            clean = _cleanup_confirmed(target, instances)
            detail = (f"configuration reloaded on {len(instances)} instance(s), no restart"
                      + ("" if clean else "; NOTE: Azure was still deleting the temporary run command after 90 s"))
        elif mode == "restart":
            rolling_restart(target, instances, progress)
            detail = f"{len(instances)} instance(s) restarted one at a time"
        else:
            raise SyncError(f"unknown sync mode {mode!r}")
    return {"mode": mode, "instances": len(instances), "detail": detail, "seconds": round(time.time() - t0, 1)}
