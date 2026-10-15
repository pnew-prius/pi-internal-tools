import pytest

from add_cog import STEPS, add_cog, group_state, reconcile_stray_tile_layers

WS, G = "TESTWS", "Svc"


def test_first_cog_creates_group_and_tiles_only_the_group(fake):
    fake.workspaces.add(WS)
    m = add_cog("dev", WS, G, "t-01", "Cust/proj/t-01-RGB.tif")
    assert m["group_action"] == "created" and m["members_after"] == 1
    assert group_state("dev", WS, G)[1] == ["t-01"]
    assert [k for k in fake.gwc if k.startswith(WS + ":")] == [f"{WS}:{G}"]      # strays swept, only the group is tiled
    assert "<string>image/png</string>" in fake.gwc[f"{WS}:{G}"] and "jpeg" not in fake.gwc[f"{WS}:{G}"]
    assert "EPSG:3857" in fake.gwc[f"{WS}:{G}"]


def test_truncate_then_seed_use_same_bbox_with_right_zoom_ranges(fake):
    fake.workspaces.add(WS)
    add_cog("dev", WS, G, "t-01", "Cust/proj/t-01-RGB.tif")
    trunc, seed = fake.seeds[-2], fake.seeds[-1]
    assert trunc[0] == "truncate" and seed[0] == "seed"
    assert trunc[1:3] == (0, 24) and seed[1:3] == (0, 15)         # truncate every zoom, pre-seed 0-15 only
    assert trunc[3] == seed[3] and len(seed[3]) == 4


def test_second_cog_unions_bounds_and_widens_tile_extent(fake):
    fake.workspaces.add(WS)
    a = add_cog("dev", WS, G, "t-01", "Cust/proj/t-01-RGB.tif")
    b = add_cog("dev", WS, G, "t-02", "Cust/proj/t-02-RGB.tif")
    g, members = group_state("dev", WS, G)
    assert members == ["t-01", "t-02"] and b["group_action"].startswith("updated")
    bb = g["bounds"]
    assert bb["minx"] == min(a["footprint_3857"][0], b["footprint_3857"][0])
    assert bb["maxx"] == max(a["footprint_3857"][2], b["footprint_3857"][2])
    assert str(bb["maxx"]) in fake.gwc[f"{WS}:{G}"]                 # tile layer extent follows the group bounds


def test_mixed_utm_zones_end_up_in_one_3857_group(fake):
    fake.workspaces.add(WS)
    add_cog("dev", WS, G, "t-01", "Cust/proj/t-01-RGB.tif")
    m = add_cog("dev", WS, G, "t-03", "Cust/proj/t-03-RGB.tif")
    assert m["srs"] == "EPSG:32614" and group_state("dev", WS, G)[0]["bounds"]["crs"]["$"] == "EPSG:3857"


def test_adding_same_cog_twice_is_a_noop(fake):
    fake.workspaces.add(WS)
    add_cog("dev", WS, G, "t-01", "Cust/proj/t-01-RGB.tif")
    n = len(fake.seeds)
    again = add_cog("dev", WS, G, "t-01", "Cust/proj/t-01-RGB.tif")
    assert again["skipped"] and len(fake.seeds) == n


def test_missing_workspace_requires_opt_in(fake):
    with pytest.raises(RuntimeError, match="does not exist"):
        add_cog("dev", "NEWWS", G, "t-01", "Cust/proj/t-01-RGB.tif")
    m = add_cog("dev", "NEWWS", G, "t-01", "Cust/proj/t-01-RGB.tif", create_workspace=True)
    assert m["workspace_created"] and "NEWWS" in fake.workspaces


def test_unreadable_cog_fails_clearly_and_leaves_no_group(fake):
    fake.workspaces.add(WS)
    with pytest.raises(RuntimeError, match="publish failed"):
        add_cog("dev", WS, G, "nope", "Cust/proj/nope-RGB.tif")
    assert group_state("dev", WS, G) is None
    assert (WS, "nope") not in fake.stores                          # the store created before the failure is removed


