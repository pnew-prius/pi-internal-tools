"""
Pipeline data collector.
Reads every zip in tobeprocessed, extracts image count / KML area / metadata,
pairs with DevOps build hours, writes pipeline_runs.json + pipeline_runs.csv.
"""
import json, struct, math, cmath, re, sys, os
from datetime import datetime, timezone
from collections import defaultdict
from azure.identity import AzureCliCredential
from azure.storage.blob import BlobServiceClient
import urllib.request

# ── Config ─────────────────────────────────────────────────────────────────────
ACCOUNT          = "piimageprocessing"
CONTAINER_INPUT  = "tobeprocessed"
CONTAINER_GDAL   = "gdal-processing"
COMPUTE_RATE     = 0.816          # $/hr Standard_F16s_v2 PAYG southcentralus
LICENSE_RATE     = 0.50           # $/hr one-button mosaic software license
EARTH_RADIUS_MI  = 3958.8

DEVOPS_MOSAIC_ORG  = "https://dev.azure.com/PriusIntelli/0709c1b8-2c78-4a24-81b4-af6ac1645690"
DEVOPS_GDAL_ORG    = "https://dev.azure.com/PriusIntelli/5942a494-b65d-4b83-8eb9-ebb6cce89e99"
MOSAIC_PIPE_ID     = 5
GDAL_PIPE_ID       = 12
DEVOPS_RESOURCE    = "499b84ac-1321-427f-aa17-267ca6975798"

OUTPUT_JSON = r"C:\Users\pi\claude\pipeline_runs.json"
OUTPUT_CSV  = r"C:\Users\pi\claude\pipeline_runs.csv"

IMG_EXTS = {"jpg", "jpeg"}

KAPPA_ON_LINE_THRESHOLD = 25.0  # degrees — Kappa must be within this of a primary heading

# ── Auth ───────────────────────────────────────────────────────────────────────
cred     = AzureCliCredential()
svc      = BlobServiceClient(f"https://{ACCOUNT}.blob.core.windows.net", credential=cred)

def devops_token():
    t = cred.get_token(f"{DEVOPS_RESOURCE}/.default")
    return t.token

def devops_get(url, token):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    })
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def devops_get_text(url, token):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "text/plain"
    })
    with urllib.request.urlopen(req) as r:
        return r.read().decode("utf-8", errors="replace")

# ── Zip range reader ───────────────────────────────────────────────────────────
def range_bytes(container, blob_name, offset, length):
    client = svc.get_blob_client(container, blob_name)
    return client.download_blob(offset=offset, length=length).readall()

def zip_central_directory(container, blob_name):
    """Return list of {name, comp_size, comp_method, local_hdr_offset} from zip."""
    client = svc.get_blob_client(container, blob_name)
    size   = client.get_blob_properties().size

    tail_size = min(65536, size)
    tail = range_bytes(container, blob_name, size - tail_size, tail_size)

    cd_offset = cd_size = None

    # ZIP64 locator
    idx64 = tail.rfind(b'\x50\x4b\x06\x07')
    if idx64 != -1:
        eocd64_off = struct.unpack_from('<Q', tail, idx64 + 8)[0]
        eocd64 = range_bytes(container, blob_name, eocd64_off, 56)
        cd_size   = struct.unpack_from('<Q', eocd64, 40)[0]
        cd_offset = struct.unpack_from('<Q', eocd64, 48)[0]
    else:
        idx = tail.rfind(b'\x50\x4b\x05\x06')
        if idx == -1:
            raise RuntimeError(f"EOCD not found in {blob_name}")
        eocd = tail[idx:]
        cd_size   = struct.unpack_from('<I', eocd, 12)[0]
        cd_offset = struct.unpack_from('<I', eocd, 16)[0]

    cd  = range_bytes(container, blob_name, cd_offset, cd_size)
    pos = 0
    entries = []
    sig = b'\x50\x4b\x01\x02'
    while pos <= len(cd) - 46:
        if cd[pos:pos+4] != sig:
            pos += 1
            continue
        comp_method = struct.unpack_from('<H', cd, pos + 10)[0]
        comp_size   = struct.unpack_from('<I', cd, pos + 20)[0]
        local_hdr   = struct.unpack_from('<I', cd, pos + 42)[0]
        fname_len   = struct.unpack_from('<H', cd, pos + 28)[0]
        extra_len   = struct.unpack_from('<H', cd, pos + 30)[0]
        comment_len = struct.unpack_from('<H', cd, pos + 32)[0]
        fname = cd[pos+46 : pos+46+fname_len].decode('utf-8', errors='replace')

        # Resolve ZIP64 local header offset if needed
        if local_hdr == 0xFFFFFFFF:
            xd = cd[pos+46+fname_len : pos+46+fname_len+extra_len]
            ep = 0
            while ep < len(xd) - 4:
                hid  = struct.unpack_from('<H', xd, ep)[0]
                hlen = struct.unpack_from('<H', xd, ep+2)[0]
                if hid == 0x0001 and hlen >= 8:
                    local_hdr = struct.unpack_from('<Q', xd, ep+4)[0]
                    break
                ep += 4 + hlen

        entries.append({
            "name": fname, "comp_size": comp_size,
            "comp_method": comp_method, "local_hdr": local_hdr
        })
        pos += 46 + fname_len + extra_len + comment_len

    return entries

