"""
GeoServer AOI tile cache cost report.
Pulls coverage bounding boxes from GeoServer REST, computes tile counts,
storage and compute costs for each GSD level (JPEG and PNG), outputs a PDF.

Usage:
    python gsd_cost_table.py [--workspace WS] [--output report.pdf]
"""

import argparse, math, subprocess, json
from datetime import date
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, HRFlowable, KeepTogether)

# ── Constants ──────────────────────────────────────────────────────────────────
GEOSERVER_URL  = "https://devimageservices.priusintelli.com"
GEOSERVER_USER = "geoadmin"
GEOSERVER_PASS = "Ag3CtKS93hhnxLBX"
BASE_RES       = 156543.03392   # WebMercator m/px at zoom 0
TILE_PX        = 256
VM_RATE        = 0.169          # $/hr Standard_F4s_v2 PAYG southcentralus
STOR_RATE      = 0.018          # $/GB/month Hot LRS
THREADS        = 4
MIN_ZOOM       = 10
PNG_MULTIPLIER = 2.5            # PNG tile size relative to JPEG

# Empirically determined GSD (m) -> max useful zoom
GSD_ZOOM_TABLE = [
    (0.025, 22),
    (0.050, 21),
    (0.075, 20),
    (0.100, 20),
    (0.150, 20),
]

# ── Colours ────────────────────────────────────────────────────────────────────
DARK_BLUE   = colors.HexColor("#1e3a5f")
MID_BLUE    = colors.HexColor("#2563eb")
LIGHT_BLUE  = colors.HexColor("#dbeafe")
ACCENT      = colors.HexColor("#0ea5e9")
GREEN       = colors.HexColor("#16a34a")
ORANGE      = colors.HexColor("#ea580c")
GRAY_BG     = colors.HexColor("#f8fafc")
GRAY_BORDER = colors.HexColor("#e2e8f0")
PNG_BG      = colors.HexColor("#fef9c3")   # soft yellow for PNG columns
TEXT_DARK   = colors.HexColor("#0f172a")
TEXT_MID    = colors.HexColor("#475569")
WHITE       = colors.white

# ── GeoServer helpers ──────────────────────────────────────────────────────────
def gs_get(path):
    r = subprocess.run(
        ["curl.exe", "-s", "-u", f"{GEOSERVER_USER}:{GEOSERVER_PASS}",
         f"{GEOSERVER_URL}{path}"],
        capture_output=True, text=True, timeout=30)
    return json.loads(r.stdout)


def get_workspace_bboxes(workspace):
    stores = gs_get(f"/rest/workspaces/{workspace}/coveragestores.json")
    stores = stores["coverageStores"]["coverageStore"]
    bboxes = []
    for s in stores:
        n = s["name"]
        try:
            c  = gs_get(f"/rest/workspaces/{workspace}/coveragestores/{n}/coverages/{n}.json")
            bb = c["coverage"]["latLonBoundingBox"]
            bboxes.append((bb["minx"], bb["maxx"], bb["miny"], bb["maxy"]))
        except Exception as e:
            print(f"  Warning: {n}: {e}")
    return bboxes

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


def tiles_for_bbox(x1, x2, y1, y2, z):
    mid = (y1 + y2) / 2
    wm  = (x2 - x1) * math.cos(math.radians(mid)) * 111320
    hm  = (y2 - y1) * 111320
    tsm = TILE_PX * BASE_RES / (2 ** z)
    return max(math.ceil(wm / tsm), 1) * max(math.ceil(hm / tsm), 1)


def tile_kb(z, native_z, fmt="jpeg"):
    d  = z - native_z
    kb = 60.0 * (2 ** (d * 0.7)) if d <= 0 else 60.0 * (0.5 ** d)
    kb = max(kb, 2.0)
    return kb * PNG_MULTIPLIER if fmt == "png" else kb


def seed_rate(z, native_z):
    d = z - native_z
    if   d <= -4: base = 600
    elif d <= -2: base = 400
    elif d <=  0: base = 150
    else:         base = 80
    return base * THREADS


