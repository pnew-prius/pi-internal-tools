const {
  NAVY, TEAL, AMBER, MUTED, PageBreak,
  docTitle, statRow, h1, h2, h3sub, body, bullet, note,
  compareTable, equipmentTable, buildDocument, writeDoc,
} = require("./docx_helpers");
const { Paragraph } = require("docx");

const children = [
  ...docTitle(
    "Quarterly Permian Collection",
    "Costs & Timelines",
    "13 September 2026",
    "Scope",
    "Steady-state operation over the Permian AOI — collected & delivered quarterly. Recurring costs and turnaround times only; no one-time build costs included."
  ),

  statRow([
    { number: "~$6,830–6,990/mo", label: "Recurring cloud operating cost", color: NAVY },
    { number: "~16.3–27.4 h", label: "Wheels-up to delivery-ready (150 MP, one day, winter–summer range)", color: TEAL },
    { number: "3", label: "Pipeline legs — Collection, FBO, Cloud", color: MUTED },
  ]),

  h2("Key Notes", NAVY),
  bullet("All figures below are steady-state recurring costs and turnaround times — no one-time build or equipment costs are included."),
  bullet("The ~$6,830–6,990/month recurring figure is scoped to this project's AOI, collected and delivered quarterly."),
  bullet("Cloud figures reflect real, current metered rates; flight-collection figures reflect real internal flight-planning estimates."),
  bullet("Collection time and processing volume are broken out by winter and summer throughout this document — the usable flying window differs by season, so daily collection volume does too, and processing runs alongside collection."),
  bullet("This document covers both 10 cm and 7.5 cm resolution, in two parallel blocks (Sections 1–6 and 8–13) — don't compare figures across the two resolutions, they cover different image-volume bases."),
  bullet("Section 6 (10 cm) and Section 13 (7.5 cm) each combine flight collection, cloud recurring, and processing cost into one whole-quarter total, by camera and season."),

  new Paragraph({ spacing: { before: 260 }, children: [] }),

  h2("10 cm Resolution", NAVY),
  body("Sections 1–6 below cover 10 cm resolution, matching the real image-volume basis (215,000 / 135,000 images) used throughout this document. FBO to Cloud recurring cost (Section 1) is the exception — it doesn't depend on resolution."),

  h1("1", "Recurring Operating Cost (10 cm)"),
  body("Monthly cost to run the finished pipeline, by leg. Collection to FBO carries no standing infrastructure cost of its own — its recurring cost is the flight operation itself, covered in Section 2. Itemized detail behind these totals is in Appendix A."),
  compareTable(
    ["Leg", "Recurring"],
    [
      ["1 · FBO to Cloud", "$1,460/mo"],
      ["2 · Cloud to Delivery", "~$5,370–5,530/mo*"],
      ["Total", "~$6,830–6,990/mo*"],
    ],
    [4680, 4680]
  ),
  note("*Cloud to Delivery recurring cost includes a derived estimate for image conversion (~$409–566/mo on the 150 MP camera) alongside current metered rates for a shared-tenant workload; see Appendix A.2 and A.3."),

  h1("2", "Collection Time & Cost, by Fleet Configuration (10 cm)"),
  body("Real internal flight-planning estimates at 10 cm resolution. This is flight operations cost (aircraft, crew, fuel) to physically collect the AOI — a different cost category from the cloud recurring cost in Section 1. PAS150 = the current 150 MP camera; RS250 = the 250 MP camera discussed throughout this document."),
  compareTable(
    ["Configuration", "Hours", "Winter days", "Summer days", "Winter cost", "Summer cost"],
    [
      ["1× PAS150 (current)", "425", "107", "63", "$176,055", "$165,582"],
      ["1× RS250", "321", "81", "48", "$133,528", "$125,867"],
      ["1× PAS150 + 1× RS250", "183", "46", "28", "$152,830", "$145,415"],
      ["2× RS250", "161", "41", "24", "$135,346", "$127,076"],
      ["1× PAS150 + 2× RS250", "117", "30", "18", "$148,349", "$140,415"],
      ["3× RS250", "107", "27", "16", "$135,488", "$127,827"],
      ["4× RS250", "81", "15", "12", "$140,028", "$129,614"],
    ],
    [2400, 1090, 1290, 1290, 1645, 1645]
  ),
  note("At 10 cm, a single RS250 already fits the quarter in both seasons (81 winter days, 48 summer — a 9-day winter margin), unlike at finer resolutions. PAS150 alone still fails winter (107 days) though it clears summer (63 days). The more useful finding: RS250 fleet cost is nearly flat from 1 to 3 aircraft (~$133,500–135,500 winter) — adding a second or third RS250 barely changes total cost, because total flight hours stay roughly the same, just split across more aircraft in parallel. Once RS250 is the chosen camera, fleet size becomes a schedule/margin decision, not a cost one — going from 1 to 2 aircraft roughly doubles collection speed (81→41 winter days) for about 1.4% more cost."),

  h1("3", "Process Time — One Collection Day, Winter vs. Summer (150 MP vs. 250 MP, 10 cm)"),
  body("One aircraft, one day of flying, using the 1× PAS150 and 1× RS250 rows from Section 2. Winter and summer fly different average hours/day (425 h ÷ 107 winter days ≈ 4.0 h vs. 425 h ÷ 63 summer days ≈ 6.7 h for the 150 MP camera; 321 h ÷ 81 and ÷ 48 for the 250 MP camera, both also ≈ 4.0 h / 6.7 h) — real figures from Section 2, not independently measured. Because processing runs alongside collection, a day's processing load tracks what that day collected: each downstream stage below is scaled from the real measured single-sortie baseline (3,171 images, 482 GB, 150 MP) by the ratio of that season's average daily image count to the baseline — not independently measured for winter or summer specifically. 250 MP figures additionally carry the 1.63× pixel-ratio extrapolation already used throughout this document. Processing cost combines real image-conversion and mosaic compute rates — see the note below the tables for how it's derived."),

  h3sub("150 MP"),
  compareTable(
    ["Stage", "Winter", "Summer"],
    [
      ["Collection (flight)", "~4.0 h", "~6.7 h"],
      ["Aircraft → FBO", "~8 min", "~8 min"],
      ["Images collected that day", "~2,010", "~3,410"],
      ["Upload to cloud (1 Gbps)", "~0.8–0.9 h (~306 GB)", "~1.4–1.5 h (~518 GB)"],
      ["Image conversion (parallel)", "~1.3 h", "~2.2 h"],
      ["Mosaic (parallel)", "~9.7 h", "~16.5 h"],
      ["GDAL merge/trim/COG (parallel)", "~0.3 h", "~0.5 h"],
      ["Publish to image server", "minutes", "minutes"],
      ["Total, wheels-up → delivery-ready", "~16.3 h", "~27.4 h"],
      ["Processing cost (conversion + mosaic)", "~$158–169", "~$269–287"],
    ],
    [3200, 3080, 3080]
  ),

  h3sub("250 MP"),
  compareTable(
    ["Stage", "Winter", "Summer"],
    [
      ["Collection (flight)", "~4.0 h", "~6.7 h"],
      ["Aircraft → FBO", "~8 min", "~8 min"],
      ["Images collected that day", "~1,670", "~2,810"],
      ["Upload to cloud (1 Gbps)", "~0.3–0.5 h (~94–185 GB)", "~0.4–0.9 h (~159–311 GB)"],
      ["Image conversion (parallel)", "~1.7 h", "~2.9 h"],
      ["Mosaic (parallel)", "~14.8 h", "~24.9 h"],
      ["GDAL merge/trim/COG (parallel)", "~0.4 h", "~0.7 h"],
      ["Publish to image server", "minutes", "minutes"],
      ["Total, wheels-up → delivery-ready", "~21.5 h", "~35.9 h"],
      ["Processing cost (conversion + mosaic)", "~$215–230", "~$361–386"],
    ],
    [3200, 3080, 3080]
  ),
  note("None of the four combinations reach same-calendar-day delivery. Summer's longer flying window means more images collected per day, so summer's processing backlog runs longer than winter's despite the same 22-VM parallel capacity — this is the same pixels-not-files effect already noted for the 150 vs. 250 MP comparison, now also running across seasons. Mosaic remains the bottleneck in every case (~55–60% of total time)."),
  note("Mosaic compute cost is derived from the real $1.316/hr rate (Standard_F16s_v2 compute at $0.816/hr + the $0.50/hr One-Button license, both real metered rates) divided by the real measured throughput (17.24–17.98 img/hr per head) = ~$0.073–0.076/image at 150 MP; scaled by the same 1.63× pixel ratio for 250 MP (~$0.119–0.124/image). GDAL compute isn't broken out per-image here — no measured GDAL throughput rate is established; it's folded into the Orthomosaic & file-finishing compute figure in Appendix A.2."),

  h1("4", "Volume Comparison — Whole Project and Daily (150 MP vs. 250 MP, 10 cm)"),
  body("Whole-project totals are fixed regardless of season — the same AOI needs the same total images either way. Daily volume varies by season because the usable flying window does (Section 2); since processing runs alongside collection, the volume processed on any given day tracks what was collected that day."),
  h3sub("Whole project"),
  compareTable(
    ["", "150 MP", "250 MP"],
    [
      ["Images, whole project (real)", "215,000", "135,000"],
      ["Total pixel volume (derived)", "~32,530 Gigapixels", "~33,345 Gigapixels"],
      ["Image-conversion cost, whole project", "$1,226–1,699", "$1,254–1,744 (extrapolated)"],
    ],
    [3760, 2800, 2800]
  ),
  note("Despite 135,000 images being 37% fewer than 215,000, total conversion cost comes out nearly identical (within ~2.5%) — because total pixel volume, which is what compute cost tracks, is almost the same either way. The 250 MP camera trades file count for per-file size; it doesn't reduce processing cost."),

  h3sub("Daily volume, by season"),
  compareTable(
    ["150 MP", "Winter", "Summer"],
    [
      ["Images/day", "~2,010", "~3,410"],
      ["Data/day", "~306 GB", "~518 GB"],
      ["Image-conversion cost/day", "~$11–16", "~$19–27"],
      ["Mosaic cost/day", "~$147–153", "~$250–260"],
      ["Total processing cost/day", "~$158–169", "~$269–287"],
    ],
    [3200, 3080, 3080]
  ),
  compareTable(
    ["250 MP", "Winter", "Summer"],
    [
      ["Images/day", "~1,670", "~2,810"],
      ["Data/day", "~94–185 GB", "~159–311 GB"],
      ["Image-conversion cost/day", "~$16–22", "~$26–36"],
      ["Mosaic cost/day", "~$199–208", "~$335–350"],
      ["Total processing cost/day", "~$215–230", "~$361–386"],
    ],
    [3200, 3080, 3080]
  ),
  note("Daily figures are derived by dividing each camera's real whole-project total (215,000 / 135,000 images) by its real winter/summer day count from Section 2 — not independently measured day by day. Mosaic cost/day uses the same per-image rate derived in Section 3's note (~$0.073–0.076/image at 150 MP, ~$0.119–0.124/image at 250 MP)."),

  h1("5", "Whole-AOI Batch Processing Time (22 parallel VMs, 10 cm)"),
  body("A different question from the daily turnaround above: if the entire AOI had to be mosaic-processed as one batch — e.g. catching up a backlog — how long would it take running the demonstrated 22-VM burst capacity flat out? Modeled using a real measured build as the throughput unit: cpd26-22-d6, 430 images in 23.92 hours (17.98 img/hr), the largest single real build on record. 150 MP uses that time as-is; 250 MP scales it by the same 1.63× pixel ratio used throughout this document — not independently measured."),
  compareTable(
    ["", "150 MP", "250 MP"],
    [
      ["AOI total", "215,000 images", "135,000 images"],
      ["Time per 430-image package", "23.92 h (measured)", "39.0 h (extrapolated)"],
      ["Packages needed", "500", "314"],
      ["Waves across 22 parallel VMs", "23", "15"],
      ["Total batch processing time", "~550 h (~22.9 days)", "~585 h (~24.4 days)"],
      ["Total compute cost (22 VMs, $1.316/hr each)", "~$15,700–15,900", "~$16,100–16,900"],
    ],
    [3760, 2800, 2800]
  ),
  note("250 MP again comes out slightly slower overall (~24.4 vs. ~22.9 days) despite 37% fewer images, for the same reason as the daily comparison: processing time tracks total pixels, not file count. A smoother cross-check using total compute-hours instead of discrete 22-wide waves gives ~22.6 days (150 MP) and ~23.2 days (250 MP) — the gap to the wave-based figures above is the wall-clock cost of each scenario's last, partial wave running under a full VM pool."),
  note("Compute cost is the same real $1.316/hr rate used in Sections 3–4 (Standard_F16s_v2 + One-Button license), applied to total VM-hours — packages needed × time per package. The range reflects the same wave-based vs. compute-hours cross-check as the time figures above; the gap is wider for 250 MP because its last wave has more unused VM slots (16 of 330) than 150 MP's (6 of 506)."),
  note("This figure doesn't vary by season — it's a fixed-volume, whole-AOI catch-up scenario, and total project volume (215,000 / 135,000 images) doesn't change with when it was collected. Season affects how long collection itself takes (Section 2) and how the daily processing load varies (Sections 3–4), not this total-reprocessing figure."),

  h1("6", "Whole Project Summary (10 cm)"),
  body("One quarter, all three cost categories combined: flight collection (Section 2, using the 1× PAS150 and 1× RS250 rows), cloud recurring cost for a 3-month quarter (Section 1 × 3), and whole-project processing cost (image conversion + mosaic, Sections 3–4). Processing cost is the same regardless of season — it's whole-project volume, which is fixed; only the flight collection cost changes between a winter and a summer quarter."),
  compareTable(
    ["", "Flight collection", "Recurring (3 mo)", "Processing", "Total"],
    [
      ["150 MP, winter quarter", "$176,055", "$20,490–20,970", "$16,964–18,104", "~$213,500–215,100"],
      ["150 MP, summer quarter", "$165,582", "$20,490–20,970", "$16,964–18,104", "~$203,000–204,700"],
      ["250 MP, winter quarter", "$133,528", "$20,490–20,970", "$17,365–18,538", "~$171,400–173,000"],
      ["250 MP, summer quarter", "$125,867", "$20,490–20,970", "$17,365–18,538", "~$163,700–165,400"],
    ],
    [2160, 2160, 2200, 2200, 1640]
  ),
  note("Flight collection cost is real (Section 2). Recurring cost is the real monthly rate (Section 1) × 3 months. Processing cost sums the real whole-project image-conversion figure (Section 4) and the derived whole-project mosaic figure (215,000 or 135,000 images × the per-image mosaic rate from Section 3's note). GDAL and delivery-infrastructure costs are not broken out separately — see Appendix A.2 for what's folded into the recurring figure. Fleet configuration is fixed at 1× PAS150 / 1× RS250 here; see Section 2 for other fleet sizes, which change flight collection cost but not recurring or processing cost."),

  h2("7.5 cm Resolution", NAVY),
  body("Sections 8–13 below mirror Sections 1–6 at 7.5 cm resolution, using the real image-volume basis (390,630 / 240,866 images) and real fleet-configuration data for this resolution. Per-image rates (conversion, mosaic) are resolution-independent — the camera sensor captures the same pixel count regardless of GSD — so the same real rates from the 10 cm block apply here, scaled by the 7.5 cm image totals."),

  h1("8", "Recurring Operating Cost (7.5 cm)"),
  body("Same structure as Section 1, recomputed for the 7.5 cm image-volume basis. FBO to Cloud is unchanged — it doesn't depend on resolution."),
  compareTable(
    ["Leg", "Recurring"],
    [
      ["1 · FBO to Cloud", "$1,460/mo"],
      ["2 · Cloud to Delivery", "~$5,705–5,991/mo*"],
      ["Total", "~$7,165–7,451/mo*"],
    ],
    [4680, 4680]
  ),
  note("*Cloud to Delivery recurring cost includes a derived estimate for image conversion (~$743–1,029/mo on the 150 MP camera) alongside the same current metered rates used in Section 1; see Appendix A.3. The 250 MP path runs ~$7,168–7,459/mo total — nearly identical, for the same pixel-volume-parity reason noted in Section 11."),

  h1("9", "Collection Time & Cost, by Fleet Configuration (7.5 cm)"),
  body("Real internal flight-planning estimates at 7.5 cm resolution — the finer resolution needs more flight hours per configuration than the matching 10 cm row, since more images (and more flight coverage) are needed for the same AOI."),
  compareTable(
    ["Configuration", "Hours", "Winter days", "Summer days", "Winter cost", "Summer cost"],
    [
      ["1× PAS150 (current)", "576", "144", "86", "$237,786", "$224,745"],
      ["1× RS250", "427", "107", "64", "$176,744", "$167,138"],
      ["1× PAS150 + 1× RS250", "246", "62", "37", "$204,948", "$193,671"],
      ["2× RS250", "214", "54", "32", "$178,630", "$168,416"],
      ["1× PAS150 + 2× RS250", "156", "39", "24", "$195,480", "$186,729"],
      ["3× RS250", "143", "36", "22", "$179,899", "$171,420"],
      ["4× RS250", "107", "27", "16", "$180,650", "$170,436"],
    ],
    [2400, 1090, 1290, 1290, 1645, 1645]
  ),
  note("At 7.5 cm, a single RS250 no longer fits a winter quarter on its own (107 days) — matching or exceeding a typical quarter's length — where at 10 cm it comfortably did (81 days). Multiple RS250 aircraft are needed to reliably clear a winter quarter at this resolution. PAS150 alone is further out of reach (144 winter days)."),

  h1("10", "Process Time — One Collection Day, Winter vs. Summer (150 MP vs. 250 MP, 7.5 cm)"),
  body("Same method as Section 3: winter/summer flying hours/day from Section 9's real hours and day counts (576 h ÷ 144 / ÷ 86 for 150 MP ≈ 4.0 h / 6.7 h; 427 h ÷ 107 / ÷ 64 for 250 MP ≈ 4.0 h / 6.7 h — matching the 10 cm block's hours/day almost exactly, since the daylight/sun-angle constraint is physical, not resolution-dependent). Each downstream stage is scaled from the same real single-sortie baseline (3,171 images, 482 GB, 150 MP) by that season's daily image-volume ratio at this resolution."),

  h3sub("150 MP"),
  compareTable(
    ["Stage", "Winter", "Summer"],
    [
      ["Collection (flight)", "~4.0 h", "~6.7 h"],
      ["Aircraft → FBO", "~8 min", "~8 min"],
      ["Images collected that day", "~2,710", "~4,540"],
      ["Upload to cloud (1 Gbps)", "~1.1–1.2 h (~412 GB)", "~1.9–2.0 h (~690 GB)"],
      ["Image conversion (parallel)", "~1.7 h", "~2.9 h"],
      ["Mosaic (parallel)", "~13.1 h", "~21.9 h"],
      ["GDAL merge/trim/COG (parallel)", "~0.4 h", "~0.7 h"],
      ["Publish to image server", "minutes", "minutes"],
      ["Total, wheels-up → delivery-ready", "~20.5 h", "~36.3 h"],
      ["Processing cost (conversion + mosaic)", "~$214–228", "~$358–382"],
    ],
    [3200, 3080, 3080]
  ),

  h3sub("250 MP"),
  compareTable(
    ["Stage", "Winter", "Summer"],
    [
      ["Collection (flight)", "~4.0 h", "~6.7 h"],
      ["Aircraft → FBO", "~8 min", "~8 min"],
      ["Images collected that day", "~2,250", "~3,760"],
      ["Upload to cloud (1 Gbps)", "~0.3–0.7 h (~127–249 GB)", "~0.6–1.2 h (~213–416 GB)"],
      ["Image conversion (parallel)", "~2.3 h", "~3.9 h"],
      ["Mosaic (parallel)", "~19.9 h", "~33.3 h"],
      ["GDAL merge/trim/COG (parallel)", "~0.6 h", "~1.0 h"],
      ["Publish to image server", "minutes", "minutes"],
      ["Total, wheels-up → delivery-ready", "~27.5 h", "~45.8 h"],
      ["Processing cost (conversion + mosaic)", "~$289–309", "~$484–517"],
    ],
    [3200, 3080, 3080]
  ),
  note("Every 7.5 cm combination runs longer than its 10 cm counterpart — more images are collected per day at the finer resolution, so processing has more to work through. Summer 250 MP is the longest of all eight winter/summer × resolution × camera combinations in this document (~45.8 h) — still not same-calendar-day, same as every other combination."),
  note("Per-image rates are the same real ones established in Section 3 (conversion ~$0.0057–0.0079/image at 150 MP, ~$0.0093–0.0129/image at 250 MP; mosaic ~$0.0732–0.0763/image at 150 MP, ~$0.1193–0.1244/image at 250 MP) — resolution doesn't change per-image cost, only how many images there are."),

  h1("11", "Volume Comparison — Whole Project and Daily (150 MP vs. 250 MP, 7.5 cm)"),
  body("Same structure as Section 4, at the 7.5 cm image-volume basis (390,630 / 240,866 images)."),
  h3sub("Whole project"),
  compareTable(
    ["", "150 MP", "250 MP"],
    [
      ["Images, whole project (real)", "390,630", "240,866"],
      ["Total pixel volume (derived)", "~59,109 Gigapixels", "~59,504 Gigapixels"],
      ["Image-conversion cost, whole project", "$2,228–3,087", "$2,238–3,112 (extrapolated)"],
    ],
    [3760, 2800, 2800]
  ),
  note("The same pixel-volume-parity finding as the 10 cm block holds here: despite 240,866 images being 38% fewer than 390,630, total conversion cost is nearly identical (within ~1%) — total pixel volume, not file count, drives compute cost."),

  h3sub("Daily volume, by season"),
  compareTable(
    ["150 MP", "Winter", "Summer"],
    [
      ["Images/day", "~2,710", "~4,540"],
      ["Data/day", "~412 GB", "~690 GB"],
      ["Image-conversion cost/day", "~$15–21", "~$26–36"],
      ["Mosaic cost/day", "~$199–207", "~$332–347"],
      ["Total processing cost/day", "~$214–228", "~$358–382"],
    ],
    [3200, 3080, 3080]
  ),
  compareTable(
    ["250 MP", "Winter", "Summer"],
    [
      ["Images/day", "~2,250", "~3,760"],
      ["Data/day", "~127–249 GB", "~213–416 GB"],
      ["Image-conversion cost/day", "~$21–29", "~$35–49"],
      ["Mosaic cost/day", "~$269–280", "~$449–468"],
      ["Total processing cost/day", "~$289–309", "~$484–517"],
    ],
    [3200, 3080, 3080]
  ),
  note("Daily figures divide each camera's real whole-project total (390,630 / 240,866 images) by its real winter/summer day count from Section 9 — not independently measured day by day, same method as Section 4."),

  h1("12", "Whole-AOI Batch Processing Time (22 parallel VMs, 7.5 cm)"),
  body("Same question as Section 5, at the 7.5 cm image-volume basis: if the entire AOI had to be mosaic-processed as one batch, using the same real measured throughput unit (cpd26-22-d6, 430 images in 23.92 hours)."),
  compareTable(
    ["", "150 MP", "250 MP"],
    [
      ["AOI total", "390,630 images", "240,866 images"],
      ["Time per 430-image package", "23.92 h (measured)", "39.0 h (extrapolated)"],
      ["Packages needed", "909", "561"],
      ["Waves across 22 parallel VMs", "42", "26"],
      ["Total batch processing time", "~1,005 h (~41.9 days)", "~1,014 h (~42.3 days)"],
      ["Total compute cost (22 VMs, $1.316/hr each)", "~$28,600–29,100", "~$28,800–29,400"],
    ],
    [3760, 2800, 2800]
  ),
  note("A smoother cross-check using total compute-hours instead of discrete 22-wide waves gives ~41.2 days (150 MP) and ~41.4 days (250 MP) — both camera paths land close together here, since the two scenarios' final waves leave similarly small slack (15 of 924 VM-slots unused at 150 MP, 11 of 572 at 250 MP)."),
  note("This figure doesn't vary by season, same as Section 5 — it's a fixed-volume, whole-AOI catch-up scenario using this resolution's total project volume (390,630 / 240,866 images)."),

  h1("13", "Whole Project Summary (7.5 cm)"),
  body("Same structure as Section 6: flight collection (Section 9) + 3-month recurring (Section 8 × 3) + whole-project processing (Sections 10–11), by camera and season."),
  compareTable(
    ["", "Flight collection", "Recurring (3 mo)", "Processing", "Total"],
    [
      ["150 MP, winter quarter", "$237,786", "$21,495–22,353", "$30,819–32,905", "~$290,100–293,000"],
      ["150 MP, summer quarter", "$224,745", "$21,495–22,353", "$30,819–32,905", "~$277,100–280,000"],
      ["250 MP, winter quarter", "$176,744", "$21,504–22,377", "$30,975–33,082", "~$229,200–232,200"],
      ["250 MP, summer quarter", "$167,138", "$21,504–22,377", "$30,975–33,082", "~$219,600–222,600"],
    ],
    [2160, 2160, 2200, 2200, 1640]
  ),
  note("Every 7.5 cm total runs higher than its 10 cm counterpart in Section 6 — more flight hours, more images, more processing, all driven by the finer resolution needing more coverage of the same AOI. Same sourcing as Section 6: flight collection is real (Section 9), recurring is the real monthly rate (Section 8) × 3, processing sums the real whole-project conversion figure and the derived whole-project mosaic figure (Section 11)."),

  h1("14", "Key Assumptions & Risks"),
  bullet("Planning basis: this project's AOI, collected and delivered quarterly, at 1 sortie/day, 1 aircraft, ~480 GB/sortie on the 150 MP camera — measured from a real project sortie, not estimated"),
  bullet("One-time build/equipment costs are out of scope for this document — only steady-state recurring costs are covered"),
  bullet("Cloud figures reflect real, current metered rates for the existing pipeline; delivery storage is a shared account also used by other projects, not isolated to this pipeline"),
  bullet("Winter/summer daily figures in Sections 3–4 and 10–11 are derived by scaling real whole-project and single-sortie baselines by real seasonal day counts — they are not independently measured winter and summer sorties"),
  bullet("7.5 cm image-volume totals (390,630 / 240,866) and fleet-configuration data (Section 9) are real, as supplied; downstream figures (Sections 10–13) are derived from them the same way the 10 cm block is derived from its own real inputs"),

  new Paragraph({ children: [new PageBreak()] }),
  h1("A", "Appendix — Recurring Cost Detail"),
  body("Itemized detail behind the Section 1 and Section 8 recurring-cost rollups."),

  h2("A.1  FBO to Cloud", TEAL),
  equipmentTable([
    ["Internet circuit (1 Gbps)", "Carries the upload to the cloud", "1 / office", "$1,200/mo"],
    ["Cloud staging storage", "Holds raw images in the cloud while they wait to be processed", "usage-based", "~$260/mo"],
  ]),

  h2("A.2  Cloud to Delivery (10 cm)", TEAL),
  equipmentTable([
    ["Image conversion — 150 MP", "Converts raw camera files into working images. Cost derived from measured processing time (25–35 s/image) × this project's real total (215,000 images) — not yet a live production bill", "215,000 img / project", "$1,226–1,699 / project (~$409–566/mo)"],
    ["Image conversion — 250 MP", "Same conversion step on the higher-resolution camera. Per-image time extrapolated (not measured) from the 150→250 MP pixel ratio (1.63×); this project's real total is 37% fewer images, but total pixel volume is within ~2.5% of the 150 MP case, so cost comes out nearly identical", "135,000 img / project", "$1,254–1,744 / project (~$418–581/mo)"],
    ["Orthomosaic software license", "Stitches converted images into a seamless map; usage-based, no cap on capacity", "1 / org", "$1,597/mo base + $0.05/processing-hr"],
    ["Orthomosaic & file-finishing compute", "Cloud virtual machines that run the stitching and finishing steps; scale to zero when idle", "usage-based", "~$575/mo"],
    ["Image server", "Publishes finished imagery so it can be viewed and delivered", "1", "~$896/mo"],
    ["Web security gateway", "Protects and fronts the image server", "1", "~$437/mo"],
    ["Delivery storage & content delivery", "Stores and serves finished imagery to customers", "shared account", "~$1,457/mo"],
  ]),

  h2("A.3  Cloud to Delivery (7.5 cm)", TEAL),
  body("Only image conversion differs from A.2 above by resolution — the orthomosaic license, compute, image server, gateway, and delivery storage rows are shared, resolution-independent cloud infrastructure and aren't repeated here."),
  equipmentTable([
    ["Image conversion — 150 MP", "Same conversion step and per-image rate as A.2, applied to this resolution's real image total", "390,630 img / project", "$2,228–3,087 / project (~$743–1,029/mo)"],
    ["Image conversion — 250 MP", "Same conversion step and per-image rate as A.2, applied to this resolution's real image total", "240,866 img / project", "$2,238–3,112 / project (~$746–1,037/mo)"],
  ]),

  h2("A.4  Notes on Figures", TEAL),
  bullet("Image-server, gateway, and compute figures are the cloud provider's current metered rates for this workload"),
  bullet("Delivery storage is a shared-account rate, not isolated to this pipeline"),
  bullet("Image conversion's cost is derived (measured 25–35 s/image × the same VM rate used elsewhere in this pipeline × each resolution's real image totals — 215,000 / 135,000 at 10 cm, 390,630 / 240,866 at 7.5 cm), not a live production bill. See Sections 3–5 (10 cm) and 10–12 (7.5 cm) for the full process-time and volume breakdown. Converting one sortie (~3,171 images, 150 MP) serially takes ~22–31 hours on a single instance — production needs roughly 11–16 parallel instances to clear a sortie in ~2 hours (cost is essentially unchanged by how many instances share the work; parallelism buys turnaround time, not savings)"),
];

writeDoc(buildDocument("Quarterly Permian Collection — Costs & Timelines", children), "Quarterly_Permian_Collection_Costs_Timelines.docx");
