import os
import time

import pytest

import add_cog as add_cog_mod
import app as app_mod
from jobs import JobManager
from store import JsonlStore

H = {"X-MS-CLIENT-PRINCIPAL-NAME": "someone@priusintelli.com"}
BODY = {"env": "dev", "workspace": "TESTWS", "group": "Svc", "blob_path": "Cust/proj/t-01-RGB.tif", "create_workspace": True}


@pytest.fixture
def client(fake, monkeypatch, tmp_path):
    monkeypatch.setattr(app_mod, "call", fake.call)
    monkeypatch.delenv("WMTS_LOCAL", raising=False)
    mgr = JobManager(JsonlStore(str(tmp_path / "h.jsonl")))
    return app_mod.create_app(mgr).test_client(), mgr, fake


def wait(c, jid, timeout=10):
    t = time.time()
    while time.time() - t < timeout:
        j = c.get(f"/api/jobs/{jid}", headers=H).get_json()["job"]
        if j["status"] in ("done", "failed"):
            return j
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_requires_sign_in(client):
    c, *_ = client
    assert c.get("/api/me").status_code == 401 and c.post("/api/jobs", json=BODY).status_code == 401
    assert c.get("/healthz").status_code == 200                       # health probe is open


def test_local_mode_allows_dev_user(client, monkeypatch):
    c, *_ = client
    monkeypatch.setenv("WMTS_LOCAL", "1")
    assert c.get("/api/me").get_json()["user"] == "local-dev"


def test_full_job_runs_and_is_recorded_with_the_user(client):
    c, mgr, fake = client
    r = c.post("/api/jobs", json=BODY, headers=H)
    assert r.status_code == 202
    j = wait(c, r.get_json()["job"]["id"])
    assert j["status"] == "done" and j["user"] == "someone@priusintelli.com" and j["tile"] == "t-01"
    assert all(s["status"] == "done" for s in j["steps"])
    hist = c.get("/api/jobs", headers=H).get_json()["jobs"]
    assert hist and hist[0]["id"] == j["id"]                          # persisted to history


def test_failed_job_reports_error_and_frees_the_service(client):
    c, mgr, fake = client
    bad = dict(BODY, blob_path="Cust/proj/missing-RGB.tif")
    j = wait(c, c.post("/api/jobs", json=bad, headers=H).get_json()["job"]["id"])
    assert j["status"] == "failed" and "publish failed" in j["error"]
    assert c.post("/api/jobs", json=BODY, headers=H).status_code == 202   # not stuck busy


def test_second_job_on_same_service_is_rejected_while_one_runs(client):
    c, mgr, fake = client
    mgr.submit("a", "dev", "TESTWS", "Svc", "t-01", "Cust/proj/t-01-RGB.tif", run=False)   # pretend one is in flight
    r = c.post("/api/jobs", json=BODY, headers=H)
    assert r.status_code == 409 and "already running" in r.get_json()["error"]


def test_workspace_that_exists_on_prod_is_refused_for_dev(client):
    c, *_ = client
    r = c.post("/api/jobs", json=dict(BODY, workspace="COPE-S26"), headers=H)
    assert r.status_code == 403 and "share one tile cache" in r.get_json()["error"]


def test_prod_unreadable_fails_closed(client, monkeypatch):
    c, mgr, fake = client
    monkeypatch.setattr(fake, "prod_workspaces", None)               # makes the fake prod listing raise -> 503 path
    monkeypatch.setattr(app_mod.safety, "call", lambda *a, **k: (500, "boom"))
    assert c.post("/api/jobs", json=BODY, headers=H).status_code == 503


def test_prod_environment_not_enabled_by_default(client):
    c, *_ = client
    assert c.post("/api/jobs", json=dict(BODY, env="prod"), headers=H).status_code == 400


@pytest.mark.parametrize("bad", [dict(blob_path="x.tif"), dict(blob_path="a/b.tif?sig=1"), dict(workspace="a b"), dict(group="")])
def test_bad_input_is_a_400_not_a_job(client, bad):
    c, *_ = client
    assert c.post("/api/jobs", json=dict(BODY, **bad), headers=H).status_code == 400


def test_service_endpoint_reports_members_and_capabilities_url(client):
    c, *_ = client
    wait(c, c.post("/api/jobs", json=BODY, headers=H).get_json()["job"]["id"])
    s = c.get("/api/service?workspace=TESTWS&group=Svc", headers=H).get_json()
    assert s["exists"] and s["members"] == 1 and s["capabilities_url"].endswith("/TESTWS/gwc/service/wmts?REQUEST=GetCapabilities")


def test_index_page_renders_with_user(client):
    c, *_ = client
    r = c.get("/", headers=H)
    assert r.status_code == 200 and b"someone@priusintelli.com" in r.data and b"WMTS Service Builder" in r.data
