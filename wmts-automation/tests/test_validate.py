import pytest

from validate import ValidationError, check_name, normalize_blob_path, tile_name_from_path


def test_plain_path_ok():
    assert normalize_blob_path("Prius Intelli/automation-test/wmts/ww26-01-RGB.tif") == "Prius Intelli/automation-test/wmts/ww26-01-RGB.tif"


def test_full_url_is_normalized_and_decoded():
    u = "https://pigeoserverprod.blob.core.windows.net/sourceimagery/Prius%20Intelli/automation-test/wmts/ww26-01-RGB.tif"
    assert normalize_blob_path(u) == "Prius Intelli/automation-test/wmts/ww26-01-RGB.tif"


def test_container_prefix_stripped():
    assert normalize_blob_path("sourceimagery/Conoco/p/x-RGB.tif") == "Conoco/p/x-RGB.tif"


@pytest.mark.parametrize("bad", [
    "", "   ", "file.tif", "a/b/c.png", "a/../b/c.tif", "a//b.tif", "a\\b\\c.tif", "a/b/c.tif?sv=2024&sig=abc",
    "https://evil.example.com/sourceimagery/a/b.tif", "a/b/c;rm -rf.tif", "https://pigeoserverprod.blob.core.windows.net/other/a/b.tif",
])
def test_bad_paths_rejected(bad):
    with pytest.raises(ValidationError):
        normalize_blob_path(bad)


def test_tile_name_strips_rgb_suffix():
    assert tile_name_from_path("A/B/codes26-03-b1-RGB.tif") == "codes26-03-b1"
    assert tile_name_from_path("A/B/plain.tif") == "plain"


@pytest.mark.parametrize("bad", ["", "-x", "a b", "a/b", "x" * 65, "a;b"])
def test_bad_names_rejected(bad):
    with pytest.raises(ValidationError):
        check_name("Workspace", bad)
