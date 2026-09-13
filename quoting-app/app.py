"""
Tile Cache Quoting Tool — local Flask prototype.
Upload a KML or Shapefile (zipped), select GSD, get a PDF cost report.
"""

import io, json, math, os, tempfile, zipfile, concurrent.futures
from datetime import date

from PIL import Image
from pyproj import Transformer

from flask import Flask, request, send_file, render_template_string

# KML / shapefile parsers
import fastkml, shapefile as pyshp
from lxml import etree

# PDF / cost logic (reused from gsd_cost_table)
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, HRFlowable)
from reportlab.platypus import Image as RLImage

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024   # 50 MB upload limit

# ── Cost constants ─────────────────────────────────────────────────────────────
BASE_RES       = 156543.03392
TILE_PX        = 256
VM_RATE        = 0.169        # Standard_F4s_v2 PAYG southcentralus $/hr (seeding VM — pi-geoserver03/04)
STOR_RATE      = 0.018        # Azure Hot LRS $/GB/month
EGRESS_RATE    = 0.087        # Azure internet egress $/GB (first 10TB)
STOR_WRITE_RATE = 0.065 / 10000  # Azure Blob write transactions $/op (Hot LRS)
LB_RATE        = 0.025        # Azure Load Balancer $/hr (scale set only)
THREADS        = 4            # GWC seed threads per VM (= vCPU count on F4s_v2)
MAX_VMS        = 15           # Maximum seeding fleet size
MIN_ZOOM       = 10

# Measured tile sizes (BCOMB 10cm imagery, 1-PI-WMQ grid set, July 2026)
# JPEG imagery-only averages by zoom delta from native (delta = z - native_z)
JPEG_KB_MEASURED = {
    -10: 3.7, -8: 3.6, -6: 4.2, -5: 5.1,
    -4: 6.3, -3: 8.1, -2: 9.3, -1: 10.5, 0: 12.5
}
# PNG imagery-only averages by zoom delta
PNG_KB_MEASURED = {
    -10: 6.3, -8: 12.2, -6: 28.0, -5: 43.6,
    -4: 61.3, -3: 86.4, -2: 109.5, -1: 138.7, 0: 148.4
}

GSD_ZOOM_TABLE = [
    (0.025, 22),
    (0.050, 21),
    (0.075, 20),
    (0.100, 20),
    (0.150, 20),
]

GSD_LABELS = {
    0.025: "2.5 cm",
    0.050: "5 cm",
    0.075: "7.5 cm",
    0.100: "10 cm",
    0.150: "15 cm",
}

# ── Colours ────────────────────────────────────────────────────────────────────
DARK_BLUE   = colors.HexColor("#1e3a5f")
MID_BLUE    = colors.HexColor("#2563eb")
LIGHT_BLUE  = colors.HexColor("#dbeafe")
ACCENT      = colors.HexColor("#0ea5e9")
ORANGE      = colors.HexColor("#ea580c")
GRAY_BG     = colors.HexColor("#f8fafc")
GRAY_BORDER = colors.HexColor("#e2e8f0")
PNG_BG      = colors.HexColor("#fef9c3")
TEXT_DARK   = colors.HexColor("#0f172a")
TEXT_MID    = colors.HexColor("#475569")
WHITE       = colors.white

# ── Geometry helpers ───────────────────────────────────────────────────────────
def _extract_polygons_from_geom(geom):
    """Return list of polygon ring coord lists from a geometry object."""
    polys = []
    if hasattr(geom, "geoms"):
        for g in geom.geoms:
            polys.extend(_extract_polygons_from_geom(g))
    elif hasattr(geom, "exterior"):
        polys.append(list(geom.exterior.coords))
    elif hasattr(geom, "coords"):
        polys.append(list(geom.coords))
    return polys


def parse_kml(data: bytes):
    kml = fastkml.KML().from_string(data)
    polygons = []

    def walk(features):
        for f in features:
            if hasattr(f, "features") and f.features:
                walk(f.features)
            if hasattr(f, "geometry") and f.geometry:
                polygons.extend(_extract_polygons_from_geom(f.geometry))

    walk(list(kml.features))
    if not polygons:
        raise ValueError("No geometry found in KML")
    return polygons


def parse_shapefile(data: bytes):
    polygons = []
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(tmp)
        shp_files = [f for f in os.listdir(tmp) if f.lower().endswith(".shp")]
        if not shp_files:
            raise ValueError("No .shp file found in ZIP")
        base = os.path.splitext(shp_files[0])[0]
        prj_path = os.path.join(tmp, base + ".prj")

        # Read projection and set up transformer to WGS84 if needed
        transformer = None
        if os.path.exists(prj_path):
            with open(prj_path) as f:
                prj_wkt = f.read()
            try:
                transformer = Transformer.from_crs(prj_wkt, "EPSG:4326", always_xy=True)
            except Exception:
                pass

        sf = pyshp.Reader(os.path.join(tmp, shp_files[0]))
        shapes = sf.shapes()
        sf.close()
        for shape in shapes:
            if not shape.points:
                continue
            pts = [(p[0], p[1]) for p in shape.points]
            if transformer:
                pts = [transformer.transform(x, y) for x, y in pts]
            polygons.append(pts)
    if not polygons:
        raise ValueError("No shapes found in shapefile")
    return polygons


def parse_upload(filename: str, data: bytes):
    """Returns (bboxes, polygons). bboxes = [(minx,maxx,miny,maxy)...], polygons = [[(lon,lat)...]]"""
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "kml":
        polygons = parse_kml(data)
    elif ext == "zip":
        polygons = parse_shapefile(data)
    elif ext == "kmz":
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            kml_name = next((n for n in zf.namelist() if n.lower().endswith(".kml")), None)
            if not kml_name:
                raise ValueError("No .kml found inside KMZ")
            polygons = parse_kml(zf.read(kml_name))
    else:
        raise ValueError(f"Unsupported file type: .{ext}")

    bboxes = []
    for poly in polygons:
        lons = [p[0] for p in poly]
        lats = [p[1] for p in poly]
        bboxes.append((min(lons), max(lons), min(lats), max(lats)))
    return bboxes, polygons


