"""Client-side checks: fetch a WMTS tile and an uncached WMS render of the same area, and compare."""
import hashlib
import io
import os
import subprocess
import tempfile

from pyproj import Transformer

try:
    from PIL import Image
except ImportError:  # pillow optional: without it nonblank fractions are None
    Image = None

W = 40075016.68557849
O = W / 2
HOST = "devimageservices.priusintelli.com"


def tile_of(x, y, z):
    """EPSG:3857 point -> (col, row) at zoom z on the standard top-left pyramid."""
    s = W / 2**z
    return int((x + O) // s), int((O - y) // s)


def tile_bbox(c, r, z):
    s = W / 2**z
    return (c * s - O, O - (r + 1) * s, (c + 1) * s - O, O - r * s)


def center3857(bb, epsg=32613):
    return Transformer.from_crs(epsg, 3857, always_xy=True).transform((bb["minx"] + bb["maxx"]) / 2, (bb["miny"] + bb["maxy"]) / 2)


def _nonblank(data):
    if not (Image and data[:4] == b"\x89PNG"):
        return None
    a = Image.open(io.BytesIO(data)).convert("RGBA").getchannel("A")
    return round(sum(1 for p in a.getdata() if p > 0) / (a.width * a.height), 3)


def _curl(url, want_headers=False):
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = f.name
    try:
        r = subprocess.run(["curl.exe", "-s", "--max-time", "180", "-D", "-", "-o", path, url], capture_output=True, text=True)
        data = open(path, "rb").read()
    finally:
        os.remove(path)
    hdr = {k.strip().lower(): v.strip() for k, _, v in (ln.partition(":") for ln in r.stdout.splitlines()) if v}
    code = r.stdout.split(" ", 2)[1] if r.stdout.startswith("HTTP") else "?"
    return code, hdr, data


def get_tile(layer, z, col, row, host=HOST, fmt="image/png", matrixset="EPSG:3857"):
    """matrix IDs on this gridset are plain numbers (0..24), not 'EPSG:3857:N'."""
    code, hdr, data = _curl(f"https://{host}/gwc/service/wmts?REQUEST=GetTile&SERVICE=WMTS&VERSION=1.0.0&LAYER={layer}&STYLE="
                            f"&TILEMATRIXSET={matrixset}&TILEMATRIX={z}&TILEROW={row}&TILECOL={col}&FORMAT={fmt}")
    return {"http": code, "cache": hdr.get("geowebcache-cache-result"), "bytes": len(data),
            "md5": hashlib.md5(data).hexdigest()[:10], "nonblank": _nonblank(data)}


def wms_nonblank(layer, bbox, host=HOST):
    """Uncached ground truth: a 257px request is not grid-aligned, so GWC does not serve it."""
    _, _, data = _curl(f"https://{host}/ows?service=WMS&version=1.1.1&request=GetMap&layers={layer}&styles=&srs=EPSG:3857"
                       f"&bbox={','.join(str(v) for v in bbox)}&width=257&height=257&format=image/png&transparent=true")
    return _nonblank(data)
