import json
import time

import pytest

import app as app_mod
import instance_sync as isync
from jobs import JobManager
from store import JsonlStore

SECRET = "s3cret-geoserver-pw"
TARGET = "vmss:RG_X/geoserver-vmss"


class FakeArm:
    """Stands in for Azure Resource Manager: instance list, managed run commands, restart, health."""

    def __init__(self, n=2, exit_code=0, put_status=201, unhealthy_polls=1):
        self.calls, self.n, self.exit_code, self.put_status = [], n, exit_code, put_status
        self.unhealthy_polls, self.polls = unhealthy_polls, 0

    def __call__(self, method, url, body=None, timeout=60):
        self.calls.append((method, url, body))
        if method == "GET" and "/runCommands?" in url:
            return 200, {"value": []}          # nothing left: the asynchronous delete has finished
        if "/runCommands/" in url:
            if method == "PUT":
                return self.put_status, {} if self.put_status < 300 else {"error": "AuthorizationFailed"}
            if method == "GET":
                ok = self.exit_code == 0
                return 200, {"properties": {"provisioningState": "Succeeded", "instanceView": {
                    "executionState": "Succeeded" if ok else "Failed", "exitCode": self.exit_code,
                    "output": "reload=200 gwc_reload=200 base=http://localhost:8080" if ok else "reload failed on every known base URL (last HTTP 401)"}}}
            return 200, None
        if method == "GET" and url.split("?")[0].endswith("/virtualMachines"):
            return 200, {"value": [{"instanceId": str(i)} for i in range(self.n)]}
        if method == "POST" and "/restart" in url:
            return 202, None
        if method == "GET" and "/instanceView" in url:
            self.polls += 1
            healthy = self.polls > self.unhealthy_polls
            return 200, {"statuses": [{"code": "PowerState/running"}], "vmHealth": {"status": {"code": "HealthState/healthy" if healthy else "HealthState/unhealthy"}}}
        return 404, "unhandled"


@pytest.fixture
def arm(monkeypatch):
    f = FakeArm()
    monkeypatch.setattr(isync, "_arm", f)
    monkeypatch.setattr(isync.time, "sleep", lambda *_: None)
    return f


def test_reload_runs_on_every_instance_in_parallel_without_a_restart(arm):
    r = isync.sync("reload", SECRET, TARGET)
    puts = [c for c in arm.calls if c[0] == "PUT"]
    assert r["instances"] == 2 and "no restart" in r["detail"] and len(puts) == 2
    assert sorted(("virtualMachines/0/" in c[1], "virtualMachines/1/" in c[1]) for c in puts) == [(False, True), (True, False)]   # one each
    assert not [c for c in arm.calls if c[0] == "POST"]                                                                 # nothing was restarted


def test_the_password_is_a_protected_parameter_and_never_in_the_script(arm):
    isync.sync("reload", SECRET, TARGET)
    body = [c for c in arm.calls if c[0] == "PUT"][0][2]["properties"]
    assert body["protectedParameters"] == [{"name": "GSPW", "value": SECRET}]
    assert SECRET not in json.dumps(body["source"]) and "$GSPW" in body["source"]["script"]
    assert "curl" in body["source"]["script"] and "-u " not in body["source"]["script"]    # credentials via stdin config, not argv


def test_every_run_command_is_deleted_afterwards_even_when_the_reload_fails(arm):
    arm.exit_code = 3
    with pytest.raises(isync.SyncError, match="reload failed on 2 of 2 instance"):
        isync.sync("reload", SECRET, TARGET)
    kinds = [c[0] for c in arm.calls if "/runCommands/" in c[1]]
    assert kinds.count("PUT") == 2 and kinds.count("DELETE") == 2                     # every instance attempted, every run command cleaned up


def test_it_says_so_when_azure_is_slow_to_delete_the_run_command(monkeypatch):
    f = FakeArm()
    orig = f.__call__
    monkeypatch.setattr(isync, "_arm", lambda m, u, b=None, timeout=60: (200, {"value": [{"name": "wmts-reload-abc"}]}) if (m == "GET" and "/runCommands?" in u) else f(m, u, b))
    clock = {"t": 0.0}
    monkeypatch.setattr(isync.time, "time", lambda: clock.__setitem__("t", clock["t"] + 50) or clock["t"])
    monkeypatch.setattr(isync.time, "sleep", lambda *_: None)
    r = isync.sync("reload", SECRET, TARGET)
    assert "still deleting the temporary run command" in r["detail"]                  # reported, but the reload itself succeeded


