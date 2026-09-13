"""
GeoServer tile pre-seeding cost estimator.

Inputs:
  --workspace   GeoServer workspace name (pulls coverage bboxes via REST)
  --gsd         Source imagery GSD in meters (e.g. 0.11 for 11cm)
  --format      Tile format: jpeg or png (default: jpeg)
  --min-zoom    Minimum zoom level to seed (default: 14)
  --max-zoom    Override max zoom (default: derived from GSD)
  --threads     GWC seed thread count (default: 4)

Outputs:
  - Per-zoom tile count, storage estimate, seed time, compute cost
  - Totals and recommendation
"""

import argparse
import math
import sys
import json
import subprocess
import urllib.request
import urllib.parse
import base64

GEOSERVER_URL = "https://devimageservices.priusintelli.com"
GEOSERVER_USER = "geoadmin"
GEOSERVER_PASS = "Ag3CtKS93hhnxLBX"

VM_RATE_PER_HR  = 0.169   # Standard_F4s_v2 PAYG southcentralus
STORAGE_RATE_GB = 0.018   # Hot LRS $/GB/month
TILE_PX         = 256     # tile width/height in pixels
BASE_RESOLUTION = 156543.03392  # WebMercator meters/pixel at zoom 0

# Empirically determined GSD (m) -> max useful zoom mapping.
# Sorted ascending by GSD. Values between entries are interpolated.
GSD_ZOOM_TABLE = [
    (0.025, 22),
    (0.050, 21),
    (0.075, 20),
    (0.100, 20),
    (0.150, 20),
]


def gs_get(path):
    url = f"{GEOSERVER_URL}{path}"
    result = subprocess.run(
        ["curl.exe", "-s", "-u", f"{GEOSERVER_USER}:{GEOSERVER_PASS}", url],
        capture_output=True, text=True, timeout=30
    )
    return json.loads(result.stdout)


def max_useful_zoom(gsd_m):
    """
    Highest useful zoom for the given GSD, from empirical lookup table.
    Clamps to table bounds; interpolates (floor) between defined entries.
    """
    if gsd_m <= GSD_ZOOM_TABLE[0][0]:
        return GSD_ZOOM_TABLE[0][1]
    if gsd_m >= GSD_ZOOM_TABLE[-1][0]:
        return GSD_ZOOM_TABLE[-1][1]
    for i in range(len(GSD_ZOOM_TABLE) - 1):
        g0, z0 = GSD_ZOOM_TABLE[i]
        g1, z1 = GSD_ZOOM_TABLE[i + 1]
        if g0 <= gsd_m <= g1:
            # Linear interpolation, floored to integer zoom
            t = (gsd_m - g0) / (g1 - g0)
            return math.floor(z0 + t * (z1 - z0))


def tile_size_m(zoom):
    """WebMercator tile width/height in meters at given zoom."""
    return TILE_PX * BASE_RESOLUTION / (2 ** zoom)


def tiles_for_bbox(min_lon, max_lon, min_lat, max_lat, zoom):
    """Number of 256px WebMercator tiles covering a WGS84 bounding box."""
    mid_lat  = (min_lat + max_lat) / 2
    width_m  = (max_lon - min_lon) * math.cos(math.radians(mid_lat)) * 111320
    height_m = (max_lat - min_lat) * 111320
    tsm = tile_size_m(zoom)
    tx  = math.ceil(width_m  / tsm)
    ty  = math.ceil(height_m / tsm)
    return max(tx, 1) * max(ty, 1)