def extract_file(container, blob_name, entry):
    """Download and decompress a single file from a zip."""
    lhdr = range_bytes(container, blob_name, entry["local_hdr"], 30)
    fname_len = struct.unpack_from('<H', lhdr, 26)[0]
    extra_len = struct.unpack_from('<H', lhdr, 28)[0]
    data_offset = entry["local_hdr"] + 30 + fname_len + extra_len
    comp = range_bytes(container, blob_name, data_offset, entry["comp_size"])
    if entry["comp_method"] == 0:
        return comp
    elif entry["comp_method"] == 8:
        import zlib
        return zlib.decompress(comp, -15)
    raise RuntimeError(f"Unsupported compression method {entry['comp_method']}")

# ── KML area calculation ───────────────────────────────────────────────────────
def kml_sq_miles(kml_bytes):
    """Calculate polygon area in sq miles from KML coordinates using Shoelace."""
    txt = kml_bytes.decode('utf-8', errors='replace')
    m = re.search(r'<coordinates>(.*?)</coordinates>', txt, re.DOTALL)
    if not m:
        return None
    raw = m.group(1).strip().split()
    coords = []
    for pt in raw:
        parts = pt.split(',')
        if len(parts) >= 2:
            try:
                coords.append((float(parts[0]), float(parts[1])))  # lon, lat
            except ValueError:
                pass
    if len(coords) < 3:
        return None

    avg_lat  = sum(lat for _, lat in coords) / len(coords)
    lat_rad  = math.radians(avg_lat)
    mi_per_deg_lat = EARTH_RADIUS_MI * math.pi / 180
    mi_per_deg_lon = EARTH_RADIUS_MI * math.cos(lat_rad) * math.pi / 180

    # Shoelace on projected coords
    area = 0.0
    n = len(coords)
    for i in range(n):
        j = (i + 1) % n
        xi = (coords[i][0] - coords[0][0]) * mi_per_deg_lon
        yi = (coords[i][1] - coords[0][1]) * mi_per_deg_lat
        xj = (coords[j][0] - coords[0][0]) * mi_per_deg_lon
        yj = (coords[j][1] - coords[0][1]) * mi_per_deg_lat
        area += xi * yj - xj * yi

    return round(abs(area) / 2, 3)

# ── Flight metrics from mosaic log ────────────────────────────────────────────
def haversine_mi(lon1, lat1, lon2, lat2):
    """Great-circle distance in miles between two lon/lat points."""
    r = EARTH_RADIUS_MI
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return 2 * r * math.asin(math.sqrt(a))

def angular_delta(a, b):
    """Smallest angle between two headings in degrees [0-180]."""
    d = abs(a - b) % 360
    return d if d <= 180 else 360 - d

def circular_mean_deg(angles_deg):
    """Circular mean of a list of angles in degrees, returned in [0, 360)."""
    z = sum(cmath.exp(1j * math.radians(a)) for a in angles_deg)
    return math.degrees(cmath.phase(z)) % 360