def test_missing_permission_gives_an_actionable_error(monkeypatch):
    f = FakeArm(put_status=403)
    monkeypatch.setattr(isync, "_arm", f)
    with pytest.raises(isync.SyncError, match="Virtual Machine Contributor"):
        isync.sync("reload", SECRET, TARGET)


def test_rolling_restart_waits_for_each_instance_to_be_healthy_before_the_next(arm):
    r = isync.sync("restart", SECRET, TARGET)
    seq = [("restart" if c[0] == "POST" else "health") for c in arm.calls if c[0] == "POST" or "/instanceView" in c[1]]
    assert r["instances"] == 2 and "one at a time" in r["detail"]
    assert seq.index("restart") < seq.index("health") and seq.count("restart") == 2
    first_restart, second_restart = [i for i, s in enumerate(seq) if s == "restart"]
    assert "health" in seq[first_restart:second_restart]                              # healthy check happened between the two restarts
    assert [c[2] for c in arm.calls if c[0] == "POST"] == [{"instanceIds": ["0"]}, {"instanceIds": ["1"]}]


def test_restart_stops_if_an_instance_never_becomes_healthy(monkeypatch):
    f = FakeArm(unhealthy_polls=10**9)
    monkeypatch.setattr(isync, "_arm", f)
    clock = {"t": 0.0}
    monkeypatch.setattr(isync.time, "time", lambda: clock.__setitem__("t", clock["t"] + 400) or clock["t"])
    monkeypatch.setattr(isync.time, "sleep", lambda *_: None)
    with pytest.raises(isync.SyncError, match="remaining instances were NOT restarted"):
        isync.sync("restart", SECRET, TARGET)
    assert len([c for c in f.calls if c[0] == "POST"]) == 1


def test_none_unknown_mode_no_instances_and_bad_target(arm):
    assert isync.sync("none", SECRET, None)["detail"] == "skipped by choice"
    with pytest.raises(isync.SyncError, match="unknown sync mode"):
        isync.sync("explode", SECRET, TARGET)
    arm.n = 0
    assert "nothing to update" in isync.sync("reload", SECRET, TARGET)["detail"]
    for bad in (None, "", "vmss:onlyone", "rm -rf /", "vmss:rg/na me"):
        with pytest.raises(isync.SyncError):
            isync.parse_target(bad)


# ---------------------------------------------------------------------- inside jobs: once per job, after all seeding
ONE = "Cust/proj/t-01-RGB.tif"
THREE = "Cust/proj/t-01-RGB.tif\nCust/proj/t-02-RGB.tif\nCust/proj/t-03-RGB.tif"
BOSS = {"X-MS-CLIENT-PRINCIPAL-NAME": "boss@priusintelli.com"}


class Syncs:
    def __init__(self, fail=None):
        self.calls, self.fail = [], fail

    def __call__(self, mode, progress=None):
        self.calls.append((mode, time.time()))
        if progress:
            progress("reloading instance 0 (1 of 1)")
        if self.fail:
            raise isync.SyncError(self.fail)
        return {"mode": mode, "instances": 2, "detail": f"{mode}: 2 instance(s) updated", "seconds": 0.1}


def make(fake, monkeypatch, tmp_path, sync):
    monkeypatch.setattr(app_mod, "call", fake.call)
    monkeypatch.delenv("WMTS_LOCAL", raising=False)
    monkeypatch.setenv("WMTS_ENVS", "dev,prod")
    monkeypatch.setenv("WMTS_PROD_USERS", "boss@priusintelli.com")
    mgr = JobManager(JsonlStore(str(tmp_path / "h.jsonl")), sync_fn=sync)
    return app_mod.create_app(mgr).test_client(), mgr


def run(c, path, body):
    r = c.post(path, json=body, headers=BOSS)
    assert r.status_code == 202, r.get_json()
    jid = r.get_json()["job"]["id"]
    deadline = time.time() + 20          # time-based: the shared fixture turns time.sleep into a no-op
    while time.time() < deadline:
        j = c.get(f"/api/jobs/{jid}", headers=BOSS).get_json()["job"]
        if j["status"] in ("done", "partial", "failed"):
            return j
        time.sleep(0.05)
    raise AssertionError("job did not finish")