# ── Tile math ──────────────────────────────────────────────────────────────────
def max_useful_zoom(gsd_m):
    if gsd_m <= GSD_ZOOM_TABLE[0][0]:  return GSD_ZOOM_TABLE[0][1]
    if gsd_m >= GSD_ZOOM_TABLE[-1][0]: return GSD_ZOOM_TABLE[-1][1]
    for i in range(len(GSD_ZOOM_TABLE) - 1):
        g0, z0 = GSD_ZOOM_TABLE[i]
        g1, z1 = GSD_ZOOM_TABLE[i + 1]
        if g0 <= gsd_m <= g1:
            t = (gsd_m - g0) / (g1 - g0)
            return math.floor(z0 + t * (z1 - z0))


def _lon_to_x(lon, z): return int((lon + 180) / 360 * (2 ** z))
def _lat_to_y(lat, z): return int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * (2 ** z))

def tiles_for_bbox(x1, x2, y1, y2, z):
    tx0 = _lon_to_x(x1, z);  tx1 = _lon_to_x(x2, z)
    ty0 = _lat_to_y(y2, z);  ty1 = _lat_to_y(y1, z)  # y2=maxlat (smaller tile y)
    return max(tx1 - tx0 + 1, 1) * max(ty1 - ty0 + 1, 1)


DEFAULT_JPEG_KB   = 12.5    # measured JPEG tile size at native zoom (BCOMB July 2026)
DEFAULT_RATE      = 212     # measured tiles/min/thread at native zoom (BCOMB JPEG, July 2026)

def tile_kb(z, native_z, fmt="jpeg", native_kb=None):
    """Return estimated tile size in KB using measured decay curve."""
    if native_kb is None:
        native_kb = DEFAULT_JPEG_KB
    d = z - native_z
    # Scale measured table relative to native_kb override
    scale = native_kb / DEFAULT_JPEG_KB
    table = JPEG_KB_MEASURED if fmt == "jpeg" else PNG_KB_MEASURED
    # Find nearest two deltas and interpolate
    deltas = sorted(table.keys())
    if d <= deltas[0]:
        kb = table[deltas[0]]
    elif d >= deltas[-1]:
        kb = table[deltas[-1]]
    else:
        lo = max(k for k in deltas if k <= d)
        hi = min(k for k in deltas if k >= d)
        if lo == hi:
            kb = table[lo]
        else:
            t  = (d - lo) / (hi - lo)
            kb = table[lo] + t * (table[hi] - table[lo])
    return max(round(kb * scale, 1), 1.6)


def seed_rate(z, native_z, native_rate=None):
    if native_rate is None:
        native_rate = DEFAULT_RATE
    return native_rate * THREADS


def compute_gsd_row(gsd_m, bboxes, native_kb=None, native_rate=None, monthly_requests=None, vm_instances=1):
    native_z  = max_useful_zoom(gsd_m)
    zoom_rows = []
    jpg_tot   = dict(tiles=0, gb=0.0, vm_hrs=0.0, wall_hrs=0.0, write_tx=0.0)
    png_tot   = dict(tiles=0, gb=0.0, vm_hrs=0.0, wall_hrs=0.0, write_tx=0.0)
    for z in range(MIN_ZOOM, native_z + 1):
        cnt       = sum(tiles_for_bbox(*b, z) for b in bboxes)
        kb_jpg    = tile_kb(z, native_z, "jpeg", native_kb)
        kb_png    = tile_kb(z, native_z, "png",  native_kb)
        gb_jpg    = cnt * kb_jpg / (1024 * 1024)
        gb_png    = cnt * kb_png / (1024 * 1024)
        vm_hrs    = (cnt / seed_rate(z, native_z, native_rate)) / 60
        wall_hrs  = vm_hrs / vm_instances
        write_tx  = cnt * STOR_WRITE_RATE
        lb_cost   = (wall_hrs * LB_RATE) if vm_instances > 1 else 0.0
        comp_cost = round(vm_hrs * VM_RATE + write_tx + lb_cost, 4)
        zoom_rows.append(dict(z=z, tiles=cnt, vm_hrs=vm_hrs, wall_hrs=wall_hrs,
                              kb_jpg=kb_jpg,   gb_jpg=gb_jpg,
                              kb_png=kb_png,   gb_png=gb_png,
                              stor_jpg=round(gb_jpg * STOR_RATE, 4),
                              stor_png=round(gb_png * STOR_RATE, 4),
                              write_tx=round(write_tx, 4),
                              comp=comp_cost))
        jpg_tot["tiles"]    += cnt;      png_tot["tiles"]    += cnt
        jpg_tot["gb"]       += gb_jpg;   png_tot["gb"]       += gb_png
        jpg_tot["vm_hrs"]   += vm_hrs;   png_tot["vm_hrs"]   += vm_hrs
        jpg_tot["wall_hrs"] += wall_hrs; png_tot["wall_hrs"] += wall_hrs
        jpg_tot["write_tx"] += write_tx; png_tot["write_tx"] += write_tx
    lb_total = (jpg_tot["wall_hrs"] * LB_RATE) if vm_instances > 1 else 0.0
    for t in (jpg_tot, png_tot):
        t["stor"] = round(t["gb"] * STOR_RATE, 2)
        t["comp"] = round(t["vm_hrs"] * VM_RATE + t["write_tx"] + lb_total, 2)
    # Egress: monthly requests × native-zoom tile size (conservative — largest tile, most detail)
    # Each client request fetches exactly one tile at one zoom level.
    native_kb_jpg = tile_kb(native_z, native_z, "jpeg", native_kb)
    native_kb_png = tile_kb(native_z, native_z, "png",  native_kb)
    egr_jpg_gb = (monthly_requests * native_kb_jpg / (1024 * 1024)) if monthly_requests else 0.0
    egr_png_gb = (monthly_requests * native_kb_png / (1024 * 1024)) if monthly_requests else 0.0
    jpg_tot["egress_gb"] = egr_jpg_gb
    jpg_tot["egress"]    = round(egr_jpg_gb * EGRESS_RATE, 2)
    png_tot["egress_gb"] = egr_png_gb
    png_tot["egress"]    = round(egr_png_gb * EGRESS_RATE, 2)
    return native_z, zoom_rows, jpg_tot, png_tot