def test_progress_callback_reports_every_step_in_order(fake):
    fake.workspaces.add(WS)
    seen = []
    add_cog("dev", WS, G, "t-01", "Cust/proj/t-01-RGB.tif", progress=lambda s, st, *a: seen.append((s, st)))
    assert [s for s, st in seen if st == "done"] == STEPS


def test_reconcile_removes_only_stray_layers_in_that_workspace(fake):
    fake.workspaces.add(WS)
    add_cog("dev", WS, G, "t-01", "Cust/proj/t-01-RGB.tif")
    fake.gwc.update({f"{WS}:stray": "x", "OTHER:keep": "x"})
    assert reconcile_stray_tile_layers("dev", WS, G, settle_sec=0) == [f"{WS}:stray"]
    assert "OTHER:keep" in fake.gwc and f"{WS}:{G}" in fake.gwc


def test_reconcile_never_deletes_another_service_in_the_same_workspace(fake):
    """Regression (found live): a workspace can hold several layer groups; their tile layers must survive."""
    fake.workspaces.add(WS)
    add_cog("dev", WS, "ServiceA", "t-01", "Cust/proj/t-01-RGB.tif")
    add_cog("dev", WS, "ServiceB", "t-02", "Cust/proj/t-02-RGB.tif")
    assert f"{WS}:ServiceA" in fake.gwc and f"{WS}:ServiceB" in fake.gwc
    assert [k for k in fake.gwc if k.startswith(WS + ":")] == [f"{WS}:ServiceA", f"{WS}:ServiceB"]


def test_reconcile_refuses_to_sweep_if_it_cannot_list_groups(fake, monkeypatch):
    fake.workspaces.add(WS)
    real = fake.call
    monkeypatch.setattr(add_cog_mod_for_test(), "call", lambda env, m, path, *a, **k: (500, "boom") if path.endswith("/layergroups.json") else real(env, m, path, *a, **k))
    with pytest.raises(RuntimeError, match="refusing to sweep"):
        reconcile_stray_tile_layers("dev", WS, G, settle_sec=0)


def add_cog_mod_for_test():
    import add_cog
    return add_cog


# ---------------------------------------------------------------- WMS (live render, no tile cache)
def test_wms_service_builds_group_but_no_tiles_and_no_tile_layer(fake):
    fake.workspaces.add(WS)
    seen = []
    m = add_cog("dev", WS, G, "t-01", "Cust/proj/t-01-RGB.tif", service="wms", progress=lambda s, st, *a: seen.append((s, st)))
    assert m["service"] == "wms" and group_state("dev", WS, G)[1] == ["t-01"]
    assert fake.seeds == []                                          # no truncate, no seed
    assert [k for k in fake.gwc if k.startswith(WS + ":")] == []     # not even the group's auto-created tile layer
    assert [s for s, st in seen if st == "skipped"] == ["tile_config", "truncate", "seed"]
    assert group_state("dev", WS, G)[0]["metadata"]["entry"][0]["$"] == "wms"


def test_wms_second_cog_updates_group_bounds_without_seeding(fake):
    fake.workspaces.add(WS)
    add_cog("dev", WS, G, "t-01", "Cust/proj/t-01-RGB.tif", service="wms")
    b = add_cog("dev", WS, G, "t-02", "Cust/proj/t-02-RGB.tif", service="wms")
    g, members = group_state("dev", WS, G)
    assert members == ["t-01", "t-02"] and g["bounds"]["maxx"] == b["footprint_3857"][2] and fake.seeds == []


