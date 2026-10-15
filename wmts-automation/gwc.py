"""GeoWebCache helpers: tile-layer config (XML), bounded truncate/seed, EPSG:3857 footprints."""
import time

from pyproj import Transformer

from gs_client import call


def bbox_to_3857(bb, src_epsg):
    """bb: dict with minx,miny,maxx,maxy in src_epsg -> [minx,miny,maxx,maxy] in EPSG:3857 (densified edges)."""
    t = Transformer.from_crs(src_epsg, 3857, always_xy=True)
    xs, ys, n = [], [], 20
    for i in range(n + 1):
        f = i / n
        for x, y in ((bb["minx"] + f * (bb["maxx"] - bb["minx"]), bb["miny"]), (bb["minx"] + f * (bb["maxx"] - bb["minx"]), bb["maxy"]),
                     (bb["minx"], bb["miny"] + f * (bb["maxy"] - bb["miny"])), (bb["maxx"], bb["miny"] + f * (bb["maxy"] - bb["miny"]))):
            X, Y = t.transform(x, y)
            xs.append(X)
            ys.append(Y)
    return [min(xs), min(ys), max(xs), max(ys)]


def set_tile_layer_xml(env, layer, ext3857, formats=("image/png",), gridset="EPSG:3857", meta=(4, 4), expire_clients=0):
    """GWC's JSON layer config duplicates list fields on write-back, so the XML form is required."""
    xml = ("<GeoServerLayer><enabled>true</enabled><name>%s</name><mimeFormats>%s</mimeFormats>"
           "<gridSubsets><gridSubset><gridSetName>%s</gridSetName><extent><coords>%s</coords></extent></gridSubset></gridSubsets>"
           "<metaWidthHeight><int>%d</int><int>%d</int></metaWidthHeight><expireCache>0</expireCache><expireClients>%d</expireClients>"
           "<gutter>0</gutter></GeoServerLayer>") % (
        layer, "".join(f"<string>{f}</string>" for f in formats), gridset,
        "".join(f"<double>{v}</double>" for v in ext3857), meta[0], meta[1], expire_clients)
    return call(env, "PUT", f"/gwc/rest/layers/{layer}.xml", xml, ctype="text/xml", accept="text/xml")


def seed_request(env, layer, kind, bbox, z0, z1, fmt="image/png", gridset="EPSG:3857", threads=2):
    """kind: 'seed' (fill missing), 'reseed', or 'truncate'. bbox is in the gridset's CRS (3857)."""
    body = {"seedRequest": {"name": layer, "bounds": {"coords": {"double": [str(v) for v in bbox]}}, "gridSetId": gridset,
                            "zoomStart": z0, "zoomStop": z1, "format": fmt, "type": kind, "threadCount": threads}}
    return call(env, "POST", f"/gwc/rest/seed/{layer}.json", body)


def wait_seed_idle(env, layer, timeout=3600, poll=1.5, appear_grace=6.0):
    """Block until the seed/truncate just submitted for the layer has finished. Returns the largest job total seen.
    GWC lists a task only once it is scheduled, so an empty list straight after a POST does not mean done: wait up to
    appear_grace seconds for a task to show up (a task that finishes before the first look is never seen; that is fine)."""
    peak, seen, t0 = 0, False, time.time()
    while time.time() - t0 < timeout:
        s = call(env, "GET", f"/gwc/rest/seed/{layer}.json")[1]
        tasks = s.get("long-array-array", []) if isinstance(s, dict) else []
        if tasks:
            seen = True
            peak = max(peak, max(t[1] for t in tasks))
        elif seen or time.time() - t0 >= appear_grace:
            return peak
        time.sleep(poll)
    raise TimeoutError(f"seed on {layer} exceeded {timeout}s")
