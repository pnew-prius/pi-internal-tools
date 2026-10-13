import base64
import json
import time

import pytest

import app as app_mod
import gs_client
from add_cog import group_state
from jobs import JobManager
from store import JsonlStore

BOSS = {"X-MS-CLIENT-PRINCIPAL-NAME": "boss@priusintelli.com"}
OTHER = {"X-MS-CLIENT-PRINCIPAL-NAME": "someone.else@priusintelli.com"}
ONE = "Cust/proj/t-01-RGB.tif"
PBODY = {"env": "prod", "workspace": "PW", "group": "Svc", "blob_text": ONE, "create_workspace": True, "confirm_prod": True}


def make(fake, monkeypatch, tmp_path, envs="dev,prod", users="boss@priusintelli.com", group="", maxb=None):
    monkeypatch.setattr(app_mod, "call", fake.call)
    monkeypatch.delenv("WMTS_LOCAL", raising=False)
    monkeypatch.setenv("WMTS_ENVS", envs)
    monkeypatch.setenv("WMTS_PROD_USERS", users)
    monkeypatch.setenv("WMTS_PROD_GROUP_ID", group)
    if maxb:
        monkeypatch.setenv("WMTS_PROD_MAX_BATCH", str(maxb))
    mgr = JobManager(JsonlStore(str(tmp_path / "h.jsonl")))
    return app_mod.create_app(mgr).test_client(), mgr


def wait(c, jid, headers, timeout=15):
    t = time.time()
    while time.time() - t < timeout:
        j = c.get(f"/api/jobs/{jid}", headers=headers).get_json()["job"]
        if j["status"] in ("done", "partial", "failed"):
            return j
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_prod_is_hidden_when_nobody_is_authorized(fake, monkeypatch, tmp_path):
    c, _ = make(fake, monkeypatch, tmp_path, users="")           # prod requested but no users/group configured -> fail closed
    assert c.get("/api/me", headers=BOSS).get_json()["envs"] == ["dev"]
    assert c.post("/api/jobs", json=PBODY, headers=BOSS).status_code == 400


def test_prod_is_offered_only_to_listed_users(fake, monkeypatch, tmp_path):
    c, _ = make(fake, monkeypatch, tmp_path)
    assert c.get("/api/me", headers=BOSS).get_json()["envs"] == ["dev", "prod"]
    assert c.get("/api/me", headers=OTHER).get_json()["envs"] == ["dev"]
    r = c.post("/api/jobs", json=PBODY, headers=OTHER)
    assert r.status_code == 403 and "not authorized" in r.get_json()["error"] and not fake.prod.groups
    assert c.get("/api/workspaces?env=prod", headers=OTHER).status_code == 403   # not even reads
    assert b"prod" not in c.get("/", headers=OTHER).data.split(b"<select id=\"env\">")[1].split(b"</select>")[0]


def test_membership_of_the_prod_entra_group_grants_prod(fake, monkeypatch, tmp_path):
    c, _ = make(fake, monkeypatch, tmp_path, users="", group="11111111-aaaa")
    claims = base64.b64encode(json.dumps({"claims": [{"typ": "groups", "val": "11111111-aaaa"}]}).encode()).decode()
    assert c.get("/api/me", headers=dict(OTHER, **{"X-MS-CLIENT-PRINCIPAL": claims})).get_json()["envs"] == ["dev", "prod"]
    wrong = base64.b64encode(json.dumps({"claims": [{"typ": "groups", "val": "other-group"}]}).encode()).decode()
    assert c.get("/api/me", headers=dict(OTHER, **{"X-MS-CLIENT-PRINCIPAL": wrong})).get_json()["envs"] == ["dev"]
    assert c.get("/api/me", headers=dict(OTHER, **{"X-MS-CLIENT-PRINCIPAL": "not-base64!!"})).get_json()["envs"] == ["dev"]


def test_prod_add_needs_the_confirmation_and_starts_nothing_without_it(fake, monkeypatch, tmp_path):
    c, mgr = make(fake, monkeypatch, tmp_path)
    r = c.post("/api/jobs", json=dict(PBODY, confirm_prod=False), headers=BOSS)
    assert r.status_code == 400 and "PRODUCTION" in r.get_json()["error"] and not mgr.jobs
    body = dict(PBODY); body.pop("confirm_prod")
    assert c.post("/api/jobs", json=body, headers=BOSS).status_code == 400


def test_a_prod_job_changes_only_prod_and_seeds_gently(fake, monkeypatch, tmp_path):
    c, mgr = make(fake, monkeypatch, tmp_path)
    j = wait(c, c.post("/api/jobs", json=PBODY, headers=BOSS).get_json()["job"]["id"], BOSS)
    assert j["status"] == "done" and j["env"] == "prod"
    assert ("PW", "Svc") in fake.prod.groups and not fake.groups and "PW" not in fake.workspaces      # dev untouched
    assert fake.prod.seeds[-1][4] == 2                                                              # fewer seed threads on prod