def compute_gsd_row(gsd_m, bboxes):
    """Returns (native_z, zoom_rows, jpeg_totals, png_totals)."""
    native_z  = max_useful_zoom(gsd_m)
    zoom_rows = []
    jpg_tot   = dict(tiles=0, gb=0.0, hrs=0.0)
    png_tot   = dict(tiles=0, gb=0.0, hrs=0.0)
    for z in range(MIN_ZOOM, native_z + 1):
        cnt      = sum(tiles_for_bbox(*b, z) for b in bboxes)
        kb_jpg   = tile_kb(z, native_z, "jpeg")
        kb_png   = tile_kb(z, native_z, "png")
        gb_jpg   = cnt * kb_jpg / (1024 * 1024)
        gb_png   = cnt * kb_png / (1024 * 1024)
        hrs      = (cnt / seed_rate(z, native_z)) / 60
        zoom_rows.append(dict(
            z=z, tiles=cnt, hrs=hrs,
            kb_jpg=kb_jpg,  gb_jpg=gb_jpg,
            kb_png=kb_png,  gb_png=gb_png,
            stor_jpg=round(gb_jpg * STOR_RATE, 4),
            stor_png=round(gb_png * STOR_RATE, 4),
            comp=round(hrs * VM_RATE, 4),
        ))
        jpg_tot["tiles"] += cnt;  jpg_tot["gb"] += gb_jpg;  jpg_tot["hrs"] += hrs
        png_tot["tiles"] += cnt;  png_tot["gb"] += gb_png;  png_tot["hrs"] += hrs
    jpg_tot["stor"] = round(jpg_tot["gb"] * STOR_RATE, 2)
    jpg_tot["comp"] = round(jpg_tot["hrs"] * VM_RATE,  2)
    png_tot["stor"] = round(png_tot["gb"] * STOR_RATE, 2)
    png_tot["comp"] = round(png_tot["hrs"] * VM_RATE,  2)
    return native_z, zoom_rows, jpg_tot, png_tot

# ── PDF helpers ────────────────────────────────────────────────────────────────
def styles():
    ss = getSampleStyleSheet()
    def P(name, **kw):
        return ParagraphStyle(name, parent=ss["Normal"], **kw)
    return dict(
        title    = P("title",    fontSize=20, textColor=WHITE,      leading=26, fontName="Helvetica-Bold"),
        subtitle = P("subtitle", fontSize=9,  textColor=LIGHT_BLUE, leading=14),
        h2       = P("h2",       fontSize=13, textColor=DARK_BLUE,  leading=18, fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=4),
        h3       = P("h3",       fontSize=9,  textColor=MID_BLUE,   leading=13, fontName="Helvetica-Bold", spaceBefore=8,  spaceAfter=2),
        body     = P("body",     fontSize=8,  textColor=TEXT_DARK,  leading=12),
        note     = P("note",     fontSize=7,  textColor=TEXT_MID,   leading=10, leftIndent=12),
        stat     = P("stat",     fontSize=11, textColor=DARK_BLUE,  leading=15, fontName="Helvetica-Bold", alignment=1),
        statlbl  = P("statlbl",  fontSize=7,  textColor=TEXT_MID,   leading=10, alignment=1),
    )


