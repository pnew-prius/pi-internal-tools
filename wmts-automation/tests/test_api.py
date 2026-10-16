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
    steps = {s["name"]: s["status"] for s in j["items"][0]["steps"]}
    assert steps.pop("seed") == "skipped" and all(v == "done" for v in steps.values())   # seeding is deferred to the job...
    assert j["seed"]["status"] == "done" and fake.seeds[-1][0] == "seed"                 # ...and runs once at the end
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
    assert [i["status"] for i in j["items"]] == ["skipped", "done"] and len(fake.seeds) == n + 3   # only t-02 truncated; t-02 and its neighbour t-01 seeded
    n = len(fake.seeds)
    j = wait(c, post(c, dict(BODY, blob_text=ONE, refresh=True)).get_json()["job"]["id"])
    assert j["items"][0]["status"] == "done" and "refreshed" in j["items"][0]["result"]["group_action"] and len(fake.seeds) == n + 3   # truncate, seed t-01, seed neighbour t-02


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
    j = wait(c, post(c, BODY).get_json()["job"]["id"])
    assert j["status"] == "partial" and j["items"][0]["status"] == "done"            # the COG is published...
    assert j["seed"]["status"] == "failed" and "Refresh" in j["seed"]["detail"]      # ...but its tiles were not cached: said so
    j = wait(c, post(c, BODY).get_json()["job"]["id"])                # plain re-run: member already there -> skipped, tiles still missing
    assert j["items"][0]["status"] == "skipped" and j["seed"]["status"] == "skipped"
    state["fail"] = False
    j = wait(c, post(c, dict(BODY, refresh=True)).get_json()["job"]["id"])
    assert j["status"] == "done" and j["seed"]["status"] == "done" and fake.seeds[-1][0] == "seed"   # refresh finishes the job


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
    assert s["exists"] and s["members"] == 1 and s["capabilities_url"].endswith("/TESTWS/Svc/gwc/service/wmts?REQUEST=GetCapabilities")


def test_index_page_renders_with_user(client):
    c, *_ = client
    r = c.get("/", headers=H)
    assert r.status_code == 200 and b"someone@priusintelli.com" in r.data and b"Map Service Builder" in r.data and b"<textarea" in r.data


def test_wms_job_via_api_runs_without_seeding(client):
    c, mgr, fake = client
    j = wait(c, post(c, dict(BODY, service_type="wms")).get_json()["job"]["id"])
    assert j["status"] == "done" and j["service"] == "wms" and fake.seeds == []
    assert [s["status"] for s in j["items"][0]["steps"] if s["name"] in ("tile_config", "truncate", "seed")] == ["skipped"] * 3


def test_unknown_service_type_is_a_400(client):
    c, *_ = client
    assert post(c, dict(BODY, service_type="wfs")).status_code == 400


def test_mixing_types_in_one_service_fails_the_cog_with_a_clear_message(client):
    c, *_ = client
    wait(c, post(c, BODY).get_json()["job"]["id"])
    j = wait(c, post(c, dict(BODY, blob_text="Cust/proj/t-02-RGB.tif", service_type="wms")).get_json()["job"]["id"])
    assert j["status"] == "failed" and "is a WMTS service" in j["items"][0]["error"]


def test_service_urls_for_a_wmts_service(client):
    c, *_ = client
    wait(c, post(c, BODY).get_json()["job"]["id"])
    s = c.get("/api/service?workspace=TESTWS&group=Svc", headers=H).get_json()
    assert s["service_type"] == "wmts" and s["wms_url"].endswith("/TESTWS/Svc/ows?service=WMS&request=GetCapabilities&version=1.3.0")
    assert s["wmts_url"].endswith("/TESTWS/Svc/gwc/service/wmts?REQUEST=GetCapabilities")   # scoped to the layer group
    assert "LAYER=TESTWS:Svc" in s["tile_url_template"] and "{z}" in s["tile_url_template"] and "{x}" in s["tile_url_template"]


def test_service_urls_for_a_wms_service_have_no_wmts(client):
    c, *_ = client
    wait(c, post(c, dict(BODY, service_type="wms")).get_json()["job"]["id"])
    s = c.get("/api/service?workspace=TESTWS&group=Svc", headers=H).get_json()
    assert s["service_type"] == "wms" and s["wmts_url"] is None and s["tile_url_template"] is None and "/TESTWS/Svc/ows?service=WMS" in s["wms_url"]