# ── Inset map ─────────────────────────────────────────────────────────────────
def build_aoi_map(raw_bytes, filename, map_w=900, map_h=420):
    """Render the uploaded shapefile/KML directly in Leaflet via Playwright."""
    import base64
    from playwright.sync_api import sync_playwright

    ext = filename.rsplit(".", 1)[-1].lower()
    b64 = base64.b64encode(raw_bytes).decode()

    if ext in ("kml", "kmz"):
        # Use Leaflet omnivore to load KML/KMZ directly
        loader_js = f"""
var b64 = '{b64}';
var bin = atob(b64);
var bytes = new Uint8Array(bin.length);
for (var i=0;i<bin.length;i++) bytes[i]=bin.charCodeAt(i);
var blob = new Blob([bytes], {{type:'application/vnd.google-earth.kml+xml'}});
var url  = URL.createObjectURL(blob);
var layer = omnivore.kml(url).addTo(map);
layer.on('ready', function() {{
    layer.setStyle({{color:'#0ea5e9', weight:2, fillColor:'#1e3a5f', fillOpacity:0.35}});
    map.fitBounds(layer.getBounds().pad(0.12));
}});
"""
        extra_scripts = '<script src="https://unpkg.com/leaflet-omnivore@0.3.4/leaflet-omnivore.min.js"></script>'
    else:
        # Shapefile zip — use shpjs to parse, then L.geoJSON
        loader_js = f"""
var b64 = '{b64}';
var bin = atob(b64);
var bytes = new Uint8Array(bin.length);
for (var i=0;i<bin.length;i++) bytes[i]=bin.charCodeAt(i);
shp(bytes.buffer).then(function(geojson) {{
    var layer = L.geoJSON(geojson, {{
        style: {{color:'#0ea5e9', weight:2, fillColor:'#1e3a5f', fillOpacity:0.35}}
    }}).addTo(map);
    map.fitBounds(layer.getBounds().pad(0.12));
    window._mapReady = true;
}});
"""
        extra_scripts = '<script src="https://unpkg.com/shpjs@latest/dist/shp.js"></script>'

    html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
{extra_scripts}
<style>html,body,#map{{margin:0;padding:0;width:{map_w}px;height:{map_h}px;}}</style>
</head><body>
<div id="map"></div>
<script>
var map = L.map('map', {{zoomControl:false, attributionControl:false}});
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{maxZoom:20}}).addTo(map);
window._mapReady = false;
{loader_js}
</script>
</body></html>"""

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": map_w, "height": map_h}, device_scale_factor=2)
        page.set_content(html, wait_until="networkidle")
        # Wait for shpjs/omnivore to parse and render
        page.wait_for_timeout(3000)
        png_bytes = page.screenshot(full_page=False)
        browser.close()

    buf = io.BytesIO(png_bytes)
    buf.seek(0)
    return buf


# ── PDF builder ────────────────────────────────────────────────────────────────
def pdf_styles():
    ss = getSampleStyleSheet()
    def P(name, **kw):
        return ParagraphStyle(name, parent=ss["Normal"], **kw)
    return dict(
        title   = P("t",   fontSize=18, textColor=WHITE,      leading=24, fontName="Helvetica-Bold"),
        sub     = P("s",   fontSize=8,  textColor=LIGHT_BLUE, leading=12),
        h2      = P("h2",  fontSize=12, textColor=DARK_BLUE,  leading=16, fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=4),
        h3      = P("h3",  fontSize=8,  textColor=MID_BLUE,   leading=12, fontName="Helvetica-Bold", spaceBefore=6,  spaceAfter=2),
        body    = P("b",   fontSize=8,  textColor=TEXT_DARK,  leading=12),
        note    = P("n",   fontSize=7,  textColor=TEXT_MID,   leading=10, leftIndent=10),
        stat    = P("st",  fontSize=10, textColor=DARK_BLUE,  leading=14, fontName="Helvetica-Bold", alignment=1),
        statlbl = P("sl",  fontSize=6,  textColor=TEXT_MID,   leading=9,  alignment=1),
    )


def build_pdf(project_name, filename, raw_bytes, bboxes, polygons, gsd_results, native_kb=None, native_rate=None, monthly_requests=None):
    st     = pdf_styles()
    buf    = io.BytesIO()
    page_w = letter[0] - 1.0 * inch

    # AOI extents
    min_lon = min(b[0] for b in bboxes); max_lon = max(b[1] for b in bboxes)
    min_lat = min(b[2] for b in bboxes); max_lat = max(b[3] for b in bboxes)
    mid_lat = (min_lat + max_lat) / 2
    width_km  = round((max_lon - min_lon) * math.cos(math.radians(mid_lat)) * 111.32, 1)
    height_km = round((max_lat - min_lat) * 111.32, 1)

    doc   = SimpleDocTemplate(buf, pagesize=letter,
                              leftMargin=0.5*inch, rightMargin=0.5*inch,
                              topMargin=0.5*inch,  bottomMargin=0.5*inch)
    story = []

    # ── Inset map (non-blocking — skip if OSM fetch times out) ────────────────
    map_img = None
    map_err = None
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(build_aoi_map, raw_bytes, filename, 900, 420)
            map_buf = future.result(timeout=25)
        map_img = RLImage(map_buf, width=page_w, height=page_w * 420/900)
    except Exception as e:
        map_err = str(e)

    # ── Banner ────────────────────────────────────────────────────────────────
    jpg_stor_min = min(t["stor"]   for _,_,_,t,_,_ in gsd_results)
    jpg_stor_max = max(t["stor"]   for _,_,_,t,_,_ in gsd_results)
    jpg_comp_min = min(t["comp"]   for _,_,_,t,_,_ in gsd_results)
    jpg_comp_max = max(t["comp"]   for _,_,_,t,_,_ in gsd_results)
    jpg_egr_min  = min(t["egress"] for _,_,_,t,_,_ in gsd_results)
    jpg_egr_max  = max(t["egress"] for _,_,_,t,_,_ in gsd_results)
    png_stor_min = min(t["stor"]   for _,_,_,_,t,_ in gsd_results)
    png_stor_max = max(t["stor"]   for _,_,_,_,t,_ in gsd_results)
    png_comp_min = min(t["comp"]   for _,_,_,_,t,_ in gsd_results)
    png_comp_max = max(t["comp"]   for _,_,_,_,t,_ in gsd_results)
    png_egr_min  = min(t["egress"] for _,_,_,_,t,_ in gsd_results)
    png_egr_max  = max(t["egress"] for _,_,_,_,t,_ in gsd_results)
    has_egress   = monthly_requests is not None

    def stat_cell(val, lbl):
        return [Paragraph(val, st["stat"]), Paragraph(lbl, st["statlbl"])]

    title_row = Table([[
        Paragraph("GeoServer AOI Tile Cache Cost Report", st["title"]),
        Paragraph(f"Project: <b>{project_name}</b><br/>"
                  f"Source file: {filename}  |  AOI polygons: {len(bboxes)}  |  "
                  f"Generated: {date.today().strftime('%B %d, %Y')}", st["sub"]),
    ]], colWidths=[page_w * 0.55, page_w * 0.45])
    title_row.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), DARK_BLUE),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING",   (0,0), (-1,-1), 14),
        ("TOPPADDING",    (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
    ]))

    if has_egress:
        jpg_mo_min = jpg_stor_min + jpg_egr_min
        jpg_mo_max = jpg_stor_max + jpg_egr_max
        png_mo_min = png_stor_min + png_egr_min
        png_mo_max = png_stor_max + png_egr_max
        stat_cells = [
            stat_cell(f"${jpg_mo_min:.2f} - ${jpg_mo_max:.2f}/mo", "JPEG Monthly (storage+egress)"),
            stat_cell(f"${jpg_comp_min:.2f} - ${jpg_comp_max:.2f}", "JPEG Cache Build"),
            stat_cell(f"${png_mo_min:.2f} - ${png_mo_max:.2f}/mo", "PNG Monthly (storage+egress)"),
            stat_cell(f"${png_comp_min:.2f} - ${png_comp_max:.2f}", "PNG Cache Build"),
        ]
    else:
        stat_cells = [
            stat_cell(f"${jpg_stor_min:.2f} - ${jpg_stor_max:.2f}/mo", "JPEG Storage Range"),
            stat_cell(f"${jpg_comp_min:.2f} - ${jpg_comp_max:.2f}",    "JPEG Cache Build Range"),
            stat_cell(f"${png_stor_min:.2f} - ${png_stor_max:.2f}/mo", "PNG Storage Range"),
            stat_cell(f"${png_comp_min:.2f} - ${png_comp_max:.2f}",    "PNG Cache Build Range"),
        ]
    stats_row = Table([stat_cells], colWidths=[page_w * 0.25] * 4)
    stats_row.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#162d4a")),
        ("TEXTCOLOR",     (0,0), (-1,-1), WHITE),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LINEBEFORE",    (1,0), (-1,-1), 0.5, colors.HexColor("#2a4a6b")),
    ]))

    story += [title_row, stats_row, Spacer(1, 8)]

    # ── AOI info bar ──────────────────────────────────────────────────────────
    aoi_data = [[
        Paragraph(f"<b>AOI Polygons</b><br/>{len(bboxes)}", st["body"]),
        Paragraph(f"<b>Extent</b><br/>{width_km} km x {height_km} km", st["body"]),
        Paragraph(f"<b>Lon Range</b><br/>{min_lon:.4f} to {max_lon:.4f}", st["body"]),
        Paragraph(f"<b>Lat Range</b><br/>{min_lat:.4f} to {max_lat:.4f}", st["body"]),
        Paragraph(f"<b>Zoom Range</b><br/>z{MIN_ZOOM} – z{max(r[1] for r in gsd_results)}", st["body"]),
        Paragraph(f"<b>Tile Size</b><br/>256 x 256 px", st["body"]),
    ]]
    aoi_t = Table(aoi_data, colWidths=[page_w / 6] * 6)
    aoi_t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), GRAY_BG),
        ("BOX",           (0,0), (-1,-1), 0.5, GRAY_BORDER),
        ("INNERGRID",     (0,0), (-1,-1), 0.5, GRAY_BORDER),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("FONTSIZE",      (0,0), (-1,-1), 8),
    ]))
    story += [aoi_t, Spacer(1, 8)]

    if map_img:
        story += [map_img, Spacer(1, 8)]
    elif map_err:
        story += [Paragraph(f"[Map error: {map_err[:200]}]", st["note"]), Spacer(1, 4)]

    # ── Summary table ─────────────────────────────────────────────────────────
    story.append(Paragraph("Tile Cache Cost by GSD — Summary", st["h2"]))
    story.append(Paragraph(
        "Each row is an independent scenario from z10 to the maximum useful zoom for that GSD. "
        "Cache build cost is one-time; storage cost recurs monthly.", st["body"]))
    story.append(Spacer(1, 4))

    hdr0 = ["", "", "", "", "JPEG", "JPEG", "JPEG", "JPEG", "PNG", "PNG", "PNG", "PNG"]
    hdr1 = ["GSD", "Min Z", "Max Z", "Total Tiles",
            "Cache GB", "$/mo", f"Build Hrs\n({MAX_VMS} VMs)", "Build Cost",
            "Cache GB", "$/mo", f"Build Hrs\n({MAX_VMS} VMs)", "Build Cost"]
    rows = [hdr0, hdr1]
    for gsd_m, native_z, _zr, jt, pt, vm_count in gsd_results:
        rows.append([
            GSD_LABELS[gsd_m],
            f"z{MIN_ZOOM}", f"z{native_z}",
            f"{jt['tiles']:,}",
            f"{jt['gb']:.0f}", f"${jt['stor']:.2f}", f"{jt['wall_hrs']:.0f}", f"${jt['comp']:.2f}",
            f"{pt['gb']:.0f}", f"${pt['stor']:.2f}", f"{pt['wall_hrs']:.0f}", f"${pt['comp']:.2f}",
        ])
    cw = [page_w * f for f in [0.07,0.06,0.06,0.10, 0.07,0.07,0.07,0.08, 0.07,0.07,0.07,0.08]]
    sum_t = Table(rows, colWidths=cw, repeatRows=2)
    n = len(rows)
    sum_t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(3,0),  DARK_BLUE), ("SPAN",(0,0),(3,0)),
        ("BACKGROUND",    (4,0),(7,0),  MID_BLUE),  ("SPAN",(4,0),(7,0)),
        ("BACKGROUND",    (8,0),(11,0), ORANGE),    ("SPAN",(8,0),(11,0)),
        ("BACKGROUND",    (0,1),(3,1),  DARK_BLUE),
        ("BACKGROUND",    (4,1),(7,1),  MID_BLUE),
        ("BACKGROUND",    (8,1),(11,1), ORANGE),
        ("TEXTCOLOR",     (0,0),(-1,1), WHITE),
        ("FONTNAME",      (0,0),(-1,1), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,-1),7),
        ("ALIGN",         (0,0),(-1,-1),"CENTER"),
        ("VALIGN",        (0,0),(-1,-1),"MIDDLE"),
        ("ROWBACKGROUNDS",(0,2),(-1,-1),[WHITE, GRAY_BG]),
        ("BACKGROUND",    (8,2),(11,n), PNG_BG),
        ("GRID",          (0,0),(-1,-1),0.4, GRAY_BORDER),
        ("TOPPADDING",    (0,0),(-1,-1),4),
        ("BOTTOMPADDING", (0,0),(-1,-1),4),
        ("LINEAFTER",     (7,0),(7,-1), 1.2, GRAY_BORDER),
        ("FONTNAME",      (7,2),(7,-1), "Helvetica-Bold"),
        ("FONTNAME",      (11,2),(11,-1),"Helvetica-Bold"),
    ]))
    story += [sum_t, Spacer(1, 14)]

    # ── Per-GSD zoom detail ───────────────────────────────────────────────────
    story.append(Paragraph("Per-Zoom Tile Cache Cost Breakdown by GSD", st["h2"]))
    story.append(Paragraph(
        "The highest zoom level typically accounts for over 90% of total cost. "
        "Cache build compute cost is the same for JPEG and PNG.", st["body"]))
    story.append(Spacer(1, 6))

    for gsd_m, native_z, zoom_rows, jt, pt, vm_count in gsd_results:
        label = (f"{GSD_LABELS[gsd_m]} GSD  |  z{MIN_ZOOM}-z{native_z}  |  "
                 f"{jt['tiles']:,} tiles  |  {vm_count} VMs  |  {jt['wall_hrs']:.1f} hrs build  |  "
                 f"JPEG: {jt['gb']:.0f} GB / ${jt['stor']:.2f}/mo / ${jt['comp']:.2f}  |  "
                 f"PNG: {pt['gb']:.0f} GB / ${pt['stor']:.2f}/mo / ${pt['comp']:.2f}")
        zh0 = ["","","JPEG","JPEG","JPEG","JPEG","JPEG","PNG","PNG","PNG","PNG"]
        zh1 = ["Zoom","Tiles","KB/tile","Cache GB","$/mo","Build Hrs","Build $",
                              "KB/tile","Cache GB","$/mo","Build $"]
        zrows = [zh0, zh1]
        for r in zoom_rows:
            zrows.append([f"z{r['z']}", f"{r['tiles']:,}",
                          f"{r['kb_jpg']:.1f}", f"{r['gb_jpg']:.1f}", f"${r['stor_jpg']:.2f}",
                          f"{r['wall_hrs']:.1f}", f"${r['comp']:.2f}",
                          f"{r['kb_png']:.1f}", f"{r['gb_png']:.1f}", f"${r['stor_png']:.2f}",
                          f"${r['comp']:.2f}"])
        nr = len(zrows)
        zrows.append(["TOTAL", f"{jt['tiles']:,}",
                      "", f"{jt['gb']:.1f}", f"${jt['stor']:.2f}", f"{jt['wall_hrs']:.0f}", f"${jt['comp']:.2f}",
                      "", f"{pt['gb']:.1f}", f"${pt['stor']:.2f}", f"${pt['comp']:.2f}"])
        zcw = [page_w*f for f in [0.07,0.11,0.07,0.08,0.08,0.08,0.08,0.07,0.08,0.08,0.08]]
        zt = Table(zrows, colWidths=zcw, repeatRows=2)
        zt.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(1,0),  DARK_BLUE), ("SPAN",(0,0),(1,0)),
            ("BACKGROUND",    (2,0),(6,0),  MID_BLUE),  ("SPAN",(2,0),(6,0)),
            ("BACKGROUND",    (7,0),(10,0), ORANGE),    ("SPAN",(7,0),(10,0)),
            ("BACKGROUND",    (0,1),(1,1),  DARK_BLUE),
            ("BACKGROUND",    (2,1),(6,1),  MID_BLUE),
            ("BACKGROUND",    (7,1),(10,1), ORANGE),
            ("TEXTCOLOR",     (0,0),(-1,1), WHITE),
            ("FONTNAME",      (0,0),(-1,1), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0),(-1,-1),7),
            ("ALIGN",         (0,0),(-1,-1),"CENTER"),
            ("VALIGN",        (0,0),(-1,-1),"MIDDLE"),
            ("ROWBACKGROUNDS",(0,2),(-1,nr-1),[WHITE,GRAY_BG]),
            ("BACKGROUND",    (7,2),(10,nr-1),PNG_BG),
            ("GRID",          (0,0),(-1,-1),0.4,GRAY_BORDER),
            ("TOPPADDING",    (0,0),(-1,-1),3),
            ("BOTTOMPADDING", (0,0),(-1,-1),3),
            ("LINEAFTER",     (6,0),(6,-1), 1.2,GRAY_BORDER),
            ("BACKGROUND",    (0,nr),(-1,nr),LIGHT_BLUE),
            ("FONTNAME",      (0,nr),(-1,nr),"Helvetica-Bold"),
            ("LINEABOVE",     (0,nr),(-1,nr),1.0,MID_BLUE),
        ]))
        story.append(Paragraph(label, st["h3"]))
        story.append(zt)
        story.append(Spacer(1, 6))

    # ── Monthly Recurring Costs ───────────────────────────────────────────────
    story.append(HRFlowable(width=page_w, color=GRAY_BORDER, spaceAfter=6))
    story.append(Paragraph("Monthly Recurring Costs", st["h2"]))
    if has_egress:
        story.append(Paragraph(
            f"Based on {monthly_requests:,.0f} tile requests/month. "
            "Egress computed at native zoom tile size (conservative — largest tile, highest detail). "
            "Storage is a fixed monthly cost; egress scales with traffic.", st["body"]))
    else:
        story.append(Paragraph(
            "Egress not included — enter monthly tile request volume in the form to estimate.", st["body"]))
    story.append(Spacer(1, 4))

    mo_hdr = ["GSD", "JPEG Cache GB", "JPEG Storage/mo",
              "JPEG Egress/mo" if has_egress else "JPEG Egress",
              "JPEG Total/mo",
              "PNG Cache GB", "PNG Storage/mo",
              "PNG Egress/mo" if has_egress else "PNG Egress",
              "PNG Total/mo"]
    mo_rows = [mo_hdr]
    for gsd_m, native_z, _, jt, pt, _ in gsd_results:
        mo_rows.append([
            GSD_LABELS[gsd_m],
            f"{jt['gb']:.0f} GB",
            f"${jt['stor']:.2f}",
            f"${jt['egress']:.2f}" if has_egress else "—",
            f"${jt['stor'] + jt['egress']:.2f}",
            f"{pt['gb']:.0f} GB",
            f"${pt['stor']:.2f}",
            f"${pt['egress']:.2f}" if has_egress else "—",
            f"${pt['stor'] + pt['egress']:.2f}",
        ])
    mo_cw = [page_w * f for f in [0.09, 0.10, 0.11, 0.11, 0.10, 0.10, 0.11, 0.11, 0.10]]
    mo_t = Table(mo_rows, colWidths=mo_cw, repeatRows=1)
    nm = len(mo_rows)
    mo_t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  DARK_BLUE),
        ("TEXTCOLOR",     (0,0),(-1,0),  WHITE),
        ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,-1), 7),
        ("ALIGN",         (0,0),(-1,-1), "CENTER"),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [WHITE, GRAY_BG]),
        ("BACKGROUND",    (5,1),(8,nm),  PNG_BG),
        ("GRID",          (0,0),(-1,-1), 0.4, GRAY_BORDER),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ("LINEAFTER",     (4,0),(4,-1),  1.2, GRAY_BORDER),
        ("FONTNAME",      (4,1),(4,-1),  "Helvetica-Bold"),
        ("FONTNAME",      (8,1),(8,-1),  "Helvetica-Bold"),
    ]))
    story += [mo_t, Spacer(1, 10)]

    # ── Assumptions ───────────────────────────────────────────────────────────
    story.append(HRFlowable(width=page_w, color=GRAY_BORDER, spaceAfter=6))
    story.append(Paragraph("Model Assumptions & Parameters", st["h2"]))
    egress_note = (f"{monthly_requests:,.0f} req/mo × native-zoom tile KB ÷ 1024² × $0.087/GB"
                   if monthly_requests else "Not included — provide monthly request volume to estimate")
    a_rows = [
        ["Parameter", "Value", "Notes"],
        ["── Storage", "", ""],
        ["Storage rate",      "$0.018/GB/month",   "Azure Hot LRS, southcentralus — recurring monthly"],
        ["── Compute", "", ""],
        ["VM type",           "Standard_F4s_v2",    "4 vCPU / 8 GB RAM — dedicated seeding VMs (pi-geoserver03/04)"],
        ["VM rate",           f"${VM_RATE:.3f}/hr", "PAYG southcentralus — one-time cache build cost"],
        ["Seeding fleet size",  f"{MAX_VMS} VMs",       "Fixed fleet — all VMs run in parallel; build time = VM-hours / 15"],
        ["Cache build threads","4",                 "GWC seed threads per VM, matches vCPU count on F4s_v2"],
        ["Write transactions", f"${STOR_WRITE_RATE*10000:.3f}/10K ops", "Azure Blob write transactions per tile seeded"],
        ["Load balancer",     f"${LB_RATE}/hr (when >1 VM)", "Azure Load Balancer during seeding (scale set only)"],
        ["Build rate",
         f"{native_rate:.0f} tiles/min/thread" if native_rate else f"{DEFAULT_RATE} tiles/min/thread",
         "OVERRIDE" if native_rate else "MEASURED — JPEG seed, July 2026"],
        ["── Egress", "", ""],
        ["Egress rate",       "$0.087/GB",          "Azure internet egress, first 10TB/month"],
        ["Monthly requests",
         f"{monthly_requests:,.0f} tiles/month" if monthly_requests else "Not provided",
         egress_note],
        ["Egress basis",      "Native zoom only",   "Each request fetches one tile; native zoom is conservative (largest tile size)"],
        ["── Tile Sizes (Measured)", "", ""],
        ["JPEG native zoom",
         f"{native_kb:.1f} KB" if native_kb else f"{DEFAULT_JPEG_KB} KB",
         "OVERRIDE" if native_kb else "MEASURED — 10cm, July 2026"],
        ["PNG native zoom",   f"{PNG_KB_MEASURED[0]:.0f} KB",  "MEASURED — 10cm, July 2026"],
        ["Tile size",         "256 x 256 px",       "GWC / 1-PI-WMQ grid set"],
        ["AOI method",        "Per-polygon bbox",   "Individual polygon bboxes summed"],
    ]
    acw = [page_w*0.22, page_w*0.23, page_w*0.55]
    at = Table(a_rows, colWidths=acw, repeatRows=1)
    at.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  DARK_BLUE),
        ("TEXTCOLOR",     (0,0),(-1,0),  WHITE),
        ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
        ("FONTNAME",      (0,1),(0,-1),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,-1), 7),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [WHITE, GRAY_BG]),
        ("GRID",          (0,0),(-1,-1), 0.4, GRAY_BORDER),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
    ]))
    story += [at, Spacer(1,6)]
    story.append(Paragraph(
        "Tile sizes are measured from a calibration seed. Build rate is measured at native zoom "
        "and applied uniformly across all zoom levels (conservative — lower zooms typically seed faster).",
        st["note"]))


    doc.build(story)
    buf.seek(0)
    return buf

# ── HTML form ──────────────────────────────────────────────────────────────────
FORM_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tile Cache Cost Estimator</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         background: #f1f5f9; min-height: 100vh; display: flex; flex-direction: column;
         align-items: center; justify-content: center; padding: 32px 16px; }
  .card { background: white; border-radius: 12px; box-shadow: 0 4px 24px rgba(0,0,0,0.10);
          width: 480px; overflow: hidden; }
  .info-card { background: white; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.07);
               width: 480px; margin-top: 18px; overflow: hidden; }
  .info-card details { padding: 0; }
  .info-card summary {
    padding: 14px 20px; font-size: 13px; font-weight: 600; color: #1e3a5f;
    cursor: pointer; user-select: none; list-style: none; display: flex;
    align-items: center; justify-content: space-between; }
  .info-card summary::-webkit-details-marker { display: none; }
  .info-card summary::after { content: "▸"; color: #93c5fd; }
  .info-card details[open] summary::after { content: "▾"; }
  .info-body { padding: 0 20px 18px; }
  .info-body h3 { font-size: 12px; font-weight: 700; color: #1e3a5f;
                  margin: 14px 0 6px; text-transform: uppercase; letter-spacing: 0.05em; }
  .info-row { display: flex; gap: 10px; padding: 5px 0;
              border-bottom: 1px solid #f1f5f9; font-size: 12px; }
  .info-row dt { color: #6b7280; font-weight: 600; min-width: 160px; flex-shrink: 0; }
  .info-row dd { color: #111827; }
  .header { background: #1e3a5f; padding: 28px 32px; }
  .header h1 { color: white; font-size: 20px; font-weight: 700; }
  .header p  { color: #93c5fd; font-size: 13px; margin-top: 4px; }
  .body { padding: 28px 32px; }
  .field { margin-bottom: 20px; }
  label { display: block; font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 6px; }
  input[type=text], select {
    width: 100%; padding: 10px 12px; border: 1.5px solid #d1d5db;
    border-radius: 8px; font-size: 14px; color: #111827;
    transition: border-color 0.2s; outline: none; }
  input[type=text]:focus, select:focus { border-color: #2563eb; }
  .drop-zone {
    border: 2px dashed #93c5fd; border-radius: 8px; padding: 28px;
    text-align: center; cursor: pointer; background: #f8fafc;
    transition: border-color 0.2s, background 0.2s; }
  .drop-zone:hover, .drop-zone.drag { border-color: #2563eb; background: #eff6ff; }
  .drop-zone p { color: #6b7280; font-size: 13px; }
  .drop-zone strong { color: #2563eb; }
  #file-name { margin-top: 8px; font-size: 12px; color: #16a34a; font-weight: 600; }
  .row { display: flex; gap: 16px; }
  .row .field { flex: 1; }
  button {
    width: 100%; padding: 12px; background: #2563eb; color: white;
    border: none; border-radius: 8px; font-size: 15px; font-weight: 600;
    cursor: pointer; transition: background 0.2s; }
  button:hover { background: #1d4ed8; }
  button:disabled { background: #93c5fd; cursor: not-allowed; }
  .spinner { display: none; text-align: center; margin-top: 14px; color: #6b7280; font-size: 13px; }
  .error { background: #fef2f2; border: 1px solid #fca5a5; color: #b91c1c;
           padding: 10px 14px; border-radius: 8px; font-size: 13px; margin-top: 14px; }
  {% if error %}.error-shown { display: block; }{% endif %}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <h1>Tile Cache Cost Estimator</h1>
    <p>Upload a KML, KMZ, or zipped Shapefile to generate a cost report</p>
  </div>
  <div class="body">
    {% if error %}
    <div class="error">{{ error }}</div>
    {% endif %}
    <form method="POST" action="/generate" enctype="multipart/form-data" id="form">
      <div class="field">
        <label>Project Name</label>
        <input type="text" name="project_name" placeholder="e.g. Conoco COPE-S26" required>
      </div>
      <div class="field">
        <label>AOI File</label>
        <div class="drop-zone" id="drop-zone" onclick="document.getElementById('file').click()">
          <p><strong>Click to browse</strong> or drag and drop</p>
          <p>.kml &nbsp; .kmz &nbsp; .zip (shapefile)</p>
          <div id="file-name"></div>
        </div>
        <input type="file" id="file" name="aoi_file" accept=".kml,.kmz,.zip"
               style="display:none" required>
      </div>
      <div class="row">
        <div class="field">
          <label>Imagery GSD</label>
          <select name="gsd">
            <option value="all">All resolutions</option>
            <option value="0.025">2.5 cm</option>
            <option value="0.050">5 cm</option>
            <option value="0.075">7.5 cm</option>
            <option value="0.100" selected>10 cm</option>
            <option value="0.150">15 cm</option>
          </select>
        </div>
        <div class="field">
          <label>Monthly Tile Requests (egress)</label>
          <input type="text" name="monthly_requests" placeholder="e.g. 500000 — blank = no egress">
        </div>
      </div>
      <details style="margin-bottom:20px">
        <summary style="font-size:13px;font-weight:600;color:#374151;cursor:pointer;user-select:none">
          Calibration Overrides <span style="font-weight:400;color:#6b7280">(optional — leave blank to use model defaults)</span>
        </summary>
        <div style="margin-top:12px;padding:14px;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0">
          <div class="row">
            <div class="field">
              <label>JPEG tile size at native zoom (KB)</label>
              <input type="text" name="native_kb" placeholder="Default: 12.5 KB (measured)">
            </div>
            <div class="field">
              <label>Seed rate at native zoom (tiles/min/thread)</label>
              <input type="text" name="native_rate" placeholder="Default: 212 (measured)">
            </div>
          </div>
          <p style="font-size:11px;color:#6b7280;margin-top:4px">
            Tile sizes are measured from 10cm imagery (July 2026). Seed rate is estimated.
            Monthly requests drives egress cost at $0.087/GB (Azure internet egress).
          </p>
        </div>
      </details>
      <button type="submit" id="submit-btn">Generate Report</button>
      <div class="spinner" id="spinner">Generating report, please wait...</div>
    </form>
  </div>
</div>
<div class="info-card">
  <details>
    <summary>About This Cost Model</summary>
    <div class="info-body">

      <h3>Calibration Tests</h3>
      <dl>
        <div class="info-row"><dt>Test imagery</dt><dd>10 cm GSD, native zoom z20, ~27.75 °N latitude</dd></div>
        <div class="info-row"><dt>Test type</dt><dd>Full-extent JPEG and PNG GeoWebCache seed jobs, July 2026</dd></div>
        <div class="info-row"><dt>Tile sizes</dt><dd>Sampled from Azure Blob Storage byte counts after seed completion — z10 through z20</dd></div>
        <div class="info-row"><dt>Seed rate</dt><dd>212 tiles/min/thread — derived from job duration vs. tile count at native zoom</dd></div>
        <div class="info-row"><dt>Zoom interpolation</dt><dd>Sizes at other zoom levels are linearly interpolated from the measured decay curve</dd></div>
      </dl>

      <h3>Storage Location</h3>
      <dl>
        <div class="info-row"><dt>Azure account</dt><dd>pigeoserverprod</dd></div>
        <div class="info-row"><dt>Container</dt><dd>tilecache</dd></div>
        <div class="info-row"><dt>GeoServer environment</dt><dd>devimageservices.priusintelli.com (southcentralus)</dd></div>
        <div class="info-row"><dt>GeoWebCache endpoint</dt><dd>devimageservices.priusintelli.com/rest/</dd></div>
        <div class="info-row"><dt>Grid set</dt><dd>1-PI-WMQ (custom Web Mercator, 256 × 256 px)</dd></div>
      </dl>

      <h3>Azure Pricing</h3>
      <dl>
        <div class="info-row"><dt>Storage</dt><dd>$0.018 / GB / month — Hot LRS, southcentralus</dd></div>
        <div class="info-row"><dt>Compute</dt><dd>$0.169 / hr — Standard_F4s_v2 PAYG, southcentralus (dedicated seeding VMs)</dd></div>
        <div class="info-row"><dt>Load balancer</dt><dd>$0.025 / hr — added when VM count &gt; 1</dd></div>
        <div class="info-row"><dt>Egress</dt><dd>$0.087 / GB — Azure internet outbound, first 10 TB/month</dd></div>
      </dl>

      <h3>VM Count Calculation</h3>
      <dl>
        <div class="info-row"><dt>VM type</dt><dd>Standard_F4s_v2 — 4 vCPU / 8 GB RAM (dedicated seeding VMs; client-serving uses a separate VMSS)</dd></div>
        <div class="info-row"><dt>Seed threads</dt><dd>4 threads per VM (= vCPU count); measured rate 212 tiles/min/thread</dd></div>
        <div class="info-row"><dt>Throughput</dt><dd>~848 tiles/min per VM (4 threads × 212 tiles/min/thread)</dd></div>
        <div class="info-row"><dt>Bottleneck</dt><dd>I/O-bound (blob reads for imagery + writes for tile cache) — CPU utilization 25–33% during seeding</dd></div>
        <div class="info-row"><dt>Fleet size</dt><dd>15 VMs fixed — all run in parallel; build time = total VM-hours ÷ 15</dd></div>
      </dl>

    </div>
  </details>
</div>

<script>
  const dz   = document.getElementById("drop-zone");
  const fi   = document.getElementById("file");
  const fn   = document.getElementById("file-name");
  const btn  = document.getElementById("submit-btn");
  const spin = document.getElementById("spinner");

  fi.addEventListener("change", () => {
    fn.textContent = fi.files[0] ? fi.files[0].name : "";
  });
  dz.addEventListener("dragover",  e => { e.preventDefault(); dz.classList.add("drag"); });
  dz.addEventListener("dragleave", () => dz.classList.remove("drag"));
  dz.addEventListener("drop", e => {
    e.preventDefault(); dz.classList.remove("drag");
    fi.files = e.dataTransfer.files;
    fn.textContent = fi.files[0] ? fi.files[0].name : "";
  });
  document.getElementById("form").addEventListener("submit", () => {
    btn.disabled = true; spin.style.display = "block";
  });
</script>
</body>
</html>"""

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string(FORM_HTML, error=None)