def header_banner(workspace, coverages, gsd_results, w):
    """Blue banner with title + workspace info + cost summary stats."""
    st = styles()

    # Compute overall cost ranges across all GSD scenarios
    jpg_stor_min = min(t["stor"] for _,_,t,_ in gsd_results)
    jpg_stor_max = max(t["stor"] for _,_,t,_ in gsd_results)
    jpg_comp_min = min(t["comp"] for _,_,t,_ in gsd_results)
    jpg_comp_max = max(t["comp"] for _,_,t,_ in gsd_results)
    png_stor_min = min(t["stor"] for _,_,_,t in gsd_results)
    png_stor_max = max(t["stor"] for _,_,_,t in gsd_results)
    png_comp_min = min(t["comp"] for _,_,_,t in gsd_results)
    png_comp_max = max(t["comp"] for _,_,_,t in gsd_results)

    def stat_cell(val, lbl):
        return [Paragraph(val, st["stat"]), Paragraph(lbl, st["statlbl"])]

    stats = Table([
        [
            stat_cell(f"${jpg_stor_min:.2f} - ${jpg_stor_max:.2f}/mo", "JPEG Storage Cost Range"),
            stat_cell(f"${jpg_comp_min:.2f} - ${jpg_comp_max:.2f}",    "JPEG Cache Build Cost Range"),
            stat_cell(f"${png_stor_min:.2f} - ${png_stor_max:.2f}/mo", "PNG Storage Cost Range"),
            stat_cell(f"${png_comp_min:.2f} - ${png_comp_max:.2f}",    "PNG Cache Build Cost Range"),
        ]
    ], colWidths=[w * 0.25] * 4)
    stats.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#162d4a")),
        ("TEXTCOLOR",     (0,0), (-1,-1), WHITE),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LINEBEFORE",    (1,0), (-1,-1), 0.5, colors.HexColor("#2a4a6b")),
    ]))

    title_row = Table([[
        Paragraph("GeoServer AOI Tile Cache Cost Report", st["title"]),
        Paragraph(
            f"Workspace: <b>{workspace}</b><br/>"
            f"Coverages: {coverages} strips  |  "
            f"GSD scenarios: {len(gsd_results)}  |  "
            f"Min zoom: z{MIN_ZOOM}  |  "
            f"Generated: {date.today().strftime('%B %d, %Y')}",
            st["subtitle"]),
    ]], colWidths=[w * 0.55, w * 0.45])
    title_row.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), DARK_BLUE),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING",   (0,0), (-1,-1), 16),
        ("TOPPADDING",    (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
    ]))

    return [title_row, stats]


def aoi_info_bar(bboxes, width_km, height_km, min_lon, max_lon, min_lat, max_lat, page_w):
    st = styles()
    data = [[
        Paragraph(f"<b>Coverage Strips</b><br/>{len(bboxes)}", st["body"]),
        Paragraph(f"<b>AOI Extent</b><br/>{width_km} km x {height_km} km", st["body"]),
        Paragraph(f"<b>Lon Range</b><br/>{min_lon:.4f} to {max_lon:.4f}", st["body"]),
        Paragraph(f"<b>Lat Range</b><br/>{min_lat:.4f} to {max_lat:.4f}", st["body"]),
        Paragraph(f"<b>Tile Size</b><br/>256 x 256 px", st["body"]),
        Paragraph(f"<b>Gridset</b><br/>1-PI-WMQ (EPSG:3857)", st["body"]),
    ]]
    t = Table(data, colWidths=[page_w / 6] * 6)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), GRAY_BG),
        ("BOX",           (0,0), (-1,-1), 0.5, GRAY_BORDER),
        ("INNERGRID",     (0,0), (-1,-1), 0.5, GRAY_BORDER),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ("FONTSIZE",      (0,0), (-1,-1), 8),
    ]))
    return t


