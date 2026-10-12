import time

import pytest

import app as app_mod
from jobs import JobManager
from store import JsonlStore

H = {"X-MS-CLIENT-PRINCIPAL-NAME": "someone@priusintelli.com"}
ONE = "Cust/proj/t-01-RGB.tif"
BODY = {"env": "dev", "workspace": "TESTWS", "group": "Svc", "blob_text": ONE, "create_workspace": True}


@pytest.fixture
def client(fake, monkeypatch, tmp_path):
    monkeypatch.setattr(app_mod, "call", fake.call)
    monkeypatch.delenv("WMTS_LOCAL", raising=False)
    mgr = JobManager(JsonlStore(str(tmp_path / "h.jsonl")))
    return app_mod.create_app(mgr).test_client(), mgr, fake


def wait(c, jid, timeout=15):
    t = time.time()
    while time.time() - t < timeout:
        j = c.get(f"/api/jobs/{jid}", headers=H).get_json()["job"]
        if j["status"] in ("done", "partial", "failed"):
            return j
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def post(c, body, **kw):
    return c.post("/api/jobs", json=body, headers=H, **kw)


def test_requires_sign_in(client):
    c, *_ = client
    assert c.get("/api/me").status_code == 401 and c.post("/api/jobs", json=BODY).status_code == 401
    assert c.get("/healthz").status_code == 200                       # health probe is open


def test_local_mode_allows_dev_user(client, monkeypatch):
    c, *_ = client
    monkeypatch.setenv("WMTS_LOCAL", "1")
    assert c.get("/api/me").get_json()["user"] == "local-dev"


def test_single_cog_job_runs_and_is_recorded_with_the_user(client):
    c, mgr, fake = client
    r = post(c, BODY)
    assert r.status_code == 202
    j = wait(c, r.get_json()["job"]["id"])
    assert j["status"] == "done" and j["user"] == "someone@priusintelli.com" and j["counts"] == {"total": 1, "done": 1, "skipped": 0, "failed": 0}
    assert all(s["status"] == "done" for s in j["items"][0]["steps"])
    hist = c.get("/api/jobs", headers=H).get_json()["jobs"]
    assert [h["tile"] for h in hist] == ["t-01"] and hist[0]["batch"] == j["id"]


def test_batch_is_added_in_pasted_order_one_at_a_time(client):
    c, mgr, fake = client
    j = wait(c, post(c, dict(BODY, blob_text="Cust/proj/t-02-RGB.tif\nCust/proj/t-01-RGB.tif")).get_json()["job"]["id"])
    assert j["status"] == "done" and [i["tile"] for i in j["items"]] == ["t-02", "t-01"]
    from add_cog import group_state
    import add_cog
    assert group_state("dev", "TESTWS", "Svc")[1] == ["t-02", "t-01"]


def test_batch_carries_on_after_a_failure_and_reports_partial(client):
    c, mgr, fake = client
    text = "Cust/proj/t-01-RGB.tif\nCust/proj/missing-RGB.tif\nCust/proj/t-02-RGB.tif"
    j = wait(c, post(c, dict(BODY, blob_text=text)).get_json()["job"]["id"])
    assert j["status"] == "partial" and j["counts"] == {"total": 3, "done": 2, "skipped": 0, "failed": 1}
    assert [i["status"] for i in j["items"]] == ["done", "failed", "done"]
    assert "publish failed" in j["items"][1]["error"]
    assert ("TESTWS", "missing") not in fake.stores                  # the failed COG left nothing behind
    rows = c.get("/api/jobs", headers=H).get_json()["jobs"]
    assert sorted(r["status"] for r in rows) == ["done", "done", "failed"]   # one history row per COG


def test_all_failed_batch_is_failed(client):
    c, *_ = client
    j = wait(c, post(c, dict(BODY, blob_text="Cust/proj/a-RGB.tif\nCust/proj/b-RGB.tif")).get_json()["job"]["id"])
    assert j["status"] == "failed" and j["counts"]["failed"] == 2


def test_cogs_already_in_service_are_skipped_unless_refresh(client):
    c, mgr, fake = client
    wait(c, post(c, BODY).get_json()["job"]["id"])
    n = len(fake.seeds)
    j = wait(c, post(c, dict(BODY, blob_text=ONE + "\nCust/proj/t-02-RGB.tif")).get_json()["job"]["id"])
    assert [i["status"] for i in j["items"]] == ["skipped", "done"] and len(fake.seeds) == n + 2   # only t-02 truncated+seeded
    n = len(fake.seeds)
    j = wait(c, post(c, dict(BODY, blob_text=ONE, refresh=True)).get_json()["job"]["id"])
    assert j["items"][0]["status"] == "done" and "refreshed" in j["items"][0]["result"]["group_action"] and len(fake.seeds) == n + 2