def test_a_service_keeps_the_type_it_was_created_with(fake):
    fake.workspaces.add(WS)
    add_cog("dev", WS, "A", "t-01", "Cust/proj/t-01-RGB.tif", service="wmts")
    with pytest.raises(RuntimeError, match="is a WMTS service"):
        add_cog("dev", WS, "A", "t-02", "Cust/proj/t-02-RGB.tif", service="wms")
    add_cog("dev", WS, "B", "t-01", "Cust/proj/t-01-RGB.tif", service="wms")
    with pytest.raises(RuntimeError, match="is a WMS service"):
        add_cog("dev", WS, "B", "t-02", "Cust/proj/t-02-RGB.tif", service="wmts")
    assert group_state("dev", WS, "A")[1] == ["t-01"] and group_state("dev", WS, "B")[1] == ["t-01"]   # nothing half-added


def test_wms_sweep_keeps_other_services_tile_layers_in_the_workspace(fake):
    fake.workspaces.add(WS)
    add_cog("dev", WS, "Cached", "t-01", "Cust/proj/t-01-RGB.tif", service="wmts")
    add_cog("dev", WS, "Live", "t-02", "Cust/proj/t-02-RGB.tif", service="wms")
    assert [k for k in fake.gwc if k.startswith(WS + ":")] == [f"{WS}:Cached"]    # WMTS service intact, WMS group untiled


def test_group_made_by_hand_is_typed_by_whether_it_has_a_tile_layer(fake):
    fake.workspaces.add(WS)
    fake.groups[(WS, "Hand")] = {"name": "Hand", "publishables": {"published": [{"name": f"{WS}:x"}]}, "bounds": {"minx": 0, "miny": 0, "maxx": 1, "maxy": 1}}
    fake.gwc[f"{WS}:Hand"] = "x"
    from add_cog import group_service_type
    assert group_service_type("dev", WS, "Hand", fake.groups[(WS, "Hand")]) == "wmts"
    fake.gwc.pop(f"{WS}:Hand")
    assert group_service_type("dev", WS, "Hand", fake.groups[(WS, "Hand")]) == "wms"


def test_unknown_service_type_is_rejected(fake):
    with pytest.raises(ValueError):
        add_cog("dev", WS, G, "t-01", "Cust/proj/t-01-RGB.tif", service="wfs")


# ---------------------------------------------------------------- remove service
def test_remove_service_truncates_tiles_then_deletes_group_and_exclusive_layers(fake, monkeypatch):
    import remove_service as rs
    monkeypatch.setattr(rs, "call", fake.call)
    fake.workspaces.add(WS)
    add_cog("dev", WS, "A", "t-01", "Cust/proj/t-01-RGB.tif")
    add_cog("dev", WS, "A", "t-02", "Cust/proj/t-02-RGB.tif")
    n = len(fake.seeds)
    out = rs.remove_service("dev", WS, "A")
    assert fake.seeds[n][0] == "truncate" and fake.seeds[n][1:3] == (0, 24) and out["truncated"]   # truncate BEFORE delete, every zoom
    assert group_state("dev", WS, "A") is None and f"{WS}:A" not in fake.gwc
    assert sorted(out["layers_deleted"]) == ["t-01", "t-02"] and not any(k[0] == WS for k in fake.stores)


def test_remove_service_keeps_layers_another_group_still_uses(fake, monkeypatch):
    import remove_service as rs
    monkeypatch.setattr(rs, "call", fake.call)
    fake.workspaces.add(WS)
    add_cog("dev", WS, "A", "t-01", "Cust/proj/t-01-RGB.tif")
    add_cog("dev", WS, "B", "t-01", "Cust/proj/t-01-RGB.tif")          # same layer used by a second service
    out = rs.remove_service("dev", WS, "A")
    assert out["layers_kept"] == ["t-01"] and (WS, "t-01") in fake.stores and group_state("dev", WS, "B")[1] == ["t-01"]


def test_remove_wms_service_has_nothing_to_truncate(fake, monkeypatch):
    import remove_service as rs
    monkeypatch.setattr(rs, "call", fake.call)
    fake.workspaces.add(WS)
    add_cog("dev", WS, "L", "t-01", "Cust/proj/t-01-RGB.tif", service="wms")
    n = len(fake.seeds)
    out = rs.remove_service("dev", WS, "L")
    assert out["type"] == "wms" and not out["truncated"] and len(fake.seeds) == n