def summary_table(gsd_results, page_w):
    """Comparison table: one row per GSD, JPEG and PNG columns side by side."""
    hdr0 = ["", "", "", "", "JPEG", "JPEG", "JPEG", "JPEG", "PNG", "PNG", "PNG", "PNG"]
    hdr1 = ["GSD", "Min Z", "Max Z", "Total Tiles",
            "Cache GB", "$/mo", "Build Hrs", "Build Cost",
            "Cache GB", "$/mo", "Build Hrs", "Build Cost"]
    rows = [hdr0, hdr1]

    for gsd_m, native_z, jt, pt in gsd_results:
        rows.append([
            f"{gsd_m*100:g} cm",
            f"z{MIN_ZOOM}",
            f"z{native_z}",
            f"{jt['tiles']:,}",
            f"{jt['gb']:.0f}",
            f"${jt['stor']:.2f}",
            f"{jt['hrs']:.0f}",
            f"${jt['comp']:.2f}",
            f"{pt['gb']:.0f}",
            f"${pt['stor']:.2f}",
            f"{pt['hrs']:.0f}",
            f"${pt['comp']:.2f}",
        ])

    cw = [page_w * f for f in [0.07, 0.06, 0.06, 0.10,
                                0.07, 0.07, 0.07, 0.08,
                                0.07, 0.07, 0.07, 0.08]]
    t = Table(rows, colWidths=cw, repeatRows=2)
    n = len(rows)
    t.setStyle(TableStyle([
        # Header row 0 — group labels
        ("BACKGROUND",    (0,0),  (3,0),   DARK_BLUE),
        ("BACKGROUND",    (4,0),  (7,0),   MID_BLUE),
        ("BACKGROUND",    (8,0),  (11,0),  ORANGE),
        ("TEXTCOLOR",     (0,0),  (-1,0),  WHITE),
        ("FONTNAME",      (0,0),  (-1,0),  "Helvetica-Bold"),
        ("SPAN",          (0,0),  (3,0)),
        ("SPAN",          (4,0),  (7,0)),
        ("SPAN",          (8,0),  (11,0)),
        # Header row 1
        ("BACKGROUND",    (0,1),  (3,1),   DARK_BLUE),
        ("BACKGROUND",    (4,1),  (7,1),   MID_BLUE),
        ("BACKGROUND",    (8,1),  (11,1),  ORANGE),
        ("TEXTCOLOR",     (0,1),  (-1,1),  WHITE),
        ("FONTNAME",      (0,1),  (-1,1),  "Helvetica-Bold"),
        # Data rows
        ("FONTSIZE",      (0,0),  (-1,-1), 7),
        ("ALIGN",         (0,0),  (-1,-1), "CENTER"),
        ("VALIGN",        (0,0),  (-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS",(0,2),  (-1,-1), [WHITE, GRAY_BG]),
        ("GRID",          (0,0),  (-1,-1), 0.4, GRAY_BORDER),
        ("TOPPADDING",    (0,0),  (-1,-1), 4),
        ("BOTTOMPADDING", (0,0),  (-1,-1), 4),
        # Tint PNG data columns
        ("BACKGROUND",    (8,2),  (11,n),  PNG_BG),
        # Bold cost columns
        ("FONTNAME",      (7,2),  (7,-1),  "Helvetica-Bold"),
        ("FONTNAME",      (11,2), (11,-1), "Helvetica-Bold"),
        ("TEXTCOLOR",     (7,2),  (7,-1),  DARK_BLUE),
        ("TEXTCOLOR",     (11,2), (11,-1), colors.HexColor("#7c2d12")),
        # Vertical divider between JPEG and PNG
        ("LINEAFTER",     (7,0),  (7,-1),  1.2, GRAY_BORDER),
    ]))
    return t


def zoom_detail_table(zoom_rows, jpg_tot, png_tot, page_w):
    """Per-zoom breakdown for one GSD: JPEG and PNG side by side."""
    hdr0 = ["", "", "JPEG", "JPEG", "JPEG", "JPEG", "JPEG", "PNG", "PNG", "PNG", "PNG"]
    hdr1 = ["Zoom", "Tiles", "KB/tile", "Cache GB", "$/mo", "Build Hrs", "Build $",
                             "KB/tile", "Cache GB", "$/mo", "Build $"]
    rows = [hdr0, hdr1]

    for r in zoom_rows:
        rows.append([
            f"z{r['z']}",
            f"{r['tiles']:,}",
            f"{r['kb_jpg']:.1f}",
            f"{r['gb_jpg']:.1f}",
            f"${r['stor_jpg']:.2f}",
            f"{r['hrs']:.1f}",
            f"${r['comp']:.2f}",
            f"{r['kb_png']:.1f}",
            f"{r['gb_png']:.1f}",
            f"${r['stor_png']:.2f}",
            f"${r['comp']:.2f}",   # build cost same for both formats (compute time identical)
        ])

    n_data = len(rows)
    rows.append([
        "TOTAL", f"{jpg_tot['tiles']:,}",
        "", f"{jpg_tot['gb']:.1f}", f"${jpg_tot['stor']:.2f}", f"{jpg_tot['hrs']:.0f}", f"${jpg_tot['comp']:.2f}",
        "", f"{png_tot['gb']:.1f}", f"${png_tot['stor']:.2f}", f"${png_tot['comp']:.2f}",
    ])

    cw = [page_w * f for f in [0.07, 0.12, 0.07, 0.08, 0.08, 0.08, 0.08,
                                        0.07, 0.08, 0.08, 0.08]]
    t = Table(rows, colWidths=cw, repeatRows=2)
    nr = len(rows) - 1
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),  (1,0),   DARK_BLUE),
        ("BACKGROUND",    (2,0),  (6,0),   MID_BLUE),
        ("BACKGROUND",    (7,0),  (10,0),  ORANGE),
        ("TEXTCOLOR",     (0,0),  (-1,0),  WHITE),
        ("FONTNAME",      (0,0),  (-1,0),  "Helvetica-Bold"),
        ("SPAN",          (0,0),  (1,0)),
        ("SPAN",          (2,0),  (6,0)),
        ("SPAN",          (7,0),  (10,0)),
        ("BACKGROUND",    (0,1),  (1,1),   DARK_BLUE),
        ("BACKGROUND",    (2,1),  (6,1),   MID_BLUE),
        ("BACKGROUND",    (7,1),  (10,1),  ORANGE),
        ("TEXTCOLOR",     (0,1),  (-1,1),  WHITE),
        ("FONTNAME",      (0,1),  (-1,1),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),  (-1,-1), 7),
        ("ALIGN",         (0,0),  (-1,-1), "CENTER"),
        ("VALIGN",        (0,0),  (-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS",(0,2),  (-1,nr-1), [WHITE, GRAY_BG]),
        ("BACKGROUND",    (7,2),  (10,nr-1), PNG_BG),
        ("GRID",          (0,0),  (-1,-1), 0.4, GRAY_BORDER),
        ("TOPPADDING",    (0,0),  (-1,-1), 3),
        ("BOTTOMPADDING", (0,0),  (-1,-1), 3),
        ("LINEAFTER",     (6,0),  (6,-1),  1.2, GRAY_BORDER),
        # Totals row
        ("BACKGROUND",    (0,nr), (-1,nr), LIGHT_BLUE),
        ("FONTNAME",      (0,nr), (-1,nr), "Helvetica-Bold"),
        ("TEXTCOLOR",     (0,nr), (-1,nr), DARK_BLUE),
        ("LINEABOVE",     (0,nr), (-1,nr), 1.0, MID_BLUE),
    ]))
    return t