def test_failed_add_can_be_repaired_by_refresh(client, monkeypatch):
    c, mgr, fake = client
    import add_cog
    real = add_cog.seed_request
    state = {"fail": True}
    def flaky(*a, **k):
        if state["fail"] and a[2] == "seed":
            raise RuntimeError("seed exploded")
        return real(*a, **k)
    monkeypatch.setattr(add_cog, "seed_request", flaky)
    assert wait(c, post(c, BODY).get_json()["job"]["id"])["status"] == "failed"
    j = wait(c, post(c, BODY).get_json()["job"]["id"])                # plain re-run: member already there -> skipped, tiles still missing
    assert j["items"][0]["status"] == "skipped"
    state["fail"] = False
    j = wait(c, post(c, dict(BODY, refresh=True)).get_json()["job"]["id"])
    assert j["status"] == "done" and fake.seeds[-1][0] == "seed"      # refresh finishes the job


def test_second_job_on_same_service_is_rejected_while_one_runs(client):
    c, mgr, fake = client
    mgr.submit("a", "dev", "TESTWS", "Svc", [{"tile": "t-01", "path": ONE}], run=False)   # pretend a batch is in flight
    r = post(c, BODY)
    assert r.status_code == 409 and "already running" in r.get_json()["error"]


def test_workspace_that_exists_on_prod_is_refused_for_dev(client):
    c, *_ = client
    r = post(c, dict(BODY, workspace="COPE-S26"))
    assert r.status_code == 403 and "share one tile cache" in r.get_json()["error"]


def test_prod_unreadable_fails_closed(client, monkeypatch):
    c, *_ = client
    monkeypatch.setattr(app_mod.safety, "call", lambda *a, **k: (500, "boom"))
    assert post(c, BODY).status_code == 503


def test_prod_environment_not_enabled_by_default(client):
    c, *_ = client
    assert post(c, dict(BODY, env="prod")).status_code == 400


@pytest.mark.parametrize("bad", [dict(blob_text="x.tif"), dict(blob_text=ONE + "?sig=1"), dict(workspace="a b"), dict(group=""), dict(blob_text="")])
def test_bad_input_is_a_400_and_starts_nothing(client, bad):
    c, mgr, fake = client
    assert post(c, dict(BODY, **bad)).status_code == 400 and not mgr.jobs


def test_one_bad_line_blocks_the_whole_batch_with_line_numbers(client):
    c, mgr, fake = client
    r = post(c, dict(BODY, blob_text=ONE + "\nnotes.txt\nCust/proj/t-02-RGB.tif"))
    body = r.get_json()
    assert r.status_code == 400 and body["problems"][0]["line"] == 2 and not mgr.jobs


def test_validate_endpoint_reports_duplicates_and_name_clashes(client):
    c, *_ = client
    text = "A/b/t-01-RGB.tif\nA/b/t-01-RGB.tif\nC/d/t-01-RGB.tif\n# comment\n\nA/b/t-02-RGB.tif"
    r = c.post("/api/validate", json={"blob_text": text}, headers=H).get_json()
    assert [i["tile"] for i in r["items"]] == ["t-01", "t-02"]
    assert [e["line"] for e in r["errors"]] == [2, 3] and "Duplicate" in r["errors"][0]["error"] and "Same layer name" in r["errors"][1]["error"]


def test_batch_size_is_capped(client):
    c, *_ = client
    text = "\n".join(f"A/b/t-{i:03d}-RGB.tif" for i in range(101))
    r = c.post("/api/validate", json={"blob_text": text}, headers=H).get_json()
    assert any("At most 100" in e["error"] for e in r["errors"])


def test_cross_site_form_post_is_rejected(client):
    c, mgr, fake = client
    r = c.post("/api/jobs", data='{"workspace":"TESTWS","group":"Svc","blob_text":"%s"}' % ONE, headers=dict(H, **{"Content-Type": "text/plain"}))
    assert r.status_code == 415 and not mgr.jobs
    r = c.post("/api/jobs", data={"workspace": "TESTWS"}, headers=H)       # classic HTML form encoding
    assert r.status_code == 415 and not mgr.jobs


def test_script_in_names_is_never_executed_or_accepted(client):
    c, *_ = client
    assert post(c, dict(BODY, workspace="<script>alert(1)</script>")).status_code == 400
    assert post(c, dict(BODY, blob_text="a/<img src=x onerror=1>/t-RGB.tif")).status_code == 400


def test_service_endpoint_reports_members_and_capabilities_url(client):
    c, *_ = client
    wait(c, post(c, BODY).get_json()["job"]["id"])
    s = c.get("/api/service?workspace=TESTWS&group=Svc", headers=H).get_json()
    assert s["exists"] and s["members"] == 1 and s["capabilities_url"].endswith("/TESTWS/gwc/service/wmts?REQUEST=GetCapabilities")


def test_index_page_renders_with_user(client):
    c, *_ = client
    r = c.get("/", headers=H)
    assert r.status_code == 200 and b"someone@priusintelli.com" in r.data and b"WMTS Service Builder" in r.data and b"<textarea" in r.data