def test_remove_missing_service_is_an_error(fake, monkeypatch):
    import remove_service as rs
    monkeypatch.setattr(rs, "call", fake.call)
    with pytest.raises(RuntimeError, match="does not exist"):
        rs.remove_service("dev", WS, "nope")


# ---------------------------------------------------------------- concurrent writers (two app instances)
def test_lost_creation_race_is_retried_as_an_update(fake, monkeypatch):
    """Another instance creates the same new group between our existence check and our POST."""
    import add_cog as ac
    fake.workspaces.add(WS)
    real, state = fake.call, {"raced": False}

    def racing(env, method, path, body=None, *a, **k):
        if method == "POST" and path.endswith("/layergroups") and not state["raced"]:
            state["raced"] = True
            real(env, method, path, {"layerGroup": {"name": G, "publishables": {"published": [{"name": f"{WS}:other"}]},
                 "bounds": {"minx": 0, "miny": 0, "maxx": 1, "maxy": 1, "crs": {"$": "EPSG:3857"}}}})  # the winner
            return 500, f"Layer group named '{G}' already exists in workspace {WS}"
        return real(env, method, path, body, *a, **k)
    monkeypatch.setattr(ac, "call", racing)
    monkeypatch.setattr(ac.time, "sleep", lambda *_: None)
    m = add_cog("dev", WS, G, "t-01", "Cust/proj/t-01-RGB.tif")
    assert group_state("dev", WS, G)[1] == ["other", "t-01"] and m["group_action"].startswith("updated")


def test_a_stale_overwrite_that_drops_our_cog_is_detected_and_redone(fake, monkeypatch):
    import add_cog as ac
    fake.workspaces.add(WS)
    first = add_cog("dev", WS, G, "t-01", "Cust/proj/t-01-RGB.tif")
    stale_group = group_state("dev", WS, G)[0]                          # the group exactly as another writer last saw it
    real, state = fake.call, {"n": 0}

    def clobber(env, method, path, body=None, *a, **k):
        res = real(env, method, path, body, *a, **k)
        if method == "PUT" and "/layergroups/" in path and state["n"] == 0:
            state["n"] = 1                     # a concurrent writer PUTs its stale copy (without our new COG) right after ours
            real(env, "PUT", path, {"layerGroup": stale_group})
        return res
    monkeypatch.setattr(ac, "call", clobber)
    monkeypatch.setattr(ac.time, "sleep", lambda *_: None)
    second = add_cog("dev", WS, G, "t-02", "Cust/proj/t-02-RGB.tif")
    g, members = group_state("dev", WS, G)
    b = g["bounds"]
    assert members == ["t-01", "t-02"]
    for fp in (first["footprint_3857"], second["footprint_3857"]):       # bounds cover BOTH COGs after the redo
        assert b["minx"] <= fp[0] + 1 and b["maxx"] >= fp[2] - 1 and b["miny"] <= fp[1] + 1 and b["maxy"] >= fp[3] - 1


def test_gives_up_with_a_clear_error_if_every_attempt_is_overwritten(fake, monkeypatch):
    import add_cog as ac
    fake.workspaces.add(WS)
    add_cog("dev", WS, G, "t-01", "Cust/proj/t-01-RGB.tif")
    real = fake.call

    def always_clobber(env, method, path, body=None, *a, **k):
        res = real(env, method, path, body, *a, **k)
        if method == "PUT" and "/layergroups/" in path:
            real(env, "PUT", path, {"layerGroup": {"name": G, "publishables": {"published": [{"@type": "layer", "name": f"{WS}:t-01"}]},
                 "bounds": {"minx": 0, "miny": 0, "maxx": 1, "maxy": 1, "crs": {"$": "EPSG:3857"}}}})
        return res
    monkeypatch.setattr(ac, "call", always_clobber)
    monkeypatch.setattr(ac.time, "sleep", lambda *_: None)
    with pytest.raises(RuntimeError, match="after 6 attempts"):
        add_cog("dev", WS, G, "t-02", "Cust/proj/t-02-RGB.tif")