def tile_size_kb(zoom, gsd_m, fmt):
    """
    Estimate JPEG/PNG tile size in KB.

    Model: tile size peaks near native resolution zoom, falls off above and below.
    Anchored at measured z16 JPEG = 13.6 KB for typical aerial imagery.
    Scale by zoom distance from native zoom and format.

    For PNG, apply a 2.5x multiplier (lossless vs lossy).
    """
    native_zoom = max_useful_zoom(gsd_m)
    # Relative zoom: 0 = native resolution, negative = overview, positive = upsampled
    delta = zoom - native_zoom

    if delta <= 0:
        # Overview tiles — content detail increases toward native zoom
        # Each step toward native roughly doubles detail (and file size)
        # Anchor: at native zoom, JPEG ~60 KB for 11cm aerial
        native_kb = 60.0
        kb = native_kb * (2 ** (delta * 0.7))
    else:
        # Above native — upsampled, blocky, compresses very well
        native_kb = 60.0
        kb = native_kb * (0.5 ** delta)

    kb = max(kb, 2.0)

    if fmt == "png":
        kb *= 2.5

    return round(kb, 1)


def seed_rate_tiles_per_min(zoom, gsd_m, threads):
    """
    Estimated seeding throughput in tiles/min (all threads combined).

    COG blob backend: throughput is I/O bound at high zoom (many small range reads),
    CPU bound at low zoom (fewer tiles, larger decompression area).
    Native zoom is the slowest per-tile (maximum data read per tile).
    """
    native_zoom = max_useful_zoom(gsd_m)
    delta = zoom - native_zoom

    if delta <= -4:
        base = 600   # deep overviews: fast, data already cached in COG overviews
    elif delta <= -2:
        base = 400
    elif delta <= 0:
        base = 150   # near native: most I/O per tile
    else:
        base = 80    # upsampled: more tiles but tiny data reads — blob ops dominate

    return base * threads


def get_workspace_bboxes(workspace):
    """Pull lat/lon bounding boxes for all coverages in a workspace."""
    print(f"  Fetching coverage list for {workspace}...")
    data = gs_get(f"/rest/workspaces/{workspace}/coveragestores.json")
    stores = data["coverageStores"]["coverageStore"]
    bboxes = []
    for s in stores:
        name = s["name"]
        try:
            cov = gs_get(
                f"/rest/workspaces/{workspace}/coveragestores/{name}"
                f"/coverages/{name}.json"
            )
            bb = cov["coverage"]["latLonBoundingBox"]
            bboxes.append({
                "name": name,
                "minX": bb["minx"], "maxX": bb["maxx"],
                "minY": bb["miny"], "maxY": bb["maxy"],
            })
        except Exception as e:
            print(f"  Warning: could not fetch bbox for {name}: {e}")
    return bboxes


