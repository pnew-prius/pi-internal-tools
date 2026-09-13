import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

wb = openpyxl.Workbook()

FONT_NAME = "Arial"
BLUE = Font(name=FONT_NAME, color="0000FF")
BLUE_BOLD = Font(name=FONT_NAME, color="0000FF", bold=True)
BLACK = Font(name=FONT_NAME, color="000000")
BLACK_BOLD = Font(name=FONT_NAME, color="000000", bold=True)
GREEN = Font(name=FONT_NAME, color="008000")
GREEN_BOLD = Font(name=FONT_NAME, color="008000", bold=True)
TITLE_FONT = Font(name=FONT_NAME, size=16, bold=True, color="1F3D32")
SECTION_FONT = Font(name=FONT_NAME, size=12, bold=True, color="FFFFFF")
HEADER_FONT = Font(name=FONT_NAME, size=10, bold=True, color="FFFFFF")
NOTE_FONT = Font(name=FONT_NAME, size=9, italic=True, color="595959")

SECTION_FILL = PatternFill("solid", fgColor="1F3D32")
HEADER_FILL = PatternFill("solid", fgColor="4A8F8B")
ASSUMPTION_FILL = PatternFill("solid", fgColor="FFFF00")
TOTAL_FILL = PatternFill("solid", fgColor="E6EFEB")

CUR = '$#,##0;($#,##0);"-"'
thin = Side(style="thin", color="BFBFBF")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)

def section_header(ws, cell_range, text):
    ws.merge_cells(cell_range)
    top_left = cell_range.split(":")[0]
    c = ws[top_left]
    c.value = text
    c.font = SECTION_FONT
    c.fill = SECTION_FILL
    c.alignment = Alignment(vertical="center", horizontal="left", indent=1)

def table_header(ws, row, col_start, headers):
    for i, h in enumerate(headers):
        c = ws.cell(row=row, column=col_start + i, value=h)
        c.font = HEADER_FONT
        c.fill = HEADER_FILL
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDER

def style_row(ws, row, col_start, col_end, font=BLACK, number_format=None, fill=None):
    for col in range(col_start, col_end + 1):
        c = ws.cell(row=row, column=col)
        c.font = font
        c.border = BORDER
        if number_format:
            c.number_format = number_format
        if fill:
            c.fill = fill

# =========================================================
# SHEET: Rate Card
# =========================================================
ws = wb.active
ws.title = "Rate Card"
ws.sheet_view.showGridLines = False
ws.column_dimensions["A"].width = 2
ws.column_dimensions["B"].width = 30
ws.column_dimensions["C"].width = 13
ws.column_dimensions["D"].width = 13
ws.column_dimensions["E"].width = 13
ws.column_dimensions["F"].width = 46

ws["B2"] = "Mercator — Resource Rate Card"
ws["B2"].font = TITLE_FONT

ws["B4"] = ("Blended market rates for senior contractors/consultants, reflecting the \"unlimited resources, "
            "fastest possible\" brief — i.e., staffing via contract talent available immediately rather than "
            "a multi-month FTE hiring cycle. US and India columns are directional 2026 market estimates for "
            "equivalent-seniority offshore talent via a reputable development partner, not vendor quotes — see "
            "the India Comparison note below for what this discount does and doesn't account for.")
ws["B4"].font = NOTE_FONT
ws["B4"].alignment = Alignment(wrap_text=True, vertical="top")
ws.merge_cells("B4:F4")
ws.row_dimensions[4].height = 56

section_header(ws, "B6:F6", "Roles & Hourly Rates — US vs. India")
table_header(ws, 7, 2, ["Role", "US Rate", "India Rate", "Savings %", "Notes"])

# (role, US $/hr, India $/hr, note) — India rates reflect a narrower discount for scarcer/
# specialized skills (security, data science, GIS) than for generalist roles, consistent with
# real offshore market patterns rather than a flat percentage off every role.
roles = [
    ("Delivery Lead / TPM", 150, 50, "Program management across all workstreams"),
    ("Senior Backend Engineer", 140, 42, "API, services, data-layer engineering"),
    ("Senior Frontend Engineer", 130, 38, "Portal / web application UI engineering"),
    ("DevOps / Cloud Engineer", 145, 45, "Azure infrastructure, CI/CD, security hardening, migration/cutover"),
    ("QA Engineer", 95, 28, "Test planning, automation, regression, UAT support"),
    ("UX/UI Designer", 110, 35, "Interaction and visual design, part-time allocation"),
    ("Security Consultant", 200, 70, "Short, focused access/credential audit engagement"),
    ("GIS / Geospatial Engineer", 160, 48, "Tile-cache, basemap providers, map-rendering performance"),
    ("Data Engineer", 145, 42, "ETL pipelines, data modeling"),
    ("Analytics Engineer", 135, 40, "Semantic modeling, metrics layer, dashboard integration"),
    ("BI Developer", 120, 36, "Dashboard and report development"),
    ("Data Scientist", 170, 55, "Forecasting and predictive models"),
    ("Business / Systems Analyst", 125, 35, "Reverse-engineering existing spreadsheet/manual business logic into system requirements"),
]
start_row = 8
for i, (role, us_rate, in_rate, note) in enumerate(roles):
    r = start_row + i
    ws.cell(row=r, column=2, value=role).font = BLACK
    c = ws.cell(row=r, column=3, value=us_rate)
    c.font = BLUE
    c.number_format = CUR
    c.fill = openpyxl.styles.PatternFill("solid", fgColor="FFFFFF")
    c2 = ws.cell(row=r, column=4, value=in_rate)
    c2.font = BLUE
    c2.number_format = CUR
    c2.fill = openpyxl.styles.PatternFill("solid", fgColor="FFFFFF")
    c3 = ws.cell(row=r, column=5, value=f"=(C{r}-D{r})/C{r}")
    c3.font = BLACK
    c3.number_format = "0%"
    c3.alignment = Alignment(horizontal="center")
    ws.cell(row=r, column=6, value=note).font = NOTE_FONT
    style_row(ws, r, 2, 6)

