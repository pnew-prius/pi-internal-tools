"""
Generate pipeline cost report PDF from pipeline_runs.json (real data only).
"""
import json, math
from collections import defaultdict
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable, PageBreak, KeepTogether)
from reportlab.pdfgen import canvas
from reportlab.platypus.flowables import Flowable

INPUT_JSON = r"C:\Users\pi\claude\pipeline_runs.json"
OUTPUT_PDF = r"C:\Users\pi\claude\COPECODE26_Cost_Report.pdf"

DARK_BLUE   = colors.HexColor("#1e3a5f")
MID_BLUE    = colors.HexColor("#2563eb")
LIGHT_BLUE  = colors.HexColor("#dbeafe")
ACCENT      = colors.HexColor("#0ea5e9")
GREEN       = colors.HexColor("#16a34a")
ORANGE      = colors.HexColor("#ea580c")
PURPLE      = colors.HexColor("#7c3aed")
GRAY_BG     = colors.HexColor("#f8fafc")
GRAY_BORDER = colors.HexColor("#e2e8f0")
TEXT_DARK   = colors.HexColor("#0f172a")
TEXT_MID    = colors.HexColor("#475569")
TEXT_LIGHT  = colors.HexColor("#94a3b8")
RED         = colors.HexColor("#dc2626")

# ── Load data ──────────────────────────────────────────────────────────────────
with open(INPUT_JSON, encoding="utf-8") as f:
    all_records = json.load(f)

standard = [r for r in all_records if not r["Excluded"] and not r["IsRetrim"] and not r["Failed"]]
retrims  = [r for r in all_records if not r["Excluded"] and r["IsRetrim"]]
failures = [r for r in all_records if r["Failed"] and not r["Excluded"]]

def s(v):
    return v if v is not None else "N/A"

def fv(v, fmt):
    if v is None: return "N/A"
    if fmt == "$2":  return f"${v:,.2f}"
    if fmt == "$4":  return f"${v:.4f}"
    if fmt == ",":   return f"{v:,}"
    if fmt == "f2":  return f"{v:.2f}"
    if fmt == "f4":  return f"{v:.4f}"
    return str(v)

TOTAL_TILES      = len(standard)
TOTAL_IMAGES     = sum(r["ImageCount"] or 0 for r in standard)
AOI_SQ_MI        = round(sum(r["AoiSqMiles"] or 0 for r in standard), 3)
COLL_SQ_MI       = round(sum(r["CollectionSqMiles"] or 0 for r in standard), 3)
COLL_LINEAR_MI   = round(sum(r["CollectionLinearMiles"] or 0 for r in standard), 3)
TOTAL_HRS        = round(sum(r["TotalHrs"] for r in standard), 2)
MOSAIC_HRS       = round(sum(r["MosaicHrs"] or 0 for r in standard), 2)
GDAL_HRS         = round(sum(r["GdalHrs"] or 0 for r in standard), 2)
COMPUTE_COST     = round(sum(r["ComputeCost"] for r in standard), 2)
LICENSE_COST     = round(sum(r.get("LicenseCost") or 0
                             for r in all_records if not r["Excluded"]), 2)
MOSAIC_COST      = round(MOSAIC_HRS * 0.816, 2)
GDAL_COST        = round(GDAL_HRS   * 0.816, 2)
RETRIM_COUNT     = len(retrims)
FAIL_COUNT       = len(failures)

# Shared platform apportionment (real Azure billing May-Jun 2026)
TOTAL_DEVOPS_HRS    = 550.82
PROJ_SHARE          = round(TOTAL_HRS / TOTAL_DEVOPS_HRS, 4)
PREMIUM_SSD_TOTAL   = 486.70
STANDARD_SSD_TOTAL  = 151.32
PRIVATE_LINK_TOTAL  = 66.58
BLOB_STORAGE_TOTAL  = 191.86

SHARED_PREMIUM_SSD  = round(PREMIUM_SSD_TOTAL  * PROJ_SHARE, 2)
SHARED_STANDARD_SSD = round(STANDARD_SSD_TOTAL * PROJ_SHARE, 2)
SHARED_PRIVATE_LINK = round(PRIVATE_LINK_TOTAL * PROJ_SHARE, 2)
SHARED_BLOB_STORAGE = round(BLOB_STORAGE_TOTAL * PROJ_SHARE, 2)
GRAND_TOTAL         = round(COMPUTE_COST + LICENSE_COST + SHARED_PREMIUM_SSD +
                             SHARED_STANDARD_SSD + SHARED_PRIVATE_LINK + SHARED_BLOB_STORAGE, 2)

