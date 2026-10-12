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
    fake.gwc.update({f"{WS}:{G}": "x", f"{WS}:stray": "x", "OTHER:keep": "x"})
    assert reconcile_stray_tile_layers("dev", WS, G, settle_sec=0) == [f"{WS}:stray"]
    assert "OTHER:keep" in fake.gwc and f"{WS}:{G}" in fake.gwc
