"""Input validation for the add-COG form/API. Pure functions, no network."""
import re
import urllib.parse

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
PATH_RE = re.compile(r"^[A-Za-z0-9 _./()+-]+$")
ACCOUNT_URL = "https://pigeoserverprod.blob.core.windows.net/sourceimagery/"


class ValidationError(ValueError):
    pass


def check_name(label, value):
    value = (value or "").strip()
    if not NAME_RE.match(value):
        raise ValidationError(f"{label} must be 1-64 letters, digits, '-' or '_' (starting with a letter or digit).")
    return value


def normalize_blob_path(raw):
    """Accepts 'Customer/project/tile-RGB.tif' or the full blob URL; returns the path inside `sourceimagery`."""
    p = (raw or "").strip()
    if not p:
        raise ValidationError("Paste the COG's blob path.")
    if "?" in p or "#" in p:
        raise ValidationError("Remove everything after the file name (SAS tokens and query strings must not be pasted).")
    if p.lower().startswith("http"):
        if not p.startswith(ACCOUNT_URL):
            raise ValidationError("Only COGs in pigeoserverprod/sourceimagery are supported.")
        p = p[len(ACCOUNT_URL):]
    p = urllib.parse.unquote(p).lstrip("/")
    if p.lower().startswith("sourceimagery/"):
        p = p[len("sourceimagery/"):]
    if ".." in p.split("/") or "\\" in p or "//" in p:
        raise ValidationError("Path must not contain '..', '//' or backslashes.")
    if not PATH_RE.match(p):
        raise ValidationError("Path contains unsupported characters.")
    if not p.lower().endswith((".tif", ".tiff")):
        raise ValidationError("The path must end in .tif.")
    if "/" not in p:
        raise ValidationError("Include the folders, e.g. Customer/project-season/tile-RGB.tif.")
    return p


def tile_name_from_path(path):
    """Layer name = file name without extension and without the '-RGB' suffix (convention, e.g. codes26-01-RGB.tif -> codes26-01)."""
    stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    if stem.upper().endswith("-RGB"):
        stem = stem[:-4]
    return check_name("Layer name derived from the file name", stem)