def test_page_has_service_type_and_copyable_url_support(client):
    c, *_ = client
    html = c.get("/", headers=H).data
    assert b'id="stype"' in html and b"copyText" in html and b"WMS capabilities URL" in html and b"WMTS tile URL template" in html


def test_oversized_request_is_refused(client):
    c, mgr, fake = client
    r = c.post("/api/jobs", data=("x" * (300 * 1024)), headers=dict(H, **{"Content-Type": "application/json"}))
    assert r.status_code == 413 and not mgr.jobs


# ---------------------------------------------------------------- remove service via the API
def build(c, group="Svc", service="wmts"):
    return wait(c, post(c, dict(BODY, group=group, service_type=service)).get_json()["job"]["id"])


def test_remove_requires_typing_the_service_name(client):
    c, *_ = client
    build(c)
    r = c.post("/api/remove", json={"workspace": "TESTWS", "group": "Svc", "confirm": "svc"}, headers=H)
    assert r.status_code == 400 and "exact service name" in r.get_json()["error"]


def test_remove_runs_truncate_first_then_deletes_everything(client):
    c, mgr, fake = client
    build(c)
    r = c.post("/api/remove", json={"workspace": "TESTWS", "group": "Svc", "confirm": "Svc"}, headers=H)
    assert r.status_code == 202
    j = wait(c, r.get_json()["job"]["id"])
    assert j["status"] == "done" and j["kind"] == "remove" and [s["status"] for s in j["items"][0]["steps"]] == ["done"] * 4
    assert fake.seeds[-1][0] == "truncate" and fake.seeds[-1][1:3] == (0, 24)
    assert not fake.groups and "TESTWS" not in fake.workspaces            # service, layers and the now-empty workspace are gone
    rows = c.get("/api/jobs", headers=H).get_json()["jobs"]
    assert rows[0]["kind"] == "remove"                                      # recorded in history


def test_remove_refuses_services_this_app_did_not_create(client):
    c, mgr, fake = client
    fake.workspaces.add("HANDMADE")
    fake.groups[("HANDMADE", "Old")] = {"name": "Old", "publishables": {"published": [{"name": "HANDMADE:x"}]},
                                       "bounds": {"minx": 0, "miny": 0, "maxx": 1, "maxy": 1}}
    r = c.post("/api/remove", json={"workspace": "HANDMADE", "group": "Old", "confirm": "Old"}, headers=H)
    assert r.status_code == 403 and "not created by this app" in r.get_json()["error"] and ("HANDMADE", "Old") in fake.groups


def test_remove_refuses_workspaces_that_exist_on_prod(client):
    c, *_ = client
    r = c.post("/api/remove", json={"workspace": "COPE-S26", "group": "X", "confirm": "X"}, headers=H)
    assert r.status_code == 403 and "share one tile cache" in r.get_json()["error"]


def test_remove_unknown_service_is_404_and_busy_service_is_409(client):
    c, mgr, fake = client
    assert c.post("/api/remove", json={"workspace": "TESTWS", "group": "Nope", "confirm": "Nope"}, headers=H).status_code == 404
    build(c)
    mgr.submit("a", "dev", "TESTWS", "Svc", [{"tile": "t-02", "path": "Cust/proj/t-02-RGB.tif"}], run=False)   # an add is in flight
    assert c.post("/api/remove", json={"workspace": "TESTWS", "group": "Svc", "confirm": "Svc"}, headers=H).status_code == 409


def test_remove_needs_json_and_a_signed_in_user(client):
    c, *_ = client
    assert c.post("/api/remove", json={"workspace": "TESTWS", "group": "Svc", "confirm": "Svc"}).status_code == 401
    assert c.post("/api/remove", data="x=1", headers=H).status_code == 415


# ---------------------------------------------------------------- regressions: "only 1 of 10 COGs was added"
THREE = "Cust/proj/t-01-RGB.tif\nCust/proj/t-02-RGB.tif\nCust/proj/t-03-RGB.tif"