def assumptions_table(page_w):
    rows = [
        ["Parameter", "Value", "Notes"],
        ["Storage rate",    "$0.018 / GB / month",  "Azure Hot LRS, southcentralus"],
        ["VM rate",         "$0.169 / hr",           "Standard_F4s_v2 PAYG, southcentralus"],
        ["Cache build threads", "4",                 "GWC default, matches vCPU count"],
        ["Tile size",       "256 x 256 px",          "GWC default"],
        ["Gridset",         "1-PI-WMQ",              "EPSG:3857 WebMercator, aligned top-left"],
        ["JPEG size model", "60 KB at native zoom",  "Estimated; calibrate with test seed"],
        ["PNG size model",  "150 KB at native zoom", "2.5x JPEG estimate (lossless)"],
        ["Build rate model","150 tiles/min/thread at native zoom", "COG Azure blob backend; estimated"],
        ["AOI method",      "Per-strip sum",          "Individual coverage bboxes summed, not union rectangle"],
    ]
    col_w = [page_w * 0.22, page_w * 0.25, page_w * 0.53]
    t = Table(rows, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),  (-1,0),  DARK_BLUE),
        ("TEXTCOLOR",     (0,0),  (-1,0),  WHITE),
        ("FONTNAME",      (0,0),  (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),  (-1,-1), 7),
        ("ALIGN",         (1,1),  (-1,-1), "LEFT"),
        ("VALIGN",        (0,0),  (-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS",(0,1),  (-1,-1), [WHITE, GRAY_BG]),
        ("GRID",          (0,0),  (-1,-1), 0.4, GRAY_BORDER),
        ("TOPPADDING",    (0,0),  (-1,-1), 4),
        ("BOTTOMPADDING", (0,0),  (-1,-1), 4),
        ("FONTNAME",      (0,1),  (0,-1),  "Helvetica-Bold"),
    ]))
    return t

