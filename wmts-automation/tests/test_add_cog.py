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