def _mgr_client(fake, monkeypatch, store):
    monkeypatch.setattr(app_mod, "call", fake.call)
    monkeypatch.delenv("WMTS_LOCAL", raising=False)
    mgr = JobManager(store)
    return app_mod.create_app(mgr).test_client(), mgr


def test_deleting_the_history_folder_while_running_does_not_stop_a_batch(fake, monkeypatch, tmp_path):
    import shutil
    store = JsonlStore(str(tmp_path / "data" / "history.jsonl"))
    c, mgr = _mgr_client(fake, monkeypatch, store)
    shutil.rmtree(tmp_path / "data")                                     # exactly what happened: folder gone after startup
    j = wait(c, post(c, dict(BODY, blob_text=THREE)).get_json()["job"]["id"])
    assert j["status"] == "done" and j["counts"] == {"total": 3, "done": 3, "skipped": 0, "failed": 0}
    assert len(store.recent()) == 3                                      # and the history folder was recreated


def test_a_history_write_failure_never_stops_or_fails_an_add(fake, monkeypatch, tmp_path):
    class Broken(JsonlStore):
        def save(self, job):
            raise OSError("disk is full")
    c, mgr = _mgr_client(fake, monkeypatch, Broken(str(tmp_path / "h.jsonl")))
    j = wait(c, post(c, dict(BODY, blob_text=THREE)).get_json()["job"]["id"])
    assert j["status"] == "done" and j["counts"]["done"] == 3 and "disk is full" in j["history_error"]


def test_an_unexpected_crash_marks_the_unrun_cogs_failed_never_done(fake, monkeypatch, tmp_path):
    import add_cog as ac

    class Crash(BaseException):
        pass
    real = ac.add_cog
    seen = []

    def add_then_crash(env, ws, group, tile, *a, **k):
        seen.append(tile)
        if len(seen) == 2:
            raise Crash("worker died")
        return real(env, ws, group, tile, *a, **k)
    monkeypatch.setattr(ac, "add_cog", add_then_crash)
    c, mgr = _mgr_client(fake, monkeypatch, JsonlStore(str(tmp_path / "h.jsonl")))
    j = wait(c, post(c, dict(BODY, blob_text=THREE)).get_json()["job"]["id"])
    assert j["status"] == "partial" and j["counts"] == {"total": 3, "done": 1, "skipped": 0, "failed": 2}
    assert [i["status"] for i in j["items"]] == ["done", "failed", "failed"]
    assert all("Not run" in i["error"] for i in j["items"][1:]) and "stopped unexpectedly" in j["error"]
    assert post(c, dict(BODY, blob_text=ONE)).status_code == 202            # the service lock was released


def test_a_batch_seeds_once_after_the_last_truncate_covering_every_added_footprint(client):
    """Each add's truncate clears its neighbours' seams, so a batch seeds only after the last truncate (0 gaps on dev)."""
    c, mgr, fake = client
    j = wait(c, post(c, dict(BODY, blob_text=THREE)).get_json()["job"]["id"])
    assert j["status"] == "done" and j["counts"]["done"] == 3
    kinds = [s[0] for s in fake.seeds]
    first_seed = kinds.index("seed")
    assert "truncate" not in kinds[first_seed:] and kinds[:first_seed] == ["truncate"] * 3     # every truncate happens before any seed
    seeds = [s for s in fake.seeds if s[0] == "seed"]
    assert len(seeds) >= 3 and all(s[1:3] == (0, 15) for s in seeds)
    from add_cog import group_state
    b = group_state("dev", "TESTWS", "Svc")[0]["bounds"]
    assert [b["minx"], b["miny"], b["maxx"], b["maxy"]] not in [s[3] for s in seeds]          # never the empty bounding rectangle
    assert j["seed"]["status"] == "done" and all({s["name"]: s["status"] for s in it["steps"]}["seed"] == "skipped" for it in j["items"])


def test_wms_batch_never_seeds(client):
    c, mgr, fake = client
    j = wait(c, post(c, dict(BODY, blob_text=THREE, service_type="wms")).get_json()["job"]["id"])
    assert j["status"] == "done" and j["seed"]["status"] == "skipped" and fake.seeds == []