india_col = 4  # column D on Rate Card holds India rates

rate_end = start_row + len(roles) - 1

# =========================================================
# Helper to build a track sheet
# =========================================================
def build_track_sheet(name, tab_color, team, hardware, phases, weeks_label, tasks, built_note=None):
    ws = wb.create_sheet(name)
    ws.sheet_properties.tabColor = tab_color
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 2
    ws.column_dimensions["B"].width = 32
    ws.column_dimensions["C"].width = 9
    ws.column_dimensions["D"].width = 11
    ws.column_dimensions["E"].width = 11
    ws.column_dimensions["F"].width = 12
    ws.column_dimensions["G"].width = 13
    ws.column_dimensions["H"].width = 14
    ws.column_dimensions["I"].width = 2
    ws.column_dimensions["J"].width = 13
    ws.column_dimensions["K"].width = 14

    ws["B2"] = f"{name} — Remaining Work Plan"
    ws["B2"].font = TITLE_FONT
    ws["B3"] = f"Target duration: {weeks_label}, fully parallelized workstreams, unlimited-resource staffing."
    ws["B3"].font = NOTE_FONT

    next_row = 5
    if built_note:
        full_note = "SCOPE NOTE (per direct clarification, 2026-08): " + built_note
        ws.merge_cells(f"B4:H4")
        ws["B4"] = full_note
        ws["B4"].font = Font(name=FONT_NAME, size=9, italic=True, color="7A4A00")
        ws["B4"].fill = PatternFill("solid", fgColor="FCEFD1")
        ws["B4"].alignment = Alignment(wrap_text=True, vertical="top", indent=1)
        # Merged width B:H is ~102 "characters" at this font/size; pad generously since
        # this heuristic is approximate and a clipped note is worse than empty space below it.
        chars_per_line = 95
        lines_needed = -(-len(full_note) // chars_per_line)  # ceil division
        ws.row_dimensions[4].height = max(28, (lines_needed + 1) * 14)
        next_row = 6

    # --- Team & People Costs ---
    section_header(ws, f"B{next_row}:H{next_row}", "Team & People Costs (Remaining Scope Only)")
    table_header(ws, next_row + 1, 2, ["Role", "Qty", "Hrs/Week", "Duration (Wks)", "Total Hours", "Hourly Rate", "Cost"])
    # Side-by-side India comparison columns — same roles/hours, India rate from the Rate Card.
    table_header(ws, next_row + 1, 10, ["India Rate", "India Cost"])

    r = next_row + 2
    people_first_row = r
    for role, qty, hrs_wk, dur_wk in team:
        ws.cell(row=r, column=2, value=role).font = BLACK
        cq = ws.cell(row=r, column=3, value=qty); cq.font = BLUE; cq.alignment = Alignment(horizontal="center")
        ch = ws.cell(row=r, column=4, value=hrs_wk); ch.font = BLUE; ch.alignment = Alignment(horizontal="center")
        cd = ws.cell(row=r, column=5, value=dur_wk); cd.font = BLUE; cd.alignment = Alignment(horizontal="center")
        cth = ws.cell(row=r, column=6, value=f"=C{r}*D{r}*E{r}")
        cth.font = BLACK; cth.alignment = Alignment(horizontal="center")
        crate = ws.cell(row=r, column=7,
                         value=f"=INDEX('Rate Card'!$C${start_row}:$C${rate_end},MATCH(B{r},'Rate Card'!$B${start_row}:$B${rate_end},0))")
        crate.font = GREEN; crate.number_format = CUR
        ccost = ws.cell(row=r, column=8, value=f"=F{r}*G{r}")
        ccost.font = BLACK; ccost.number_format = CUR
        style_row(ws, r, 2, 8)
        crate_in = ws.cell(row=r, column=10,
                            value=f"=INDEX('Rate Card'!$D${start_row}:$D${rate_end},MATCH(B{r},'Rate Card'!$B${start_row}:$B${rate_end},0))")
        crate_in.font = GREEN; crate_in.number_format = CUR
        ccost_in = ws.cell(row=r, column=11, value=f"=F{r}*J{r}")
        ccost_in.font = BLACK; ccost_in.number_format = CUR
        style_row(ws, r, 10, 11)
        r += 1
    people_last_row = r - 1

    people_total_row = r
    ws.cell(row=r, column=2, value="People Subtotal").font = BLACK_BOLD
    ws.cell(row=r, column=8, value=f"=SUM(H{people_first_row}:H{people_last_row})")
    ws.cell(row=r, column=8).font = BLACK_BOLD
    ws.cell(row=r, column=8).number_format = CUR
    style_row(ws, r, 2, 8, fill=TOTAL_FILL)
    ws.cell(row=r, column=2).fill = TOTAL_FILL
    ws.cell(row=r, column=11, value=f"=SUM(K{people_first_row}:K{people_last_row})")
    ws.cell(row=r, column=11).font = BLACK_BOLD
    ws.cell(row=r, column=11).number_format = CUR
    style_row(ws, r, 10, 11, fill=TOTAL_FILL)

    savings_row = people_total_row + 1
    ws.cell(row=savings_row, column=2, value="US vs. India Savings (People Only)").font = NOTE_FONT
    ws.cell(row=savings_row, column=8, value=f"=H{people_total_row}-K{people_total_row}")
    ws.cell(row=savings_row, column=8).font = NOTE_FONT
    ws.cell(row=savings_row, column=8).number_format = CUR
    ws.cell(row=savings_row, column=11, value=f"=(H{people_total_row}-K{people_total_row})/H{people_total_row}")
    ws.cell(row=savings_row, column=11).font = NOTE_FONT
    ws.cell(row=savings_row, column=11).number_format = "0%"

    # --- Hardware & Software ---
    hw_header_row = people_total_row + 3
    section_header(ws, f"B{hw_header_row}:H{hw_header_row}", "Hardware & Software (Build Phase)")
    table_header(ws, hw_header_row + 1, 2, ["Item", "", "Monthly Cost", "Months", "", "", "Cost"])
    ws.merge_cells(f"B{hw_header_row+1}:C{hw_header_row+1}")
    ws.merge_cells(f"D{hw_header_row+1}:E{hw_header_row+1}")
    ws.merge_cells(f"F{hw_header_row+1}:G{hw_header_row+1}")
    ws[f"H{hw_header_row+1}"] = "Cost"
    ws[f"H{hw_header_row+1}"].font = HEADER_FONT
    ws[f"H{hw_header_row+1}"].fill = HEADER_FILL
    ws[f"H{hw_header_row+1}"].alignment = Alignment(horizontal="center")
    ws[f"H{hw_header_row+1}"].border = BORDER

    r = hw_header_row + 2
    hw_first_row = r
    for item, monthly, months in hardware:
        ws.merge_cells(f"B{r}:C{r}")
        ws.cell(row=r, column=2, value=item).font = BLACK
        ws.merge_cells(f"D{r}:E{r}")
        cm = ws.cell(row=r, column=4, value=monthly); cm.font = BLUE; cm.number_format = CUR
        cm.alignment = Alignment(horizontal="center")
        ws.merge_cells(f"F{r}:G{r}")
        cmo = ws.cell(row=r, column=6, value=months); cmo.font = BLUE
        cmo.alignment = Alignment(horizontal="center")
        ccost = ws.cell(row=r, column=8, value=f"=D{r}*F{r}")
        ccost.font = BLACK; ccost.number_format = CUR
        for col in (2, 4, 6, 8):
            ws.cell(row=r, column=col).border = BORDER
        r += 1
    hw_last_row = r - 1

    hw_total_row = r
    ws.merge_cells(f"B{hw_total_row}:C{hw_total_row}")
    ws.cell(row=hw_total_row, column=2, value="Hardware/Software Subtotal").font = BLACK_BOLD
    ws.cell(row=hw_total_row, column=8, value=f"=SUM(H{hw_first_row}:H{hw_last_row})")
    ws.cell(row=hw_total_row, column=8).font = BLACK_BOLD
    ws.cell(row=hw_total_row, column=8).number_format = CUR
    for col in (2, 4, 6, 8):
        ws.cell(row=hw_total_row, column=col).fill = TOTAL_FILL
        ws.cell(row=hw_total_row, column=col).border = BORDER

    # Est. recurring monthly run cost post-launch
    run_row = hw_total_row + 1
    ws.merge_cells(f"B{run_row}:C{run_row}")
    ws.cell(row=run_row, column=2, value="Est. Recurring Monthly Cost Post-Launch").font = NOTE_FONT
    ws.cell(row=run_row, column=8, value=f"=SUM(D{hw_first_row}:D{hw_last_row})")
    ws.cell(row=run_row, column=8).font = NOTE_FONT
    ws.cell(row=run_row, column=8).number_format = CUR

    # --- Total Development Cost ---
    total_row = run_row + 2
    ws.merge_cells(f"B{total_row}:F{total_row}")
    ws.cell(row=total_row, column=2, value="TOTAL DEVELOPMENT COST").font = Font(name=FONT_NAME, size=12, bold=True, color="1F3D32")
    ws.cell(row=total_row, column=8, value=f"=H{people_total_row}+H{hw_total_row}")
    ws.cell(row=total_row, column=8).font = Font(name=FONT_NAME, size=12, bold=True, color="1F3D32")
    ws.cell(row=total_row, column=8).number_format = CUR
    for col in range(2, 9):
        ws.cell(row=total_row, column=col).fill = ASSUMPTION_FILL

    # --- Phase Timeline ---
    tl_header_row = total_row + 2
    section_header(ws, f"B{tl_header_row}:H{tl_header_row}", "Phase Timeline (Weeks, Parallel Workstreams)")
    table_header(ws, tl_header_row + 1, 2, ["Phase", "", "", "", "Start Wk", "End Wk", "Duration"])
    ws.merge_cells(f"B{tl_header_row+1}:E{tl_header_row+1}")

    r = tl_header_row + 2
    ph_first_row = r
    for phase, start_wk, end_wk in phases:
        ws.merge_cells(f"B{r}:E{r}")
        ws.cell(row=r, column=2, value=phase).font = BLACK
        cs = ws.cell(row=r, column=6, value=start_wk); cs.font = BLUE; cs.alignment = Alignment(horizontal="center")
        ce = ws.cell(row=r, column=7, value=end_wk); ce.font = BLUE; ce.alignment = Alignment(horizontal="center")
        cdur = ws.cell(row=r, column=8, value=f"=G{r}-F{r}+1")
        cdur.font = BLACK; cdur.alignment = Alignment(horizontal="center")
        for col in (2, 6, 7, 8):
            ws.cell(row=r, column=col).border = BORDER
        r += 1
    ph_last_row = r - 1

    dur_row = r
    ws.merge_cells(f"B{dur_row}:E{dur_row}")
    ws.cell(row=dur_row, column=2, value="Track Duration (Weeks)").font = BLACK_BOLD
    ws.cell(row=dur_row, column=8, value=f"=MAX(G{ph_first_row}:G{ph_last_row})")
    ws.cell(row=dur_row, column=8).font = BLACK_BOLD
    for col in (2, 6, 7, 8):
        ws.cell(row=dur_row, column=col).fill = TOTAL_FILL
        ws.cell(row=dur_row, column=col).border = BORDER

    # --- Task Breakdown: Technology & Hardware ---
    task_header_row = dur_row + 2
    section_header(ws, f"B{task_header_row}:H{task_header_row}", "Task Breakdown — Technology & Hardware")
    table_header(ws, task_header_row + 1, 2, ["Task", "", "Technology / Tools", "", "", "Hardware", ""])
    ws.merge_cells(f"B{task_header_row+1}:C{task_header_row+1}")
    ws.merge_cells(f"D{task_header_row+1}:F{task_header_row+1}")
    ws.merge_cells(f"G{task_header_row+1}:H{task_header_row+1}")

    r = task_header_row + 2
    for task, tech, hw in tasks:
        ws.merge_cells(f"B{r}:C{r}")
        c = ws.cell(row=r, column=2, value=task)
        c.font = BLACK_BOLD
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.merge_cells(f"D{r}:F{r}")
        c = ws.cell(row=r, column=4, value=tech)
        c.font = BLACK
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.merge_cells(f"G{r}:H{r}")
        c = ws.cell(row=r, column=7, value=hw)
        c.font = BLACK
        c.alignment = Alignment(wrap_text=True, vertical="top")
        for col in (2, 4, 7):
            ws.cell(row=r, column=col).border = BORDER
        ws.row_dimensions[r].height = 42
        r += 1

    return {
        "people_total_cell": f"'{name}'!H{people_total_row}",
        "india_people_total_cell": f"'{name}'!K{people_total_row}",
        "hw_total_cell": f"'{name}'!H{hw_total_row}",
        "run_cost_cell": f"'{name}'!H{run_row}",
        "total_cell": f"'{name}'!H{total_row}",
        "duration_cell": f"'{name}'!H{dur_row}",
    }

# =========================================================
# SHEET: Azure Migration (NEW — shared platform foundation)
# =========================================================
az_team = [
    ("Delivery Lead / TPM", 1, 40, 3),
    ("DevOps / Cloud Engineer", 1, 40, 3),
    ("Senior Backend Engineer", 1, 40, 3),
    ("Security Consultant", 1, 40, 1),
    ("QA Engineer", 1, 40, 2),
]
az_hardware = [
    ("Azure App Service Plan (Premium P2v3, 2 instances)", 500, 1),
    ("Azure Database for PostgreSQL Flexible Server (General Purpose, w/ PostGIS)", 600, 1),
    ("Azure Blob Storage (Hot LRS, project files)", 100, 1),
    ("Application Gateway capacity increment (reuse existing appgw_aptus_southcentralus, WAF_v2)", 60, 1),
    ("CDN endpoint on existing cdn-priusintelli profile (usage-based, no fixed minimum)", 0, 1),
    ("Azure Application Insights (monitoring, linked to existing la-pi-aptus workspace)", 100, 1),
]
az_phases = [
    ("Provision Azure Infrastructure (App Service, Postgres Flexible Server, Blob — joins existing VNet)", 1, 1),
    ("Deploy Database Schema (Prisma migrate, enable PostGIS) & Configure Blob Storage", 1, 2),
    ("Reconfigure Integrations (Stripe webhooks, Resend, NextAuth URLs) & Secrets", 2, 2),
    ("DNS Cutover & Full Regression Testing", 2, 3),
]
az_tasks = [
    ("Provision core infrastructure", "Azure App Service, Bicep/Terraform IaC — joins existing vnet_pi_southcentralus", "App Service (Premium P2v3)"),
    ("Deploy database schema", "Prisma migrate deploy, PostGIS extension, seed test data", "Azure Database for PostgreSQL Flexible Server"),
    ("Configure file storage", "Azure Blob Storage SDK, SAS tokens", "Blob Storage (Hot LRS)"),
    ("Reconfigure integrations & secrets", "Stripe webhook re-registration, Resend domain verify, secrets in existing Key Vault", "kv-priusintelli-web (existing, reused)"),
    ("DNS cutover & custom domain", "New listener on existing Application Gateway; new endpoint on existing CDN profile; managed cert", "appgw_aptus_southcentralus (WAF_v2, existing), cdn-priusintelli (existing)"),
    ("Regression testing", "Playwright E2E suite (existing 20+ specs), Vitest", "Staging slot on new infra"),
]
az_refs = build_track_sheet(
    "Azure Migration", "4A8F8B", az_team, az_hardware, az_phases, "3 weeks", az_tasks,
    built_note=("N/A — this track is the migration itself. Current app runs on Vercel (us-east, iad1) per response "
                "headers; team's own deployment docs target Railway for production. CONFIRMED with the team: no "
                "production-level data exists in the Railway Postgres DB today, so this is a schema-only deploy onto "
                "fresh Azure infrastructure, not a live customer-data migration/cutover — lower risk and lighter "
                "DevOps effort than a true production migration would need. REUSE SCAN (2026-08, live subscription): "
                "joins the existing vnet_pi_southcentralus VNet rather than building a new one. WAF/edge reuses the "
                "existing appgw_aptus_southcentralus Application Gateway (WAF_v2) with a new Mercator listener "
                "instead of standing up Azure Front Door — modeled as a capacity increment ($60/mo) instead of a "
                "full $250/mo Front Door+WAF profile; trade-off is no Front-Door-style global edge caching. CDN "
                "reuses the existing cdn-priusintelli profile via a new endpoint — usage-based, no fixed monthly "
                "minimum, so modeled at $0. Key Vault reuses the existing kv-priusintelli-web vault, removing that "
                "line item entirely. App Insights links to the existing la-pi-aptus Log Analytics workspace (same "
                "modeled cost — this saves setup effort, not $/mo). NOT reused: the App Service Plan (existing "
                "asp-dev1/asp-prod1 are Basic tier, no deployment slots or autoscale — too small for production) "
                "and the Postgres Flexible Server (existing pi-pgsql-prod/dev are Burstable B1ms already shared by "
                "wikijs and Aptus OMS — a dedicated server is recommended over adding contention risk to that "
                "shared box, though adding a 'mercator' database there remains a lower-cost fallback if budget "
                "pressure requires it). Blob Storage could technically live in the existing pigisstorage4361 "
                "account (already has a Private Endpoint and a 'customer delivery' container) — kept as a separate "
                "line since storage cost scales with data volume regardless of account, but flagging: that "
                "account's existing 'sharing'/'research' containers use PUBLIC blob access, which does not meet "
                "the SAS-scoped, per-tenant-isolated bar this plan requires — don't replicate that config."),
)

# =========================================================
# SHEET: Order Management (remaining gaps only)
# =========================================================
om_team = [
    ("Delivery Lead / TPM", 1, 40, 8),
    ("Senior Backend Engineer", 1, 40, 4),
    ("Business / Systems Analyst", 1, 40, 3),
    ("Senior Backend Engineer", 1, 40, 3),
    ("Senior Backend Engineer", 1, 40, 2),
    ("GIS / Geospatial Engineer", 1, 40, 7),
    ("DevOps / Cloud Engineer", 1, 40, 2),
    ("QA Engineer", 1, 40, 4),
    ("Security Consultant", 1, 20, 1),
]
om_hardware = [
    ("Azure API Management (Standard tier) — new public API layer", 700, 2),
    ("Azure Data Factory (data consolidation pipeline)", 300, 2),
]
om_phases = [
    ("Build: Data Consolidation Pipeline (pull pipeline/DevOps data in)", 1, 3),
    ("Build: Public API & Partner Integration Layer (none exists today)", 2, 4),
    ("Complete Payment Processing (checkout, webhooks, confirmation)", 1, 2),
    ("Automated Quoting: Define Pricing Logic & Build", 1, 4),
    ("Automated Flight Planning: Geospatial Engine, Iterative Build & Validation", 1, 8),
    ("Regression & Integration Testing", 7, 8),
]
om_tasks = [
    ("Data consolidation pipeline", "Azure Data Factory, Python, SQL, tRPC ingestion routes", "Azure Data Factory"),
    ("Public API & partner integration layer", "Azure API Management, API keys/OAuth2, OpenAPI spec", "Azure API Management (Standard)"),
    ("Complete payment processing", "Stripe Checkout/Payment Intents integration, webhook handling, payment-confirmation flow via Resend email", "Stripe (existing), Resend (existing) — no new Azure service"),
    ("Automated quoting — define & build", "Requirements analysis of current pricing logic, then a Node/tRPC rules engine to automate it", "None (runs on existing App Service)"),
    ("Automated flight planning — geospatial engine", "Custom geospatial algorithm (coverage/overlap/altitude), Python/Turf.js, iterative validation against real flight data", "Compute on existing App Service; no new Azure service"),
    ("Security review of new public API", "Auth/rate-limit review, penetration spot-check", "None additional"),
    ("Regression testing", "Playwright/Vitest existing suite + new API/quoting/flight-plan/payment tests", "Staging slot"),
]
om_refs = build_track_sheet(
    "Order Management", "1F3D32", om_team, om_hardware, om_phases, "8 weeks", om_tasks,
    built_note=("Order Management is NOT complete. Customer self-service portal and project visibility are built "
                "and working (Epics 2, 3, 5, 6); Stripe-backed payment processing is wired in but not fully working "
                "end-to-end and needs completion before customers can reliably pay online. Per direct clarification, "
                "two substantial capabilities were missing from this model entirely: Automated Quoting — its "
                "pricing logic must be fully defined and validated before it can be automated — and Automated "
                "Flight Planning, a heavily variable-dependent geospatial capability expected to need several "
                "build/validation iterations before it's production-ready (flagged as the highest-uncertainty item "
                "in this whole plan — treat its 7-week estimate as a floor, not a ceiling). Also still missing: a "
                "data consolidation pipeline and a public/partner API layer (confirmed absent, no API-key or "
                "integrations UI exists anywhere in Settings)."),
)

# =========================================================
# SHEET: Data Portal (remaining gaps only)
# =========================================================
dp_team = [
    ("Delivery Lead / TPM", 1, 40, 5),
    ("Senior Backend Engineer", 1, 40, 5),
    ("Senior Frontend Engineer", 1, 40, 2),
    ("GIS / Geospatial Engineer", 1, 40, 2),
    ("DevOps / Cloud Engineer", 1, 40, 4),
    ("Data Engineer", 1, 40, 3),
    ("Security Consultant", 1, 20, 1),
    ("QA Engineer", 1, 40, 3),
]
dp_hardware = [
    ("CARTO basemap API subscription", 50, 1),
    ("Azure Private Endpoint (secure AI-tool access to Blob, no public egress)", 30, 1.5),
    ("Azure Defender for Storage (malware scanning on customer uploads)", 40, 1.5),
]
dp_phases = [
    ("Build: Customer Upload & Download Wired to Azure Blob Storage (incl. fast-transfer tooling)", 1, 3),
    ("Build: Data Visualization & Download UI (browse Blob storage, download finished files)", 2, 4),
    ("Build: Secure Azure-Native Egress Path for AI Tool Access (Private Endpoint, data cataloging)", 2, 5),
    ("Data Security Hardening (encryption, scoped SAS, malware scanning, RBAC)", 3, 5),
    ("Regression & Security Testing", 4, 5),
]
dp_tasks = [
    ("Customer upload & download to Blob (fast transfer)", "Azure Blob SDK parallel block transfer; AzCopy for bulk/CLI-driven transfers; resumable multipart upload for large files", "Azure Blob Storage (shared, from Azure Migration)"),
    ("Data visualization & download UI", "Portal view listing each project's files in Blob storage, with preview and one-click download via short-lived SAS links", "Azure Blob Storage (shared, list + SAS generation)"),
    ("Azure-native AI-tool egress path", "Azure Private Endpoint + VNet integration (keeps traffic off the public internet), metadata cataloging for AI consumption", "Private Endpoint, Blob Storage (shared)"),
    ("Data security hardening", "SSE encryption at rest (default) + TLS in transit; short-lived scoped SAS tokens; Azure AD RBAC for internal access; per-tenant container isolation", "Azure Defender for Storage, Key Vault (shared)"),
    ("Regression & security testing", "Playwright existing map/file specs + upload/egress/download penetration spot-check", "Staging slot"),
]
dp_refs = build_track_sheet(
    "Data Portal", "E3B23C", dp_team, dp_hardware, dp_phases, "5 weeks", dp_tasks,
    built_note=("Data Portal is NOT complete. Project inventory, file management (KML/KMZ/Shapefile/GeoJSON up to "
                "100MB), and map visualization are built (Epics 3, 4, 8) — but per direct clarification, the portal "
                "still needs to be properly attached to Azure Blob Storage with full customer upload AND download, "
                "plus the customer-facing ability to actually visualize and download what's sitting in Blob storage "
                "(nothing exists today beyond raw file storage), and a secure Azure-native egress path so AI tools "
                "can process the data inside Azure rather than round-tripping over the public internet. Fast bulk "
                "transfer to/from Blob uses AzCopy plus parallel block transfer via the Blob SDK — no separate Data "
                "Box needed at this data volume. Data security is layered: encryption at rest and in transit, "
                "short-lived scoped SAS tokens, Private Endpoint/VNet isolation for AI-tool access, per-tenant "
                "container isolation, and Defender for Storage malware scanning on every customer upload."),
)

# =========================================================
# SHEET: Business Intelligence (remaining gaps only)
# =========================================================
bi_team = [
    ("Delivery Lead / TPM", 1, 40, 8),
    ("Data Engineer", 2, 40, 6),
    ("Analytics Engineer", 1, 40, 6),
    ("BI Developer", 1, 40, 5),
    ("Data Scientist", 1, 40, 5),
    ("QA Engineer", 1, 40, 3),
]
bi_hardware = [
    ("Azure ML workspace + training compute (forecasting)", 500, 2),
]
bi_phases = [
    ("Design: Decision-Support, Revenue & Cost-Allocation Data Model", 1, 2),
    ("Build: Real Decision-Support Views & Revenue Visibility (beyond basic KPI display)", 2, 6),
    ("Build: Cost Allocation Engine", 2, 6),
    ("Build: Forecasting Models", 3, 7),
    ("Integrate into Existing Dashboard & UAT", 7, 8),
]
bi_tasks = [
    ("Design decision-support & revenue data model", "Dimensional data modeling on existing Postgres schema", "None (design phase)"),
    ("Real decision-support & revenue-visibility views", "Analytics Engineer semantic layer + BI Developer report/dashboard build (replaces today's basic stat cards)", "Existing App Service (shared)"),
    ("Cost allocation engine", "SQL/tRPC procedures against existing order/company data", "Existing Postgres (shared)"),
    ("Forecasting models", "Azure ML, Python (scikit-learn/Prophet)", "Azure ML workspace + training compute"),
    ("Integrate into existing dashboard", "Extend existing internal dashboard components (Epic 7.6)", "Existing App Service (shared)"),
    ("Validation & UAT", "Manual reconciliation against known figures", "None additional"),
]
bi_refs = build_track_sheet(
    "Business Intelligence", "1E6F5C", bi_team, bi_hardware, bi_phases, "8 weeks", bi_tasks,
    built_note=("Business Intelligence is NOT built. Per direct clarification, only consolidation of internal data "
                "is accomplished today — the existing internal dashboard (Epic 7.6) pulls order/project/company "
                "data into basic stat cards and a pie chart, but this is data display, not genuine decision support "
                "or revenue visibility (the live app's own Revenue stat showed $0 with no real financial modeling "
                "behind it). This plan now treats decision support, revenue visibility, cost allocation, and "
                "forecasting as all still needing to be built — a materially larger scope than \"add forecasting on "
                "top of a working BI dashboard.\""),
)

# =========================================================
# SHEET: Summary
# =========================================================
sm = wb.create_sheet("Summary", 0)
sm.sheet_view.showGridLines = False
sm.column_dimensions["A"].width = 2
sm.column_dimensions["B"].width = 26
sm.column_dimensions["C"].width = 14
sm.column_dimensions["D"].width = 16
sm.column_dimensions["E"].width = 18
sm.column_dimensions["F"].width = 16
sm.column_dimensions["G"].width = 20

sm["B2"] = "Mercator — Azure Migration, OMS, Data Portal & BI Cost Summary"
sm["B2"].font = TITLE_FONT

sm["B4"] = ("REVISED 2026-08 after direct clarification on the existing app (mercator-gold.vercel.app): Order "
            "Management, Data Portal, and Business Intelligence are each NOT complete — the earlier \"mostly built\" "
            "read from the initial audit undercounted real scope in every track (see each tab's note for what's "
            "confirmed absent vs. present). Order Management is missing automated quoting (pricing logic must be "
            "fully defined and validated before it can be automated) and automated flight-plan generation (a "
            "heavily variable-dependent geospatial capability needing several build/validation iterations — the "
            "highest-uncertainty item in this plan); its Stripe-backed payment processing is also wired in but not "
            "fully working end-to-end and needs completion. Data Portal has no object storage at all today; it "
            "needs Azure Blob Storage wired in for customer upload/download, plus the customer-facing ability to "
            "visualize and download what's in Blob storage, plus secure in-Azure egress to AI tooling — with "
            "fast-transfer and data-security technology detailed on that tab. Business Intelligence is not built "
            "beyond consolidating internal data for display — no real decision support, revenue visibility, cost "
            "allocation, or forecasting exists yet. This model also includes a new Azure Migration track — the app "
            "runs on Vercel (us-east) today with a Railway-targeted production deploy guide; this migrates it onto "
            "Azure to sit alongside the rest of Prius Intelli's infrastructure. AI Workbench remains excluded and "
            "remains fully unbuilt (confirmed: /ai-tools is an explicit \"coming soon\" placeholder). Brief is "
            "unchanged: fastest achievable delivery, unlimited budget, all tracks staffed and run fully in "
            "parallel. Program timeline is the LONGEST single track, not a sum. See each tab for team, "
            "hardware/software, phase, and task detail; Rate Card tab for role rates.")
sm["B4"].font = NOTE_FONT
sm["B4"].alignment = Alignment(wrap_text=True, vertical="top")
sm.merge_cells("B4:G4")
_sm_note_lines = -(-len(sm["B4"].value) // 105)  # ceil division; merged B:G is ~105 "characters" wide
sm.row_dimensions[4].height = (_sm_note_lines + 1) * 14

section_header(sm, "B6:G6", "Cost & Timeline by Track")
table_header(sm, 7, 2, ["Track", "Duration (Wks)", "People Cost", "Hardware/Software", "Total Dev. Cost", "Post-Launch Monthly"])

tracks_summary = [
    ("Azure Migration", az_refs),
    ("Order Management", om_refs),
    ("Data Portal", dp_refs),
    ("Business Intelligence", bi_refs),
]
r = 8
first_row = r
for label, refs in tracks_summary:
    sm.cell(row=r, column=2, value=label).font = BLACK
    c = sm.cell(row=r, column=3, value=f"={refs['duration_cell']}"); c.font = GREEN; c.alignment = Alignment(horizontal="center")
    c = sm.cell(row=r, column=4, value=f"={refs['people_total_cell']}"); c.font = GREEN; c.number_format = CUR
    c = sm.cell(row=r, column=5, value=f"={refs['hw_total_cell']}"); c.font = GREEN; c.number_format = CUR
    c = sm.cell(row=r, column=6, value=f"={refs['total_cell']}"); c.font = GREEN_BOLD; c.number_format = CUR
    c = sm.cell(row=r, column=7, value=f"={refs['run_cost_cell']}"); c.font = GREEN; c.number_format = CUR
    style_row(sm, r, 2, 7)
    r += 1
last_row = r - 1

total_row = r
sm.cell(row=total_row, column=2, value="Combined Total").font = BLACK_BOLD
sm.cell(row=total_row, column=3, value=f"=MAX(C{first_row}:C{last_row})")
sm.cell(row=total_row, column=3).font = BLACK_BOLD
sm.cell(row=total_row, column=3).alignment = Alignment(horizontal="center")
sm.cell(row=total_row, column=4, value=f"=SUM(D{first_row}:D{last_row})")
sm.cell(row=total_row, column=5, value=f"=SUM(E{first_row}:E{last_row})")
sm.cell(row=total_row, column=6, value=f"=SUM(F{first_row}:F{last_row})")
sm.cell(row=total_row, column=7, value=f"=SUM(G{first_row}:G{last_row})")
for col in (4, 5, 6, 7):
    sm.cell(row=total_row, column=col).font = BLACK_BOLD
    sm.cell(row=total_row, column=col).number_format = CUR
for col in range(2, 8):
    sm.cell(row=total_row, column=col).fill = TOTAL_FILL
    sm.cell(row=total_row, column=col).border = BORDER

note_row = total_row + 1
sm.cell(row=note_row, column=2, value="Note: Duration shown is the longest track (parallel program), not a sum of weeks.").font = NOTE_FONT
sm.merge_cells(f"B{note_row}:G{note_row}")

prog_row = total_row + 3
sm.merge_cells(f"B{prog_row}:E{prog_row}")
sm.cell(row=prog_row, column=2, value="PROGRAM TIMELINE (fastest possible, all tracks parallel)").font = Font(name=FONT_NAME, size=12, bold=True, color="1F3D32")
sm.cell(row=prog_row, column=6, value=f"=MAX(C{first_row}:C{last_row})&\" weeks\"")
sm.cell(row=prog_row, column=6).font = Font(name=FONT_NAME, size=12, bold=True, color="1F3D32")
for col in range(2, 8):
    sm.cell(row=prog_row, column=col).fill = ASSUMPTION_FILL

cost_row = prog_row + 1
sm.merge_cells(f"B{cost_row}:E{cost_row}")
sm.cell(row=cost_row, column=2, value="PROGRAM TOTAL DEVELOPMENT COST").font = Font(name=FONT_NAME, size=12, bold=True, color="1F3D32")
sm.cell(row=cost_row, column=6, value=f"=F{total_row}")
sm.cell(row=cost_row, column=6).font = Font(name=FONT_NAME, size=12, bold=True, color="1F3D32")
sm.cell(row=cost_row, column=6).number_format = CUR
for col in range(2, 8):
    sm.cell(row=cost_row, column=col).fill = ASSUMPTION_FILL

# =========================================================
# Summary: US vs. India Location Comparison
# =========================================================
india_header_row = cost_row + 3
section_header(sm, f"B{india_header_row}:G{india_header_row}", "Location Comparison — US vs. India Delivery")
sm["B" + str(india_header_row + 1)] = ("Same roles, hours, and hardware — only the delivery location's labor rate changes (Rate "
            "Card tab). Cloud infrastructure cost is identical regardless of team location, so only the People "
            "portion of each track's cost shifts. This compares fully-onshore delivery to a fully-offshore India "
            "team; a blended/hybrid model would land between the two columns.")
sm["B" + str(india_header_row + 1)].font = NOTE_FONT
sm["B" + str(india_header_row + 1)].alignment = Alignment(wrap_text=True, vertical="top")
sm.merge_cells(f"B{india_header_row+1}:G{india_header_row+1}")
sm.row_dimensions[india_header_row + 1].height = 42

table_header(sm, india_header_row + 3, 2, ["Track", "US Total Cost", "India Total Cost", "Savings ($)", "Savings (%)"])

r = india_header_row + 4
india_first_row = r
for label, refs in tracks_summary:
    sm.cell(row=r, column=2, value=label).font = BLACK
    c = sm.cell(row=r, column=3, value=f"={refs['total_cell']}"); c.font = GREEN; c.number_format = CUR
    c = sm.cell(row=r, column=4, value=f"={refs['india_people_total_cell']}+{refs['hw_total_cell']}"); c.font = GREEN; c.number_format = CUR
    c = sm.cell(row=r, column=5, value=f"=C{r}-D{r}"); c.font = BLACK; c.number_format = CUR
    c = sm.cell(row=r, column=6, value=f"=E{r}/C{r}"); c.font = BLACK; c.number_format = "0%"
    style_row(sm, r, 2, 6)
    r += 1
india_last_row = r - 1

india_total_row = r
sm.cell(row=india_total_row, column=2, value="Program Total").font = BLACK_BOLD
sm.cell(row=india_total_row, column=3, value=f"=SUM(C{india_first_row}:C{india_last_row})")
sm.cell(row=india_total_row, column=4, value=f"=SUM(D{india_first_row}:D{india_last_row})")
sm.cell(row=india_total_row, column=5, value=f"=SUM(E{india_first_row}:E{india_last_row})")
sm.cell(row=india_total_row, column=6, value=f"=E{india_total_row}/C{india_total_row}")
for col in (3, 4, 5):
    sm.cell(row=india_total_row, column=col).font = BLACK_BOLD
    sm.cell(row=india_total_row, column=col).number_format = CUR
sm.cell(row=india_total_row, column=6).font = BLACK_BOLD
sm.cell(row=india_total_row, column=6).number_format = "0%"
for col in range(2, 7):
    sm.cell(row=india_total_row, column=col).fill = TOTAL_FILL
    sm.cell(row=india_total_row, column=col).border = BORDER

india_savings_row = india_total_row + 2
sm.merge_cells(f"B{india_savings_row}:D{india_savings_row}")
sm.cell(row=india_savings_row, column=2, value="TOTAL PROGRAM SAVINGS — INDIA DELIVERY").font = Font(name=FONT_NAME, size=12, bold=True, color="1F3D32")
sm.cell(row=india_savings_row, column=6, value=f"=TEXT(E{india_total_row},\"$#,##0\")&\" (\"&TEXT(F{india_total_row},\"0%\")&\")\"")
sm.cell(row=india_savings_row, column=6).font = Font(name=FONT_NAME, size=12, bold=True, color="1F3D32")
for col in range(2, 7):
    sm.cell(row=india_savings_row, column=col).fill = ASSUMPTION_FILL

wb.save(r"C:\Users\pi\claude\mercator_cost_model\Mercator_OMS_DataPortal_BI_Cost_Model.xlsx")
print("saved")