def primary_headings(kappas):
    """
    Find the two primary flight headings from Kappa values using the
    doubled-angle trick: doubling maps reciprocal headings to the same
    direction so the circular mean finds the flight axis regardless of
    orientation (E-W, N-S, or any oblique).

    Returns (h1, h2) — the refined cluster means, both in [0, 360).
    h1 is the canonical heading in [0, 180).
    """
    # Step 1: doubled-angle circular mean → flight axis
    doubled = [(k * 2) % 360 for k in kappas]
    axis = circular_mean_deg(doubled) / 2          # back to [0, 180)
    h1_init = axis % 360
    h2_init = (axis + 180) % 360

    # Step 2: assign each image to the nearer primary heading
    c1 = [k for k in kappas if angular_delta(k, h1_init) <= angular_delta(k, h2_init)]
    c2 = [k for k in kappas if angular_delta(k, h2_init) <  angular_delta(k, h1_init)]

    # Step 3: refine by circular mean of each cluster
    h1 = round(circular_mean_deg(c1), 1) if c1 else round(h1_init, 1)
    h2 = round(circular_mean_deg(c2), 1) if c2 else round(h2_init, 1)
    return h1, h2

def on_flight_line(kappa, h1, h2):
    """True if Kappa is within threshold of either primary heading."""
    return (angular_delta(kappa, h1) <= KAPPA_ON_LINE_THRESHOLD or
            angular_delta(kappa, h2) <= KAPPA_ON_LINE_THRESHOLD)

def mosaic_flight_metrics(build_id, token):
    """
    Parse GPS CSV rows from mosaic build log 7 (Filename,Lon,Lat,Alt,Omega,Phi,Kappa,...).
    Uses Kappa heading to identify flight lines vs turns.
    Returns dict with CollectionSqMiles, CollectionLinearMiles, FlightDirection.
    """
    result = {"CollectionSqMiles": None, "CollectionLinearMiles": None,
              "FlightDirection": None, "GsdCm": None}
    try:
        log_url = f"{DEVOPS_MOSAIC_ORG}/_apis/build/builds/{build_id}/logs/7"
        lines = devops_get_text(log_url, token).splitlines()

        # Parse GPS CSV rows: timestamp + "Filename,Lon,Lat,Alt,Omega,Phi,Kappa,..."
        GPS_RE = re.compile(
            r'\S+_cal\.jpg,([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+)'
        )
        rows = []   # (lon, lat, kappa) in sequence-number order
        for line in lines:
            m = GPS_RE.search(line)
            if m:
                rows.append((float(m.group(1)), float(m.group(2)), float(m.group(6))))

        if len(rows) < 2:
            return result

        lons   = [r[0] for r in rows]
        lats   = [r[1] for r in rows]
        kappas = [r[2] for r in rows]

        # ── GSD (Ground Sample Distance) ──────────────────────────────────────
        gsd_match = next((re.search(r'GSD = ([\d.]+)', l) for l in lines
                          if re.search(r'GSD = ([\d.]+)', l)), None)
        if gsd_match:
            result["GsdCm"] = round(float(gsd_match.group(1)) / 10, 2)  # mm → cm

        # ── Collection bounding box sq miles ──────────────────────────────────
        width_mi  = haversine_mi(min(lons), min(lats), max(lons), min(lats))
        height_mi = haversine_mi(min(lons), min(lats), min(lons), max(lats))
        result["CollectionSqMiles"] = round(width_mi * height_mi, 3)

        # ── Primary flight headings from Kappa ────────────────────────────────
        kappas_norm = [k % 360 for k in kappas]   # normalize to [0, 360)
        h1, h2 = primary_headings(kappas_norm)
        # FlightDirection: canonical heading in [0, 180) — describes the flight axis
        canonical = h1 if h1 < 180 else h1 - 180
        result["FlightDirection"] = round(canonical, 1)

        # ── Collection linear miles (on-line segments only) ───────────────────
        linear_mi = 0.0
        for i in range(len(rows) - 1):
            lon1, lat1, k1 = rows[i]
            lon2, lat2, k2 = rows[i + 1]
            # Both endpoints must be on a flight line (use normalized Kappa)
            if on_flight_line(k1 % 360, h1, h2) and on_flight_line(k2 % 360, h1, h2):
                linear_mi += haversine_mi(lon1, lat1, lon2, lat2)

        result["CollectionLinearMiles"] = round(linear_mi, 3)

    except Exception as e:
        print(f"  [flight metrics error: {e}]", end="", flush=True)

    return result