gsd_vals            = [r["GsdCm"] for r in standard if r.get("GsdCm") is not None]
AVG_GSD             = round(sum(gsd_vals) / len(gsd_vals), 2) if gsd_vals else None

UNIT_PER_IMG        = round(GRAND_TOTAL / TOTAL_IMAGES,   4) if TOTAL_IMAGES   else None
UNIT_PER_AOI_SQMI   = round(GRAND_TOTAL / AOI_SQ_MI,      4) if AOI_SQ_MI      else None
UNIT_PER_COLL_SQMI  = round(GRAND_TOTAL / COLL_SQ_MI,     4) if COLL_SQ_MI     else None
UNIT_PER_LINEAR_MI  = round(GRAND_TOTAL / COLL_LINEAR_MI, 4) if COLL_LINEAR_MI else None

run_dates    = [r["RunDate"] for r in all_records if r.get("RunDate")]
PERIOD_START = min(run_dates)[:7] if run_dates else "N/A"
PERIOD_END   = max(run_dates)[:7] if run_dates else "N/A"

CUSTOMER = next((r["Customer"] for r in standard if r.get("Customer")), "N/A")
PROJECT  = next((r["Project"]  for r in standard if r.get("Project")),  "N/A")

monthly = defaultdict(lambda: {"mosaic_cost":0.0,"gdal_cost":0.0,"tiles":0,"images":0,
                                "aoi_sq_mi":0.0,"coll_sq_mi":0.0,"linear_mi":0.0,"hrs":0.0})
for r in standard:
    if r.get("RunDate"):
        mo = r["RunDate"][:7]
        monthly[mo]["mosaic_cost"] += round((r["MosaicHrs"] or 0) * 0.816, 4)
        monthly[mo]["gdal_cost"]   += round((r["GdalHrs"]   or 0) * 0.816, 4)
        monthly[mo]["tiles"]       += 1
        monthly[mo]["images"]      += r["ImageCount"] or 0
        monthly[mo]["aoi_sq_mi"]   += r["AoiSqMiles"]            or 0
        monthly[mo]["coll_sq_mi"]  += r["CollectionSqMiles"]     or 0
        monthly[mo]["linear_mi"]   += r["CollectionLinearMiles"] or 0
        monthly[mo]["hrs"]         += r["TotalHrs"]

# ── Canvas / numbering ─────────────────────────────────────────────────────────
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        n = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self.setFont("Helvetica", 8)
            self.setFillColor(TEXT_LIGHT)
            self.drawRightString(letter[0]-0.5*inch, 0.4*inch, f"Page {self._pageNumber} of {n}")
            self.drawString(0.5*inch, 0.4*inch, "Prius Intelli LLC  |  Confidential  |  For Internal Use Only")
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

# ── Horizontal bar chart ───────────────────────────────────────────────────────
class HorizBarChart(Flowable):
    def __init__(self, data, width=440, row_h=22):
        super().__init__()
        self.data   = data        # [(label, value, color), ...]
        self.width  = width
        self.row_h  = row_h
        self.height = row_h * len(data) + 16

    def draw(self):
        max_val  = max((v for _, v, _ in self.data), default=1)
        bar_area = self.width - 160
        y = self.height - 16
        for label, val, col in self.data:
            bar_w = int(bar_area * val / max_val) if max_val else 0
            self.canv.setFillColor(colors.HexColor("#f1f5f9"))
            self.canv.rect(130, y - self.row_h + 5, bar_area, self.row_h - 6, fill=1, stroke=0)
            self.canv.setFillColor(col)
            self.canv.rect(130, y - self.row_h + 5, bar_w, self.row_h - 6, fill=1, stroke=0)
            self.canv.setFillColor(TEXT_DARK)
            self.canv.setFont("Helvetica", 8)
            self.canv.drawString(0, y - self.row_h + 8, label)
            self.canv.setFont("Helvetica-Bold", 8)
            self.canv.drawRightString(self.width, y - self.row_h + 8, f"${val:,.2f}")
            y -= self.row_h