@app.route("/generate", methods=["POST"])
def generate():
    project_name = request.form.get("project_name", "Unnamed Project").strip()
    gsd_raw      = request.form.get("gsd", "0.10")
    gsd_all      = gsd_raw == "all"
    gsd_m        = None if gsd_all else float(gsd_raw)
    file         = request.files.get("aoi_file")

    if not file or not file.filename:
        return render_template_string(FORM_HTML, error="Please upload a KML, KMZ, or zipped Shapefile.")

    try:
        data           = file.read()
        bboxes, polygons = parse_upload(file.filename, data)
    except Exception as e:
        import traceback
        return render_template_string(FORM_HTML, error=f"Could not parse file: {e}\n\n{traceback.format_exc()}")

    # Calibration overrides (blank = use defaults)
    try:
        native_kb        = float(request.form["native_kb"])        if request.form.get("native_kb")        else None
        native_rate      = float(request.form["native_rate"])      if request.form.get("native_rate")      else None
        monthly_requests = float(request.form["monthly_requests"]) if request.form.get("monthly_requests") else None
    except ValueError:
        native_kb = native_rate = monthly_requests = None

    # Compute selected GSD(s) — fixed fleet of MAX_VMS seeding VMs
    gsds = [g for g, _ in GSD_ZOOM_TABLE] if gsd_all else [gsd_m]
    gsd_results = []
    for g in gsds:
        native_z, zoom_rows, jpg_tot, png_tot = compute_gsd_row(g, bboxes, native_kb, native_rate, monthly_requests, MAX_VMS)
        gsd_results.append((g, native_z, zoom_rows, jpg_tot, png_tot, MAX_VMS))

    try:
        pdf_buf = build_pdf(project_name, file.filename, data, bboxes, polygons, gsd_results, native_kb, native_rate, monthly_requests)
    except Exception as e:
        import traceback
        return render_template_string(FORM_HTML, error=f"PDF generation failed: {e}\n\n{traceback.format_exc()}")

    safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in project_name)
    gsd_suffix = "All" if gsd_all else GSD_LABELS[gsd_m].replace(" ", "").replace(".", "p")
    filename   = f"{safe_name}_{gsd_suffix}_{date.today().isoformat()}.pdf"

    return send_file(pdf_buf, mimetype="application/pdf",
                     as_attachment=True, download_name=filename)


if __name__ == "__main__":
    print("Tile Cache Cost Estimator running at http://localhost:5000")
    app.run(debug=True, port=5000)
