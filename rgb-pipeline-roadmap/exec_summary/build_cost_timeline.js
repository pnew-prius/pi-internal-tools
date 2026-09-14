const {
  NAVY, TEAL, AMBER, MUTED, USABLE,
  docTitle, statRow, h1, h2, body, bullet, note,
  costTable, compareTable, resourceTable, buildDocument, writeDoc,
} = require("./docx_helpers");
const { Paragraph } = require("docx");

const children = [
  ...docTitle(
    "Cost & Timeline",
    "13 September 2026",
    "Scope",
    "Aircraft capture through customer delivery — three legs, one project's AOI, collected & delivered quarterly"
  ),

  statRow([
    { number: "$64,100–153,300", label: "Total one-time investment", color: NAVY },
    { number: "~$6,830–6,990/mo", label: "Recurring run cost", color: TEAL },
    { number: "8–14 wks", label: "Fastest possible, fully parallel", color: AMBER },
    { number: "3", label: "Pipeline legs — Collection, FBO, Cloud", color: MUTED },
  ]),

  h2("Key Notes", NAVY),
  bullet("This document covers resourcing, the rolled-up cost table, schedule, and process/collection-time comparisons. What's being built, current vs. finished state, gaps, and the itemized equipment/services behind these totals are in the companion Upgrade Plan document."),
  bullet("Development figures throughout this document are rough engineering estimates, not vendor quotes — refine before committing budget."),
  bullet("Before the timeline in Section 2 starts, hardware needs to be ordered — no committed lead time yet."),
  bullet("The ~$6,830–6,990/month recurring figure is scoped to this project's AOI (collected and delivered quarterly), not total company volume — it is not comparable to whole-company historical billing."),

  new Paragraph({ spacing: { before: 260 }, children: [] }),

  h1("1", "Resources"),
  body("Roles required to close the gaps identified in Section 4 of the companion Upgrade Plan document. Rates and total hours are not yet scoped — see Section 2 below."),
  resourceTable(),

  h1("2", "Cost & Timeline"),
  body("Figures are planning estimates by pipeline leg. See the companion Upgrade Plan document, Appendix A, for the underlying equipment and service breakdown."),
  costTable(),
  note("*Cloud to Delivery recurring cost now includes a derived estimate for image conversion (~$409–566/mo on the 150 MP camera, see the Upgrade Plan's Appendix A.3) alongside current metered rates for a shared-tenant workload; see Appendix A.4 there."),
  h2("Indicative timeline (parallel workstreams)", NAVY),
  bullet("Collection to FBO — 8–14 weeks (largest engineering scope; bounds the overall timeline)"),
  bullet("FBO to Cloud — 1–2 weeks"),
  bullet("Cloud to Delivery — 4–8 weeks"),
  body("Running in parallel, overall duration is bounded by Collection to FBO: approximately 8–14 weeks."),

  h2("Process time — one collection cycle (150 MP vs. 250 MP)", NAVY),
  body("One sortie, one aircraft, one day of flying. 150 MP figures build on real measured data (the 17.24 img/hr mosaic rate is confirmed twice from independent real datasets); the specific end-to-end scenario below — one large sortie split into ~12 parallel tile-builds — is a derivation from those real inputs, not itself a measured run. 250 MP figures are extrapolated from the 150 MP numbers by the 1.63× pixel ratio; that camera has never run through this pipeline."),
  compareTable(
    ["Stage", "150 MP", "250 MP"],
    [
      ["Collection (flight)", "6 h", "6 h"],
      ["Aircraft → FBO", "~8 min", "~8 min"],
      ["Upload to cloud (1 Gbps)", "~1.3–1.4 h (482 GB, measured)", "~0.3–0.6 h (110–215 GB)"],
      ["Image conversion (parallel)", "~2 h", "~2 h (extrapolated)"],
      ["Mosaic (parallel, ~12 tile-builds)", "~15.3 h (measured rate)", "~17.2 h (extrapolated)"],
      ["GDAL merge/trim/COG (parallel)", "~0.5 h", "~0.5 h (extrapolated)"],
      ["Publish to image server", "minutes", "minutes"],
      ["Total, wheels-up → delivery-ready", "~25.3 h", "~26.1 h"],
    ],
    [3760, 2800, 2800]
  ),
  note("Neither camera reaches same-calendar-day delivery — both land at roughly next-day. Mosaic processing, not the cloud/network steps this document otherwise focuses on, is the bottleneck (~60% of total time either way). The 250 MP camera's faster upload doesn't improve end-to-end time because mosaic time tracks total pixels processed, not file size — 250 MP is marginally slower overall despite cutting transport volume 55–75%."),

  h2("Whole-project volume comparison (150 MP vs. 250 MP)", NAVY),
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

  h2("Whole-AOI batch processing time (22 parallel VMs)", NAVY),
  body("A different question from the per-sortie turnaround above: if the entire AOI had to be mosaic-processed as one batch — e.g. catching up a backlog — how long would it take running the demonstrated 22-VM burst capacity flat out? Modeled using a real measured build as the throughput unit: cpd26-22-d6, 430 images in 23.92 hours (17.98 img/hr), the largest single real build on record. 150 MP uses that time as-is; 250 MP scales it by the same 1.63× pixel ratio used throughout this document — not independently measured."),
  compareTable(
    ["", "150 MP", "250 MP"],
    [
      ["AOI total", "215,000 images", "135,000 images"],
      ["Time per 430-image package", "23.92 h (measured)", "39.0 h (extrapolated)"],
      ["Packages needed", "500", "314"],
      ["Waves across 22 parallel VMs", "23", "15"],
      ["Total batch processing time", "~550 h (~22.9 days)", "~585 h (~24.4 days)"],
    ],
    [3760, 2800, 2800]
  ),
  note("250 MP again comes out slightly slower overall (~24.4 vs. ~22.9 days) despite 37% fewer images, for the same reason as the per-sortie comparison: processing time tracks total pixels, not file count. A smoother cross-check using total compute-hours instead of discrete 22-wide waves gives ~22.6 days (150 MP) and ~23.2 days (250 MP) — the gap to the wave-based figures above is the wall-clock cost of each scenario's last, partial wave running under a full VM pool."),

  h2("Collection time & cost, by fleet configuration (10 cm)", NAVY),
  body("Real internal flight-planning estimates at 10 cm resolution — matching the image-volume basis (215,000 / 135,000 images) used throughout this document. A different cost category from the infrastructure and cloud figures elsewhere: this is flight operations cost (aircraft, crew, fuel) to physically collect the AOI, not included in the cost table or Key Metrics totals above. PAS150 = the current 150 MP camera; RS250 = the 250 MP camera discussed throughout this document. A matching 7.5 cm comparison will be added once those image volumes are available — don't compare figures across the two resolutions until then."),
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

  h1("3", "Key Assumptions & Risks"),
  bullet("Planning basis: this project's AOI, collected and delivered quarterly, at 1 sortie/day, 1 aircraft, ~480 GB/sortie on the 150 MP camera — measured from a real project sortie, not estimated"),
  bullet("Development figures are rough engineering estimates pending detailed scoping, not vendor quotes"),
  bullet("Cloud figures reflect real, current metered rates for the existing pipeline; delivery storage is a shared account also used by other projects, not isolated to this pipeline"),
];

writeDoc(buildDocument("RGB Imagery Pipeline — Cloud Migration · Cost & Timeline", children), "RGB_Pipeline_Cost_Timeline.docx");