# ── Build PDF ──────────────────────────────────────────────────────────────────
def build_pdf():
    doc = SimpleDocTemplate(
        OUTPUT_PDF, pagesize=letter,
        leftMargin=0.5*inch, rightMargin=0.5*inch,
        topMargin=0.5*inch, bottomMargin=0.65*inch,
    )
    W = letter[0] - inch
    styles = getSampleStyleSheet()
    h2   = ParagraphStyle("h2",  fontSize=11, textColor=DARK_BLUE,
                           fontName="Helvetica-Bold", spaceAfter=5, spaceBefore=10)
    note = ParagraphStyle("note",fontSize=8,  textColor=TEXT_MID, fontName="Helvetica-Oblique")
    sm   = ParagraphStyle("sm",  fontSize=7,  textColor=TEXT_LIGHT, fontName="Helvetica")

    story = []

    # ── Header banner ──────────────────────────────────────────────────────────
    def header_table():
        d = [[
            Paragraph("<font color='#ffffff'><b>Prius Intelli LLC</b></font>", styles["Normal"]),
            Paragraph("<font color='#93c5fd'>Processing Cost Report</font>",   styles["Normal"]),
            Paragraph(f"<font color='#ffffff'><b>{PROJECT.upper()}</b></font>",styles["Normal"]),
        ]]
        t = Table(d, colWidths=[W*0.35, W*0.35, W*0.30])
        t.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), DARK_BLUE),
            ("TOPPADDING",   (0,0),(-1,-1), 11),
            ("BOTTOMPADDING",(0,0),(-1,-1), 11),
            ("LEFTPADDING",  (0,0),(0,-1),  14),
            ("ALIGN",        (1,0),(1,-1),  "CENTER"),
            ("ALIGN",        (2,0),(2,-1),  "RIGHT"),
            ("RIGHTPADDING", (2,0),(2,-1),  14),
            ("FONTSIZE",     (0,0),(-1,-1), 11),
        ]))
        return t

    story.append(header_table())
    story.append(Spacer(1, 5))

    # Sub-header
    sub_d = [[
        Paragraph(f"Customer: <b>{CUSTOMER}</b>", ParagraphStyle("s", fontSize=9, textColor=TEXT_MID, fontName="Helvetica")),
        Paragraph(f"Project: <b>{PROJECT.upper()}</b>", ParagraphStyle("s", fontSize=9, textColor=TEXT_MID, fontName="Helvetica")),
        Paragraph(f"Period: <b>{PERIOD_START} to {PERIOD_END}</b>", ParagraphStyle("s", fontSize=9, textColor=TEXT_MID, fontName="Helvetica")),
        Paragraph("Generated: <b>Jun 2026</b>", ParagraphStyle("s", fontSize=9, textColor=TEXT_MID, fontName="Helvetica")),
    ]]
    st = Table(sub_d, colWidths=[W/4]*4)
    st.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), LIGHT_BLUE),
        ("TOPPADDING",   (0,0),(-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
        ("LEFTPADDING",  (0,0),(0,-1),  14),
        ("ALIGN",        (1,0),(-1,-1), "CENTER"),
    ]))
    story.append(st)
    story.append(Spacer(1, 10))

    # ── Summary metric cards ───────────────────────────────────────────────────
    story.append(Paragraph("Project Summary", h2))
    cards = [
        ("Total Cost",      fv(GRAND_TOTAL,  "$2"),  DARK_BLUE),
        ("Tiles Processed", fv(TOTAL_TILES,  ","),   MID_BLUE),
        ("Images",          fv(TOTAL_IMAGES, ","),   ACCENT),
        ("AOI Area",        f"{AOI_SQ_MI} sq mi" if AOI_SQ_MI else "N/A", GREEN),
        ("Avg GSD",         f"{AVG_GSD} cm" if AVG_GSD else "N/A", PURPLE),
        ("Compute Hours",   fv(TOTAL_HRS,    "f2"),  ORANGE),
        ("Failed Runs",     str(FAIL_COUNT),          RED),
        ("Re-trims",        str(RETRIM_COUNT),         colors.HexColor("#d97706")),
    ]
    cw = W / len(cards)
    ct = Table([[
        Paragraph(f"<font color='#ffffff'><b>{v}</b><br/><font size='7'>{k}</font></font>", styles["Normal"])
        for k, v, _ in cards
    ]], colWidths=[cw]*len(cards))
    ct.setStyle(TableStyle(
        [("BACKGROUND", (i,0),(i,0), cards[i][2]) for i in range(len(cards))] +
        [("TOPPADDING",    (0,0),(-1,-1), 9),
         ("BOTTOMPADDING", (0,0),(-1,-1), 9),
         ("ALIGN",         (0,0),(-1,-1), "CENTER"),
         ("FONTSIZE",      (0,0),(-1,-1), 10)]
    ))
    story.append(ct)
    story.append(Spacer(1, 8))

    # Unit costs band
    unit_rows = [["Unit Cost Metric", "Value", "Basis"]]
    unit_rows.append([
        "Cost per Image",
        fv(UNIT_PER_IMG, "$4"),
        f"{TOTAL_IMAGES:,} images across {TOTAL_TILES} tiles" if TOTAL_IMAGES else "Insufficient data",
    ])
    unit_rows.append([
        "Cost per AOI Sq Mile",
        fv(UNIT_PER_AOI_SQMI, "$4"),
        f"{AOI_SQ_MI} sq mi — KML trim polygon (deliverable area)",
    ])
    unit_rows.append([
        "Cost per Collection Sq Mile",
        fv(UNIT_PER_COLL_SQMI, "$4"),
        f"{COLL_SQ_MI} sq mi — bounding box of all image positions",
    ])
    unit_rows.append([
        "Cost per Collection Linear Mile",
        fv(UNIT_PER_LINEAR_MI, "$4"),
        f"{COLL_LINEAR_MI} mi — straight flight lines, turns excluded (Kappa-filtered)",
    ])

    ut = Table(unit_rows, colWidths=[W*0.35, W*0.18, W*0.47])
    ut.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  DARK_BLUE),
        ("TEXTCOLOR",     (0,0),(-1,0),  colors.white),
        ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,-1), 8.5),
        ("ALIGN",         (1,0),(1,-1),  "CENTER"),
        ("FONTNAME",      (1,1),(1,-1),  "Helvetica-Bold"),
        ("FONTSIZE",      (1,1),(1,-1),  10),
        ("TEXTCOLOR",     (1,1),(1,-1),  DARK_BLUE),
        ("TEXTCOLOR",     (2,1),(2,-1),  TEXT_MID),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [colors.white, GRAY_BG]),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("LEFTPADDING",   (0,0),(0,-1),  8),
        ("BOX",           (0,0),(-1,-1), 0.5, GRAY_BORDER),
        ("INNERGRID",     (0,0),(-1,-1), 0.3, GRAY_BORDER),
    ]))
    story.append(ut)
    story.append(Spacer(1, 10))

    # ── Resource cost breakdown ────────────────────────────────────────────────
    story.append(HRFlowable(width=W, thickness=0.5, color=GRAY_BORDER))
    story.append(Paragraph("Resource Cost Breakdown", h2))
    story.append(Paragraph(
        f"Project share: {PROJ_SHARE*100:.1f}%  ({TOTAL_HRS} project hrs "
        f"÷ {TOTAL_DEVOPS_HRS} total DevOps hrs May–Jun 2026). "
        f"Shared costs apportioned by compute hours.", note))
    story.append(Spacer(1, 5))

    res_rows = [
        ["Cost Category", "Basis", "Platform Total", "Project Share", "Project Cost"],
        ["Pipeline Compute (Mosaic + GDAL)",
         f"Standard_F16s_v2 @ $0.816/hr  |  {TOTAL_HRS} hrs",
         "N/A — direct",
         "100%",
         fv(COMPUTE_COST, "$2")],
        ["One-Button Software License",
         f"$0.50/hr mosaic runtime  |  all runs incl. failed",
         "N/A — direct",
         "100%",
         fv(LICENSE_COST, "$2")],
        ["Storage — Premium SSD (data disks)",
         "Shared VM data disks — apportioned",
         fv(PREMIUM_SSD_TOTAL, "$2"),
         f"{PROJ_SHARE*100:.1f}%",
         fv(SHARED_PREMIUM_SSD, "$2")],
        ["Storage — Standard SSD (OS disks)",
         "Shared VM OS disks — apportioned",
         fv(STANDARD_SSD_TOTAL, "$2"),
         f"{PROJ_SHARE*100:.1f}%",
         fv(SHARED_STANDARD_SSD, "$2")],
        ["Network — Private Link",
         "Shared private endpoints — apportioned",
         fv(PRIVATE_LINK_TOTAL, "$2"),
         f"{PROJ_SHARE*100:.1f}%",
         fv(SHARED_PRIVATE_LINK, "$2")],
        ["Blob Storage (piimageprocessing)",
         "Storage account — apportioned by compute share",
         fv(BLOB_STORAGE_TOTAL, "$2"),
         f"{PROJ_SHARE*100:.1f}%",
         fv(SHARED_BLOB_STORAGE, "$2")],
        ["TOTAL", "", "", "", fv(GRAND_TOTAL, "$2")],
    ]
    rcw = [W*0.30, W*0.30, W*0.13, W*0.11, W*0.13]
    rt  = Table(res_rows, colWidths=rcw)
    rt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  DARK_BLUE),
        ("TEXTCOLOR",     (0,0),(-1,0),  colors.white),
        ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,-1), 8),
        ("ALIGN",         (2,0),(-1,-1), "RIGHT"),
        ("ALIGN",         (0,0),(1,-1),  "LEFT"),
        ("ROWBACKGROUNDS",(0,1),(-1,-2), [colors.white, GRAY_BG]),
        ("BACKGROUND",    (0,-1),(-1,-1), LIGHT_BLUE),
        ("FONTNAME",      (0,-1),(-1,-1), "Helvetica-Bold"),
        ("FONTSIZE",      (-1,-1),(-1,-1), 10),
        ("TEXTCOLOR",     (-1,-1),(-1,-1), DARK_BLUE),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ("LEFTPADDING",   (0,0),(0,-1),  8),
        ("BOX",           (0,0),(-1,-1), 0.5, GRAY_BORDER),
        ("INNERGRID",     (0,0),(-1,-1), 0.3, GRAY_BORDER),
    ]))
    story.append(rt)
    story.append(Spacer(1, 10))

    # ── Compute cost breakdown by pipeline ────────────────────────────────────
    story.append(HRFlowable(width=W, thickness=0.5, color=GRAY_BORDER))
    story.append(Paragraph("Compute Cost Breakdown", h2))
    bar_data = [
        ("Mosaic (One-Button)", MOSAIC_COST, DARK_BLUE),
        ("GDAL Processing",     GDAL_COST,   MID_BLUE),
    ]
    story.append(HorizBarChart(bar_data, width=int(W*0.7), row_h=24))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"Mosaic: {MOSAIC_HRS} hrs  |  GDAL: {GDAL_HRS} hrs  |  "
        f"Total: {TOTAL_HRS} hrs @ $0.816/hr (Standard_F16s_v2 PAYG)", note))
    story.append(Paragraph(
        "DevOps platform, network egress, and output storage costs not yet included.", note))
    story.append(Spacer(1, 10))

    # ── Monthly summary ────────────────────────────────────────────────────────
    mo_hdr  = ["Month", "Tiles", "Images", "AOI Sq Mi", "Coll Sq Mi", "Linear Mi",
               "Mosaic $", "GDAL $", "Total $", "$/Image", "$/Lin Mi"]
    mo_rows = [mo_hdr]
    for mo in sorted(monthly.keys()):
        d  = monthly[mo]
        tc = round(d["mosaic_cost"] + d["gdal_cost"], 2)
        mo_rows.append([
            mo,
            str(d["tiles"]),
            f"{d['images']:,}",
            f"{round(d['aoi_sq_mi'],2)}"  if d["aoi_sq_mi"]  else "N/A",
            f"{round(d['coll_sq_mi'],2)}" if d["coll_sq_mi"] else "N/A",
            f"{round(d['linear_mi'],2)}"  if d["linear_mi"]  else "N/A",
            fv(round(d["mosaic_cost"],2), "$2"),
            fv(round(d["gdal_cost"],2),   "$2"),
            fv(tc, "$2"),
            fv(round(tc/d["images"],4),    "$4") if d["images"]    else "N/A",
            fv(round(tc/d["linear_mi"],4), "$4") if d["linear_mi"] else "N/A",
        ])
    mo_rows.append([
        "Total", str(TOTAL_TILES), f"{TOTAL_IMAGES:,}",
        str(AOI_SQ_MI)      if AOI_SQ_MI      else "N/A",
        str(COLL_SQ_MI)     if COLL_SQ_MI     else "N/A",
        str(COLL_LINEAR_MI) if COLL_LINEAR_MI else "N/A",
        fv(MOSAIC_COST, "$2"), fv(GDAL_COST, "$2"), fv(GRAND_TOTAL, "$2"),
        fv(UNIT_PER_IMG, "$4"), fv(UNIT_PER_LINEAR_MI, "$4"),
    ])
    mcw = [W*0.08, W*0.05, W*0.07, W*0.08, W*0.08, W*0.08,
           W*0.09, W*0.09, W*0.09, W*0.09, W*0.09]
    mt  = Table(mo_rows, colWidths=mcw)
    mt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  DARK_BLUE),
        ("TEXTCOLOR",     (0,0),(-1,0),  colors.white),
        ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,-1), 8),
        ("ALIGN",         (1,0),(-1,-1), "RIGHT"),
        ("ALIGN",         (0,0),(0,-1),  "LEFT"),
        ("ROWBACKGROUNDS",(0,1),(-1,-2), [colors.white, GRAY_BG]),
        ("BACKGROUND",    (0,-1),(-1,-1), LIGHT_BLUE),
        ("FONTNAME",      (0,-1),(-1,-1), "Helvetica-Bold"),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ("LEFTPADDING",   (0,0),(0,-1),  6),
        ("BOX",           (0,0),(-1,-1), 0.5, GRAY_BORDER),
        ("INNERGRID",     (0,0),(-1,-1), 0.3, GRAY_BORDER),
    ]))
    story.append(HRFlowable(width=W, thickness=0.5, color=GRAY_BORDER))
    story.append(KeepTogether([
        Paragraph("Monthly Summary", h2),
        mt,
    ]))

    # ── Tile detail table ──────────────────────────────────────────────────────
    story.append(Spacer(1, 14))
    story.append(header_table())
    story.append(Spacer(1, 8))
    story.append(Paragraph("Tile Detail", h2))
    story.append(Paragraph(
        "All tiles with confirmed pipeline runs. "
        "Images from input zip. AOI sq mi from KML polygon. "
        "Collection sq mi = image bounding box. Linear mi = flight lines only (Kappa-filtered). "
        "Flight dir = canonical heading 0-180°.", note))
    story.append(Spacer(1, 6))

    tile_hdr = ["Tile", "Imgs", "AOI Sq Mi", "Coll Sq Mi", "Lin Mi", "Flt Dir", "GSD cm",
                "Mos Hrs", "GDAL Hrs", "Tot Hrs", "$/Img", "$/Lin Mi", "Total $"]
    tile_rows = [tile_hdr]

    for r in sorted(all_records, key=lambda x: (x.get("Customer") or "", x["TileKey"], x["IsRetrim"])):
        if r["Excluded"]:
            continue
        result_lbl = "FAIL" if r["Failed"] else ("retrim" if r["IsRetrim"] else "")

        row = [
            r["TileKey"],
            fv(r["ImageCount"], ","),
            fv(r["AoiSqMiles"],            "f2") if r.get("AoiSqMiles")            else "N/A",
            fv(r["CollectionSqMiles"],     "f2") if r.get("CollectionSqMiles")     else "N/A",
            fv(r["CollectionLinearMiles"], "f2") if r.get("CollectionLinearMiles") else "N/A",
            f"{r['FlightDirection']:.0f}°"       if r.get("FlightDirection") is not None else "N/A",
            f"{r['GsdCm']:.2f}"                  if r.get("GsdCm")          is not None else "N/A",
            fv(r["MosaicHrs"], "f3") if r["MosaicHrs"] is not None else "N/A",
            fv(r["GdalHrs"],   "f3") if r["GdalHrs"]   is not None else "N/A",
            fv(r["TotalHrs"],  "f3"),
            fv(r["CostPerImage"],  "$4") if r.get("CostPerImage")  else "N/A",
            fv(r.get("CostPerLinearMi"), "$4") if r.get("CostPerLinearMi") else "N/A",
            fv(r["ComputeCost"], "$2"),
        ]
        tile_rows.append(row)

    # Totals
    tile_rows.append([
        "TOTAL",
        fv(TOTAL_IMAGES, ","),
        str(AOI_SQ_MI)      if AOI_SQ_MI      else "N/A",
        str(COLL_SQ_MI)     if COLL_SQ_MI     else "N/A",
        str(COLL_LINEAR_MI) if COLL_LINEAR_MI else "N/A",
        "", "",
        fv(MOSAIC_HRS, "f2"), fv(GDAL_HRS, "f2"), fv(TOTAL_HRS, "f2"),
        fv(UNIT_PER_IMG, "$4"), fv(UNIT_PER_LINEAR_MI, "$4"),
        fv(COMPUTE_COST, "$2"),
    ])

    tcw = [W*0.11, W*0.05, W*0.07, W*0.07, W*0.06, W*0.05, W*0.06,
           W*0.06, W*0.06, W*0.06, W*0.08, W*0.08, W*0.07]
    tt  = Table(tile_rows, colWidths=tcw, repeatRows=1)
    ts  = TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  DARK_BLUE),
        ("TEXTCOLOR",     (0,0),(-1,0),  colors.white),
        ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,-1), 7),
        ("ALIGN",         (1,0),(-1,-1), "RIGHT"),
        ("ALIGN",         (0,0),(0,-1),  "LEFT"),
        ("ALIGN",         (5,0),(5,-1),  "CENTER"),
        ("TOPPADDING",    (0,0),(-1,-1), 3),
        ("BOTTOMPADDING", (0,0),(-1,-1), 3),
        ("LEFTPADDING",   (0,0),(0,-1),  5),
        ("BOX",           (0,0),(-1,-1), 0.5, GRAY_BORDER),
        ("INNERGRID",     (0,0),(-1,-1), 0.2, GRAY_BORDER),
        ("BACKGROUND",    (0,-1),(-1,-1), LIGHT_BLUE),
        ("FONTNAME",      (0,-1),(-1,-1), "Helvetica-Bold"),
    ])
    visible = [r for r in all_records if not r["Excluded"]]
    visible.sort(key=lambda x: (x.get("Customer") or "", x["TileKey"], x["IsRetrim"]))
    for i, rec in enumerate(visible, start=1):
        if i % 2 == 0:
            ts.add("BACKGROUND", (0,i),(-1,i), GRAY_BG)
        if rec["IsRetrim"]:
            ts.add("BACKGROUND", (0,i),(-1,i), colors.HexColor("#fff7ed"))
            ts.add("TEXTCOLOR",  (0,i),(0,i),  ORANGE)
        if rec["Failed"]:
            ts.add("BACKGROUND", (0,i),(-1,i), colors.HexColor("#fef2f2"))
            ts.add("TEXTCOLOR",  (0,i),(0,i),  RED)
    tt.setStyle(ts)
    story.append(tt)
    story.append(Spacer(1, 10))

    # Footer notes
    story.append(HRFlowable(width=W, thickness=0.5, color=GRAY_BORDER))
    story.append(Spacer(1, 4))
    for n in [
        "Compute: Standard_F16s_v2 @ $0.816/hr PAYG southcentralus. Hours from DevOps build start/finish times.",
        "Image counts: from input zip (tobeprocessed). AOI sq mi: Shoelace formula on KML polygon.",
        "Collection sq mi: bounding box of all GPS image positions. Linear mi: on-line segments only, turns excluded by Kappa heading filter.",
        "Flight direction: canonical heading 0-180 deg derived from Kappa bimodal cluster mean (doubled-angle circular statistics).",
        f"Shared costs apportioned at {PROJ_SHARE*100:.1f}% ({TOTAL_HRS} project hrs / {TOTAL_DEVOPS_HRS} total hrs, both pipeline orgs, May-Jun 2026).",
        "Shared costs source: Azure Cost Management May-Jun 2026. Categories: Premium SSD, Standard SSD, Private Link, piimageprocessing storage.",
        "Tiles marked Failed are excluded from unit cost calculations. GeoServer delivery costs excluded.",
    ]:
        story.append(Paragraph(f"  {n}", sm))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF saved: {OUTPUT_PDF}")

if __name__ == "__main__":
    build_pdf()