# ── Main ───────────────────────────────────────────────────────────────────────
def run(workspace, output_pdf):
    st = styles()
    print(f"Loading coverage bboxes for {workspace}...")
    bboxes = get_workspace_bboxes(workspace)
    print(f"  {len(bboxes)} coverages loaded")

    gsd_results = []
    for gsd_m, _ in GSD_ZOOM_TABLE:
        print(f"  Computing z{MIN_ZOOM}-z{max_useful_zoom(gsd_m)} for {gsd_m*100:g}cm GSD...")
        native_z, zoom_rows, jpg_tot, png_tot = compute_gsd_row(gsd_m, bboxes)
        gsd_results.append((gsd_m, native_z, zoom_rows, jpg_tot, png_tot))

    min_lon = min(b[0] for b in bboxes); max_lon = max(b[1] for b in bboxes)
    min_lat = min(b[2] for b in bboxes); max_lat = max(b[3] for b in bboxes)
    mid_lat = (min_lat + max_lat) / 2
    width_km  = round((max_lon - min_lon) * math.cos(math.radians(mid_lat)) * 111.32, 1)
    height_km = round((max_lat - min_lat) * 111.32, 1)

    # Repack for banner (expects 4-tuple)
    banner_results = [(g, nz, jt, pt) for g, nz, _, jt, pt in gsd_results]

    doc = SimpleDocTemplate(output_pdf, pagesize=letter,
                            leftMargin=0.5*inch, rightMargin=0.5*inch,
                            topMargin=0.5*inch,  bottomMargin=0.5*inch)
    page_w = letter[0] - 1.0 * inch
    story  = []

    # Header
    for elem in header_banner(workspace, len(bboxes), banner_results, page_w):
        story.append(elem)
    story.append(Spacer(1, 8))

    # AOI info bar
    story.append(aoi_info_bar(bboxes, width_km, height_km,
                              min_lon, max_lon, min_lat, max_lat, page_w))
    story.append(Spacer(1, 12))

    # Summary comparison table
    story.append(Paragraph("Tile Cache Cost by GSD — Summary (z10 to Max Useful Zoom)", st["h2"]))
    story.append(Paragraph(
        "Each row is an independent scenario from z10 to the maximum useful zoom for that GSD. "
        "Tile counts are summed across individual coverage strips (not a union bounding box). "
        "JPEG and PNG cache costs shown side by side. Cache build cost is one-time; storage cost recurs monthly.",
        st["body"]))
    story.append(Spacer(1, 5))
    story.append(summary_table(banner_results, page_w))
    story.append(Spacer(1, 16))

    # Per-GSD detail tables
    story.append(Paragraph("Per-Zoom Tile Cache Cost Breakdown by GSD", st["h2"]))
    story.append(Paragraph(
        "The highest zoom level typically accounts for over 90% of total cost. "
        "Cache build compute cost is the same for JPEG and PNG — only storage differs.",
        st["body"]))
    story.append(Spacer(1, 6))

    for gsd_m, native_z, zoom_rows, jpg_tot, png_tot in gsd_results:
        label = (f"{gsd_m*100:g} cm GSD  |  z{MIN_ZOOM} to z{native_z}  |  "
                 f"{jpg_tot['tiles']:,} tiles  |  "
                 f"JPEG: {jpg_tot['gb']:.0f} GB / ${jpg_tot['stor']:.2f}/mo / ${jpg_tot['comp']:.2f} build  |  "
                 f"PNG: {png_tot['gb']:.0f} GB / ${png_tot['stor']:.2f}/mo / ${png_tot['comp']:.2f} build")
        story.append(KeepTogether([
            Paragraph(label, st["h3"]),
            zoom_detail_table(zoom_rows, jpg_tot, png_tot, page_w),
            Spacer(1, 10),
        ]))

    # Assumptions
    story.append(HRFlowable(width=page_w, color=GRAY_BORDER, spaceAfter=8))
    story.append(Paragraph("Model Assumptions & Parameters", st["h2"]))
    story.append(assumptions_table(page_w))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Tile size and cache build rate figures are estimates based on typical aerial COG imagery "
        "served from Azure Blob Storage. Run a calibration seed on a small bounding box at "
        "each zoom level to obtain measured values for production cost planning.",
        st["note"]))

    doc.build(story)
    print(f"\nReport written: {output_pdf}")


def main():
    p = argparse.ArgumentParser(description="GeoServer AOI tile cache cost report (PDF)")
    p.add_argument("--workspace", default="WW-BCOMB-Test", help="GeoServer workspace name")
    p.add_argument("--output",    default=r"C:\Users\pi\claude\GeoServer_Seeding_Cost.pdf",
                   help="Output PDF path")
    args = p.parse_args()
    run(args.workspace, args.output)


if __name__ == "__main__":
    main()