def run(workspace, gsd_m, fmt, min_zoom, max_zoom_override, threads):
    print(f"\nGeoServer Tile Pre-Seeding Cost Estimator")
    print(f"  Workspace : {workspace}")
    print(f"  GSD       : {gsd_m}m")
    print(f"  Format    : {fmt.upper()}")
    print(f"  Threads   : {threads} (Standard_F4s_v2, {threads} vCPUs active)")

    native_zoom = max_useful_zoom(gsd_m)
    max_zoom    = max_zoom_override if max_zoom_override is not None else native_zoom
    print(f"  Native zoom (from GSD): z{native_zoom}  |  Seeding to: z{max_zoom}")

    if max_zoom > native_zoom:
        print(f"  WARNING: z{max_zoom} > native z{native_zoom} — tiles above z{native_zoom} will be upsampled")

    print(f"\nFetching coverage bounding boxes...")
    bboxes = get_workspace_bboxes(workspace)
    print(f"  Found {len(bboxes)} coverages")

    zoom_range = range(min_zoom, max_zoom + 1)

    # Compute per-zoom totals across all coverage strips
    totals = {}
    for z in zoom_range:
        count = sum(tiles_for_bbox(b["minX"], b["maxX"], b["minY"], b["maxY"], z)
                    for b in bboxes)
        tkb   = tile_size_kb(z, gsd_m, fmt)
        gb    = count * tkb / (1024 * 1024)     # KB -> GB
        rate  = seed_rate_tiles_per_min(z, gsd_m, threads)
        mins  = count / rate
        hrs   = mins / 60
        totals[z] = dict(count=count, tkb=tkb, gb=gb, hrs=hrs)

    # Print table
    print(f"\n{'Zoom':>4} | {'Tiles':>12} | {'KB/tile':>7} | {'Storage GB':>10} | "
          f"{'Seed hrs':>8} | {'Compute $':>9} | {'Storage $/mo':>12}")
    print("-" * 80)

    grand_tiles = 0
    grand_gb    = 0.0
    grand_hrs   = 0.0

    for z in zoom_range:
        t  = totals[z]
        compute = round(t["hrs"] * VM_RATE_PER_HR, 2)
        storage = round(t["gb"]  * STORAGE_RATE_GB, 2)
        marker  = " << native" if z == native_zoom else ""
        print(f"  z{z:>2} | {t['count']:>12,} | {t['tkb']:>6.1f}K | {t['gb']:>9.1f} | "
              f"{t['hrs']:>8.1f} | ${compute:>8.2f} | ${storage:>11.2f}{marker}")
        grand_tiles += t["count"]
        grand_gb    += t["gb"]
        grand_hrs   += t["hrs"]

    grand_compute = round(grand_hrs   * VM_RATE_PER_HR,  2)
    grand_storage = round(grand_gb    * STORAGE_RATE_GB, 2)

    print("-" * 80)
    print(f"{'TOTAL':>5}   {grand_tiles:>12,}           {grand_gb:>9.1f} | "
          f"{grand_hrs:>8.1f} | ${grand_compute:>8.2f} | ${grand_storage:>11.2f}")

    print(f"""
Summary
  Total tiles to seed : {grand_tiles:,}
  Cache storage       : {grand_gb:.1f} GB  ->  ${grand_storage:.2f}/month ongoing
  One-time seed cost  : {grand_hrs:.1f} hrs compute  ->  ${grand_compute:.2f}
  Break-even (months) : {round(grand_compute / grand_storage, 1) if grand_storage > 0 else 'N/A'} months of storage = seed compute cost

Notes
  - Tile sizes are estimates; run a small test seed to calibrate (see --help)
  - Seed rate assumes {threads}-thread GWC on Standard_F4s_v2 with COG Azure blob backend
  - Storage rate: ${STORAGE_RATE_GB}/GB/month (Hot LRS)
  - VM rate: ${VM_RATE_PER_HR}/hr (Standard_F4s_v2 PAYG southcentralus)
  - Actual tile sizes vary by image content complexity and JPEG quality setting
""")


def main():
    p = argparse.ArgumentParser(
        description="Estimate GeoServer GWC pre-seeding storage and compute costs.",
        epilog="""
Examples:
  # 11cm imagery, JPEG, z14-z20 (native)
  python geoserver_seed_cost.py --workspace WW-BCOMB-Test --gsd 0.11

  # 5cm imagery, PNG, forced to z19
  python geoserver_seed_cost.py --workspace COPE-S26 --gsd 0.05 --format png --max-zoom 19

  # 1m imagery, JPEG, z14-z18
  python geoserver_seed_cost.py --workspace SOME-WS --gsd 1.0 --max-zoom 18
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--workspace", required=True,          help="GeoServer workspace name")
    p.add_argument("--gsd",       required=True, type=float, help="Source imagery GSD in meters")
    p.add_argument("--format",    default="jpeg", choices=["jpeg","png"], help="Tile format")
    p.add_argument("--min-zoom",  default=10,    type=int, help="Minimum zoom level (default: 10)")
    p.add_argument("--max-zoom",  default=None,  type=int, help="Max zoom override (default: derived from GSD)")
    p.add_argument("--threads",   default=4,     type=int, help="GWC seed thread count (default: 4)")
    args = p.parse_args()

    run(
        workspace       = args.workspace,
        gsd_m           = args.gsd,
        fmt             = args.format,
        min_zoom        = args.min_zoom,
        max_zoom_override = args.max_zoom,
        threads         = args.threads,
    )


if __name__ == "__main__":
    main()