# ── DevOps helpers ─────────────────────────────────────────────────────────────
def dur_hrs(build):
    if build.get("finishTime") and build.get("startTime"):
        fmt = "%Y-%m-%dT%H:%M:%S.%f" if "." in build["startTime"] else "%Y-%m-%dT%H:%M:%S"
        try:
            start = datetime.strptime(build["startTime"][:26].rstrip("Z"), fmt.rstrip("Z").rstrip("%f").rstrip("."))
        except Exception:
            start = datetime.fromisoformat(build["startTime"].replace("Z",""))
        try:
            finish = datetime.fromisoformat(build["finishTime"].replace("Z",""))
            start  = datetime.fromisoformat(build["startTime"].replace("Z",""))
        except Exception:
            return None
        return round((finish - start).total_seconds() / 3600, 4)
    return None

def tile_key_from_build(build_number):
    return re.sub(r'^[^-]+-', '', build_number)

def fetch_builds(org_url, pipe_id, token):
    """Fetch all available builds — no date filter, up to 500."""
    url = f"{org_url}/_apis/build/builds?definitions={pipe_id}&$top=500&api-version=7.1"
    resp = devops_get(url, token)
    return resp.get("value", [])


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print("Acquiring DevOps token...")
    token = devops_token()

    print("Fetching Mosaic (one-button) builds...")
    mosaic_builds = fetch_builds(DEVOPS_MOSAIC_ORG, MOSAIC_PIPE_ID, token)
    print(f"  {len(mosaic_builds)} mosaic builds")

    print("Fetching GDAL builds...")
    gdal_builds = fetch_builds(DEVOPS_GDAL_ORG, GDAL_PIPE_ID, token)
    print(f"  {len(gdal_builds)} GDAL builds")

    # Index by tile key — keep all (including re-trims, failures)
    mosaic_by_tile = defaultdict(list)
    for b in mosaic_builds:
        mosaic_by_tile[tile_key_from_build(b["buildNumber"])].append(b)

    gdal_by_tile = defaultdict(list)
    for b in gdal_builds:
        gdal_by_tile[tile_key_from_build(b["buildNumber"])].append(b)

    # Index available input zips for enrichment
    print(f"\nListing {CONTAINER_INPUT} zips...")
    container_client = svc.get_container_client(CONTAINER_INPUT)
    available_zips = {b.name.replace(".zip","") for b in container_client.list_blobs()
                      if b.name.endswith(".zip")}
    print(f"  {len(available_zips)} zips available for enrichment")

    print(f"  {len(available_zips)} tiles with zip data (development dataset)")

    records = []

    for tile_key in sorted(available_zips):
        print(f"\n[{tile_key}]", end="", flush=True)

        blob_name   = tile_key + ".zip"
        image_count = sq_miles = customer = project = grid_number = None

        try:
            entries = zip_central_directory(CONTAINER_INPUT, blob_name)

            image_count = sum(
                1 for e in entries
                if e["name"].rsplit(".", 1)[-1].lower() in IMG_EXTS
            )
            print(f"  {image_count} images", end="", flush=True)

            kml_entry = next((e for e in entries if e["name"].lower().endswith(".kml")), None)
            if kml_entry:
                kml_bytes = extract_file(CONTAINER_INPUT, blob_name, kml_entry)
                sq_miles  = kml_sq_miles(kml_bytes)
                print(f"  {sq_miles} sq mi", end="", flush=True)

            json_entry = next((e for e in entries if e["name"].lower().endswith(".json")), None)
            if json_entry:
                jdata       = json.loads(extract_file(CONTAINER_INPUT, blob_name, json_entry))
                customer    = jdata.get("Customer")
                project     = jdata.get("Project")
                grid_number = jdata.get("GridNumber")
        except Exception as e:
            print(f"  zip error: {e}", end="", flush=True)
            continue

        # DevOps builds for this tile
        m_builds = mosaic_by_tile.get(tile_key, [])
        g_builds = gdal_by_tile.get(tile_key, [])

        mosaic_runs = sorted(m_builds, key=lambda b: b.get("startTime",""))
        gdal_runs   = sorted(g_builds, key=lambda b: b.get("startTime",""))

        if not mosaic_runs and not gdal_runs:
            print("  no builds", end="")
            continue

        # Build records — one per mosaic run (+ any extra GDAL-only runs as re-trims)
        paired_gdal_ids = set()

        for mb in mosaic_runs:
            m_hrs    = dur_hrs(mb)
            m_result = mb.get("result")
            m_id     = mb.get("id")

            # Find closest GDAL run that finished after this mosaic started
            m_start = mb.get("startTime","")
            matched_gdal = None
            for gb in gdal_runs:
                if gb["id"] not in paired_gdal_ids and gb.get("startTime","") >= m_start:
                    matched_gdal = gb
                    break

            g_hrs = g_result = g_id = None
            is_retrim = False
            if matched_gdal:
                g_hrs    = dur_hrs(matched_gdal)
                g_result = matched_gdal.get("result")
                g_id     = matched_gdal.get("id")
                paired_gdal_ids.add(g_id)

            m_hrs_val = m_hrs if m_hrs else 0
            g_hrs_val = g_hrs if g_hrs else 0
            total_hrs = round(m_hrs_val + g_hrs_val, 4)
            compute_cost = round(total_hrs * COMPUTE_RATE, 2)
            failed = (m_result and m_result != "succeeded") or \
                     (g_result and g_result != "succeeded")

            # Flight metrics from mosaic log (only for succeeded runs)
            flight = {"CollectionSqMiles": None, "CollectionLinearMiles": None,
                      "FlightDirection": None, "GsdCm": None}
            if m_id and m_result == "succeeded":
                print(f"  [log]", end="", flush=True)
                flight = mosaic_flight_metrics(m_id, token)

            license_cost         = round(m_hrs_val * LICENSE_RATE, 2)
            cost_per_img         = round(compute_cost / image_count, 4) if image_count else None
            cost_per_sq_mi       = round(compute_cost / sq_miles, 4)    if sq_miles   else None
            cost_per_coll_sq_mi  = round(compute_cost / flight["CollectionSqMiles"], 4) \
                                   if flight["CollectionSqMiles"] else None
            cost_per_linear_mi   = round(compute_cost / flight["CollectionLinearMiles"], 4) \
                                   if flight["CollectionLinearMiles"] else None

            run_date = mb.get("finishTime") or mb.get("startTime")

            records.append({
                "CollectedAt":           datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "RunDate":               run_date,
                "TileKey":               tile_key,
                "Customer":              customer,
                "Project":               project,
                "GridNumber":            grid_number,
                "IsRetrim":              False,
                "Excluded":              False,
                "ExcludedNote":          None,
                "MosaicBuildId":         m_id,
                "GdalBuildId":           g_id,
                "MosaicResult":          m_result,
                "GdalResult":            g_result,
                "Failed":                failed,
                "MosaicHrs":             m_hrs,
                "GdalHrs":               g_hrs,
                "TotalHrs":              total_hrs,
                "ImageCount":            image_count,
                "AoiSqMiles":            sq_miles,
                "CollectionSqMiles":     flight["CollectionSqMiles"],
                "CollectionLinearMiles": flight["CollectionLinearMiles"],
                "FlightDirection":       flight["FlightDirection"],
                "GsdCm":                flight["GsdCm"],
                "ComputeCost":           compute_cost,
                "LicenseCost":           license_cost,
                "CostPerImage":          cost_per_img,
                "CostPerAoiSqMi":        cost_per_sq_mi,
                "CostPerCollSqMi":       cost_per_coll_sq_mi,
                "CostPerLinearMi":       cost_per_linear_mi,
            })
            print(f"  mosaic={m_result} gdal={g_result} {total_hrs}hrs ${compute_cost}", end="", flush=True)

        # Remaining GDAL runs (re-trims — no paired mosaic)
        for gb in gdal_runs:
            if gb["id"] in paired_gdal_ids:
                continue
            g_hrs    = dur_hrs(gb)
            g_result = gb.get("result")
            g_id     = gb.get("id")
            g_hrs_v  = g_hrs if g_hrs else 0
            compute_cost = round(g_hrs_v * COMPUTE_RATE, 2)
            run_date = gb.get("finishTime") or gb.get("startTime")

            records.append({
                "CollectedAt":           datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "RunDate":               run_date,
                "TileKey":               tile_key,
                "Customer":              customer,
                "Project":               project,
                "GridNumber":            grid_number,
                "IsRetrim":              True,
                "Excluded":              False,
                "ExcludedNote":          None,
                "MosaicBuildId":         None,
                "GdalBuildId":           g_id,
                "MosaicResult":          None,
                "GdalResult":            g_result,
                "Failed":                g_result != "succeeded" if g_result else False,
                "MosaicHrs":             None,
                "GdalHrs":               g_hrs,
                "TotalHrs":              g_hrs_v,
                "ImageCount":            image_count,
                "AoiSqMiles":            sq_miles,
                "CollectionSqMiles":     None,
                "CollectionLinearMiles": None,
                "FlightDirection":       None,
                "GsdCm":                None,
                "ComputeCost":           compute_cost,
                "LicenseCost":           None,
                "CostPerImage":          None,
                "CostPerAoiSqMi":        None,
                "CostPerCollSqMi":       None,
                "CostPerLinearMi":       None,
            })
            print(f"  [retrim] gdal={g_result} {g_hrs_v}hrs ${compute_cost}", end="", flush=True)

        print()

    # ── Save ───────────────────────────────────────────────────────────────────
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, default=str)

    # CSV
    if records:
        import csv
        keys = list(records[0].keys())
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for r in records:
                w.writerow({k: ("" if v is None else v) for k, v in r.items()})

    print(f"\nDone. {len(records)} records written.")
    print(f"JSON: {OUTPUT_JSON}")
    print(f"CSV:  {OUTPUT_CSV}")

    # ── Summary ────────────────────────────────────────────────────────────────
    eligible = [r for r in records if not r["Excluded"] and not r["Failed"] and not r["IsRetrim"]]
    if eligible:
        total_cost      = round(sum(r["ComputeCost"] for r in eligible), 2)
        total_images    = sum(r["ImageCount"] or 0 for r in eligible)
        aoi_sq_mi       = round(sum(r["AoiSqMiles"] or 0 for r in eligible), 2)
        coll_sq_mi      = round(sum(r["CollectionSqMiles"] or 0 for r in eligible), 2)
        linear_mi       = round(sum(r["CollectionLinearMiles"] or 0 for r in eligible), 2)
        total_hrs       = round(sum(r["TotalHrs"] for r in eligible), 2)
        retrims         = sum(1 for r in records if r["IsRetrim"])
        failures        = sum(1 for r in records if r["Failed"])

        print(f"\n=== Summary ({len(eligible)} standard runs) ===")
        print(f"  Tiles:              {len(eligible)}")
        print(f"  Images:             {total_images:,}")
        print(f"  AOI sq miles:       {aoi_sq_mi}")
        print(f"  Collection sq mi:   {coll_sq_mi}")
        print(f"  Collection lin mi:  {linear_mi}")
        print(f"  Compute hrs:        {total_hrs}")
        print(f"  Compute cost:       ${total_cost:,}")
        print(f"  Re-trims:           {retrims}")
        print(f"  Failures:           {failures}")
        if total_images:
            print(f"  $/image:            ${round(total_cost/total_images, 4)}")
        if aoi_sq_mi:
            print(f"  $/AOI sq mile:      ${round(total_cost/aoi_sq_mi, 4)}")
        if coll_sq_mi:
            print(f"  $/coll sq mile:     ${round(total_cost/coll_sq_mi, 4)}")
        if linear_mi:
            print(f"  $/linear mile:      ${round(total_cost/linear_mi, 4)}")

if __name__ == "__main__":
    main()