PBODY = {"env": "prod", "workspace": "PW", "group": "Svc", "blob_text": THREE, "create_workspace": True, "confirm_prod": True}


def test_a_prod_job_syncs_once_after_all_cogs_not_per_cog(fake, monkeypatch, tmp_path):
    s = Syncs()
    c, mgr = make(fake, monkeypatch, tmp_path, s)
    j = run(c, "/api/jobs", PBODY)
    assert j["counts"]["done"] == 3 and len(s.calls) == 1 and s.calls[0][0] == "reload"          # once, default reload
    assert j["sync"]["status"] == "done" and "updated" in j["sync"]["detail"]
    finished = max(i["finished"] for i in j["items"] if i.get("finished"))
    assert s.calls[0][1] >= finished                                                              # after the last COG was seeded
    assert any(r["tile"].startswith("(update customer-facing") and r["status"] == "done" for r in mgr.store.recent())


def test_the_restart_mode_is_passed_through_and_none_skips_loudly(fake, monkeypatch, tmp_path):
    s = Syncs()
    c, mgr = make(fake, monkeypatch, tmp_path, s)
    run(c, "/api/jobs", dict(PBODY, sync_mode="restart"))
    assert s.calls[-1][0] == "restart"
    n = len(s.calls)
    j = run(c, "/api/jobs", dict(PBODY, group="Svc2", sync_mode="none"))
    assert len(s.calls) == n and j["sync"]["status"] == "skipped" and "will NOT see" in j["sync"]["detail"]


def test_dev_jobs_never_sync(fake, monkeypatch, tmp_path):
    s = Syncs()
    c, mgr = make(fake, monkeypatch, tmp_path, s)
    j = run(c, "/api/jobs", {"env": "dev", "workspace": "DEVWS", "group": "Svc", "blob_text": ONE, "create_workspace": True})
    assert not s.calls and j["sync"]["status"] == "skipped" and "not needed on dev" in j["sync"]["detail"]


def test_nothing_changed_means_no_sync(fake, monkeypatch, tmp_path):
    s = Syncs()
    c, mgr = make(fake, monkeypatch, tmp_path, s)
    run(c, "/api/jobs", PBODY)
    s.calls.clear()
    j = run(c, "/api/jobs", PBODY)                    # everything already in the service -> all skipped
    assert j["counts"]["done"] == 0 and not s.calls and j["sync"]["status"] == "skipped"


def test_a_sync_failure_is_reported_but_never_fails_the_cogs(fake, monkeypatch, tmp_path):
    c, mgr = make(fake, monkeypatch, tmp_path, Syncs(fail="Azure refused the run command (HTTP 403)"))
    j = run(c, "/api/jobs", PBODY)
    assert j["status"] == "done" and j["counts"]["done"] == 3                                     # COGs fine
    assert j["sync"]["status"] == "failed" and "may NOT see this change" in j["sync"]["detail"] and "403" in j["sync"]["detail"]
    assert any(r["tile"].startswith("(update customer-facing") and r["status"] == "failed" for r in mgr.store.recent())


def test_removing_a_prod_service_also_syncs_once(fake, monkeypatch, tmp_path):
    s = Syncs()
    c, mgr = make(fake, monkeypatch, tmp_path, s)
    run(c, "/api/jobs", PBODY)
    s.calls.clear()
    j = run(c, "/api/remove", {"env": "prod", "workspace": "PW", "group": "Svc", "confirm": "PW:Svc"})
    assert len(s.calls) == 1 and j["sync"]["status"] == "done"


def test_bad_sync_mode_is_rejected_and_the_password_is_nowhere_in_job_data(fake, monkeypatch, tmp_path):
    c, mgr = make(fake, monkeypatch, tmp_path, Syncs())
    assert c.post("/api/jobs", json=dict(PBODY, sync_mode="reboot-everything"), headers=BOSS).status_code == 400
    j = run(c, "/api/jobs", PBODY)
    assert SECRET not in json.dumps(j) and SECRET not in (tmp_path / "h.jsonl").read_text()