def test_a_dev_job_never_touches_prod(fake, monkeypatch, tmp_path):
    c, mgr = make(fake, monkeypatch, tmp_path)
    body = dict(PBODY, env="dev", workspace="DEVWS"); body.pop("confirm_prod")
    j = wait(c, c.post("/api/jobs", json=body, headers=BOSS).get_json()["job"]["id"], BOSS)
    assert j["status"] == "done" and ("DEVWS", "Svc") in fake.groups and not fake.prod.groups and fake.seeds[-1][4] == 4


def test_on_prod_the_app_only_modifies_services_it_created(fake, monkeypatch, tmp_path):
    c, _ = make(fake, monkeypatch, tmp_path)
    fake.prod.workspaces.add("PW")
    fake.prod.groups[("PW", "Svc")] = {"name": "Svc", "publishables": {"published": [{"name": "PW:x"}]},
                                       "bounds": {"minx": 0, "miny": 0, "maxx": 1, "maxy": 1}}     # built by hand: no marker
    r = c.post("/api/jobs", json=PBODY, headers=BOSS)
    assert r.status_code == 403 and "only modifies services it created" in r.get_json()["error"]
    assert group_state_prod(fake)["publishables"]["published"] == [{"name": "PW:x"}]               # untouched


def group_state_prod(fake):
    return fake.prod.groups[("PW", "Svc")]


def test_prod_batches_are_capped(fake, monkeypatch, tmp_path):
    c, mgr = make(fake, monkeypatch, tmp_path, maxb=2)
    text = "\n".join(f"Cust/proj/t-0{i}-RGB.tif" for i in (1, 2, 3))
    r = c.post("/api/jobs", json=dict(PBODY, blob_text=text), headers=BOSS)
    assert r.status_code == 400 and "At most 2" in r.get_json()["error"] and not mgr.jobs


def test_prod_removal_needs_workspace_and_service_typed_and_only_removes_app_services(fake, monkeypatch, tmp_path):
    c, mgr = make(fake, monkeypatch, tmp_path)
    wait(c, c.post("/api/jobs", json=PBODY, headers=BOSS).get_json()["job"]["id"], BOSS)
    r = c.post("/api/remove", json={"env": "prod", "workspace": "PW", "group": "Svc", "confirm": "Svc"}, headers=BOSS)
    assert r.status_code == 400 and "PW:Svc" in r.get_json()["error"] and ("PW", "Svc") in fake.prod.groups
    r = c.post("/api/remove", json={"env": "prod", "workspace": "PW", "group": "Svc", "confirm": "PW:Svc"}, headers=BOSS)
    assert r.status_code == 202
    j = wait(c, r.get_json()["job"]["id"], BOSS)
    assert j["status"] == "done" and not fake.prod.groups
    assert c.post("/api/remove", json={"env": "prod", "workspace": "PW", "group": "Svc", "confirm": "PW:Svc"}, headers=OTHER).status_code == 403


def test_prod_reads_work_for_authorized_users(fake, monkeypatch, tmp_path):
    c, _ = make(fake, monkeypatch, tmp_path)
    assert "COPE-S26" in c.get("/api/workspaces?env=prod", headers=BOSS).get_json()["workspaces"]


def test_dev_workspace_names_that_exist_on_prod_are_still_refused_for_dev(fake, monkeypatch, tmp_path):
    c, _ = make(fake, monkeypatch, tmp_path)
    body = dict(PBODY, env="dev", workspace="COPE-S26"); body.pop("confirm_prod")
    assert c.post("/api/jobs", json=body, headers=BOSS).status_code == 403


# ---------------------------------------------------------------- the client-level prod guard
def test_prod_calls_are_refused_without_an_explicit_session(monkeypatch):
    with pytest.raises(PermissionError):
        gs_client.call("prod", "GET", "/rest/workspaces.json")
    with pytest.raises(PermissionError):
        gs_client.call("prod", "POST", "/rest/workspaces", {"workspace": {"name": "X"}})
    with gs_client.prod_access():                                       # read-only session: reads pass the guard, writes do not
        with pytest.raises(PermissionError):
            gs_client.call("prod", "DELETE", "/rest/workspaces/X")
        with pytest.raises(AssertionError, match="real GeoServer request"):     # got past the guard to the (blocked) network
            gs_client.call("prod", "GET", "/rest/workspaces.json")
    with gs_client.prod_access(write=True):
        with pytest.raises(AssertionError, match="real GeoServer request"):
            gs_client.call("prod", "POST", "/rest/workspaces", {"workspace": {"name": "X"}})
    with pytest.raises(PermissionError):                                # and the session ends with the block
        gs_client.call("prod", "POST", "/rest/workspaces", {"workspace": {"name": "X"}})