def test_too_narrow_tile_extent_is_widened_to_the_group_bounds(fake):
    from add_cog import sync_tile_extent
    from gwc import set_tile_layer_xml
    fake.workspaces.add(WS)
    add_cog("dev", WS, G, "t-01", "Cust/proj/t-01-RGB.tif")
    assert sync_tile_extent("dev", WS, G) is False                      # already consistent: nothing written
    g = group_state("dev", WS, G)[0]["bounds"]
    narrow = [g["minx"] + 5000, g["miny"] + 5000, g["maxx"] - 5000, g["maxy"] - 5000]
    set_tile_layer_xml("dev", f"{WS}:{G}", narrow)
    assert sync_tile_extent("dev", WS, G) is True                       # widened back to the group's bounds
    assert sync_tile_extent("dev", WS, G) is False


# ---------------------------------------------------------------- client cache, template store, remove with progress
def test_tile_layer_tells_browsers_to_cache_tiles_for_a_while(fake):
    fake.workspaces.add(WS)
    add_cog("dev", WS, G, "t-01", "Cust/proj/t-01-RGB.tif")
    assert "<expireClients>600</expireClients>" in fake.gwc[f"{WS}:{G}"]


def test_missing_credential_template_store_gives_an_actionable_error(fake):
    fake.workspaces.add(WS)
    fake.stores.pop(("COPE-S26", "codes26-01"))
    with pytest.raises(RuntimeError, match="WMTS_TEMPLATE_STORE"):
        add_cog("dev", WS, G, "t-01", "Cust/proj/t-01-RGB.tif")


def test_remove_reports_progress_and_deletes_an_empty_workspace(fake, monkeypatch):
    import remove_service as rs
    monkeypatch.setattr(rs, "call", fake.call)
    fake.workspaces.add(WS)
    add_cog("dev", WS, "A", "t-01", "Cust/proj/t-01-RGB.tif")
    seen = []
    out = rs.remove_service("dev", WS, "A", progress=lambda s, st, *a: seen.append((s, st)), delete_empty_workspace=True)
    assert [s for s, st in seen if st == "done"] == rs.REMOVE_STEPS and out["workspace_deleted"] and WS not in fake.workspaces


def test_remove_keeps_a_workspace_that_still_has_other_services(fake, monkeypatch):
    import remove_service as rs
    monkeypatch.setattr(rs, "call", fake.call)
    fake.workspaces.add(WS)
    add_cog("dev", WS, "A", "t-01", "Cust/proj/t-01-RGB.tif")
    add_cog("dev", WS, "B", "t-02", "Cust/proj/t-02-RGB.tif")
    out = rs.remove_service("dev", WS, "A", delete_empty_workspace=True)
    assert out["workspace_deleted"] is False and WS in fake.workspaces and group_state("dev", WS, "B") is not None


# --- seeding (dev experiments 2026-10-15): a COG's truncate also clears its neighbours' seams, so seed it AND the members touching it ---

def _same(a, b):
    return all(abs(x - y) < 1.0 for x, y in zip(a, b))


def test_a_joining_cog_seeds_its_own_footprint_and_the_neighbour_it_touches(fake):
    fake.workspaces.add(WS)
    a = add_cog("dev", WS, G, "t-01", "Cust/proj/t-01-RGB.tif")
    b = add_cog("dev", WS, G, "t-02", "Cust/proj/t-02-RGB.tif")        # t-02 overlaps t-01
    tail = fake.seeds[-3:]
    assert [s[0] for s in tail] == ["truncate", "seed", "seed"] and all(s[1:3] == (0, 15) for s in tail[1:])
    assert tail[0][3] == b["footprint_3857"] and tail[1][3] == b["footprint_3857"]       # new footprint first
    assert _same(tail[2][3], a["footprint_3857"])                                           # then t-01, whose seams were cleared
    bounds = group_state("dev", WS, G)[0]["bounds"]
    assert all(not _same(s[3], [bounds["minx"], bounds["miny"], bounds["maxx"], bounds["maxy"]]) for s in fake.seeds)   # never the whole rectangle
    assert b["seed_needed"] is None


def test_a_far_away_cog_does_not_reseed_the_others(fake):
    fake.workspaces.add(WS)
    add_cog("dev", WS, G, "t-01", "Cust/proj/t-01-RGB.tif")
    n = len(fake.seeds)
    c = add_cog("dev", WS, G, "t-03", "Cust/proj/t-03-RGB.tif")        # a different UTM zone, hundreds of km away
    assert [s[0] for s in fake.seeds[n:]] == ["truncate", "seed"] and fake.seeds[-1][3] == c["footprint_3857"]


def test_refreshing_a_member_seeds_it_and_its_neighbours(fake):
    fake.workspaces.add(WS)
    add_cog("dev", WS, G, "t-01", "Cust/proj/t-01-RGB.tif")
    b = add_cog("dev", WS, G, "t-02", "Cust/proj/t-02-RGB.tif")
    n = len(fake.seeds)
    r = add_cog("dev", WS, G, "t-02", "Cust/proj/t-02-RGB.tif", refresh=True)
    assert r["group_action"].startswith("refreshed")
    assert [s[0] for s in fake.seeds[n:]] == ["truncate", "seed", "seed"] and fake.seeds[n + 1][3] == b["footprint_3857"]


def test_deferred_seed_does_no_seeding_and_says_what_is_needed(fake):
    fake.workspaces.add(WS)
    steps = []
    m = add_cog("dev", WS, G, "t-01", "Cust/proj/t-01-RGB.tif", seed="defer", progress=lambda *a: steps.append(a))
    assert [s[0] for s in fake.seeds] == ["truncate"]
    assert m["seed_needed"] == m["footprint_3857"] and ("seed", "skipped") in [s[:2] for s in steps]
    m = add_cog("dev", WS, G, "t-01", "Cust/proj/t-01-RGB.tif", seed="defer", refresh=True)
    assert m["seed_needed"] == m["footprint_3857"]


def test_seed_targets_adds_only_members_within_the_margin_and_never_duplicates():
    from add_cog import seed_targets
    new = [0.0, 0.0, 10000.0, 10000.0]
    members = {"same": list(new), "near": [14000.0, 0.0, 20000.0, 10000.0],      # 4 km away: inside the 6 km margin
               "far": [17000.0, 0.0, 30000.0, 10000.0], "elsewhere": [1e6, 1e6, 1.1e6, 1.1e6]}   # 7 km away / far away
    out = seed_targets([new], members)
    assert out == [new, [14000.0, 0.0, 20000.0, 10000.0]]


def test_bad_seed_mode_is_rejected(fake):
    with pytest.raises(ValueError):
        add_cog("dev", WS, G, "t-01", "Cust/proj/t-01-RGB.tif", seed="later")


def test_wait_seed_idle_does_not_mistake_a_not_yet_listed_task_for_finished(fake, monkeypatch):
    import gwc
    polls = iter([[], [], [[1, 9, 1, 1, 1]], [[9, 9, 0, 1, 1]], []])     # GWC lists the task only after a short delay
    monkeypatch.setattr(gwc, "call", lambda *a, **k: (200, {"long-array-array": next(polls)}))
    assert gwc.wait_seed_idle("dev", "X:Y", poll=0) == 9                   # waited for it to appear AND finish


def test_wait_seed_idle_returns_after_the_grace_period_if_no_task_ever_shows(fake, monkeypatch):
    import gwc
    monkeypatch.setattr(gwc, "call", lambda *a, **k: (200, {"long-array-array": []}))
    clock = iter(range(0, 100))
    monkeypatch.setattr(gwc.time, "time", lambda: next(clock))
    assert gwc.wait_seed_idle("dev", "X:Y", poll=0, appear_grace=5) == 0
