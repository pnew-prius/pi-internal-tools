const {
  NAVY, TEAL, AMBER, MUTED, PageBreak,
  docTitle, statRow, h1, h2, body, bullet, note,
  compareTable, equipmentTable, buildDocument, writeDoc,
} = require("./docx_helpers");
const { Paragraph } = require("docx");

const children = [
  ...docTitle(
    "Quarterly Permian Collection",
    "Costs & Timelines",
    "13 September 2026",
    "Scope",
    "Steady-state, post-upgrade operation over the Permian AOI — collected & delivered quarterly. Assumes the RGB Minimal Touch Upgrade Road Map is complete; no one-time build costs included."
  ),

  statRow([
    { number: "~$6,830–6,990/mo", label: "Recurring cloud operating cost", color: NAVY },
    { number: "~25.3 h", label: "Wheels-up to delivery-ready (150 MP, one sortie)", color: TEAL },
    { number: "3", label: "Pipeline legs — Collection, FBO, Cloud", color: MUTED },
  ]),

  h2("Key Notes", NAVY),
  bullet("This document assumes the RGB Minimal Touch Upgrade Road Map (see the companion document) is complete and operating. All figures below are steady-state, post-upgrade recurring costs and turnaround times — no one-time build or equipment costs are included; those are itemized in the companion document."),
  bullet("The ~$6,830–6,990/month recurring figure is scoped to this project's AOI (collected and delivered quarterly), not total company volume — it is not comparable to whole-company historical billing."),
  bullet("Cloud figures reflect real, current metered rates; flight-collection figures reflect real internal flight-planning estimates."),

  new Paragraph({ spacing: { before: 260 }, children: [] }),

  h1("1", "Recurring Operating Cost"),
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
  body("Real internal flight-planning estimates at 10 cm resolution — matching the image-volume basis (215,000 / 135,000 images) used throughout this document. This is flight operations cost (aircraft, crew, fuel) to physically collect the AOI — a different cost category from the cloud recurring cost in Section 1. PAS150 = the current 150 MP camera; RS250 = the 250 MP camera discussed throughout this document. A matching 7.5 cm comparison will be added once those image volumes are available — don't compare figures across the two resolutions until then."),
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

  h1("3", "Process Time — One Collection Cycle (150 MP vs. 250 MP)"),
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

  h1("4", "Whole-Project Volume Comparison (150 MP vs. 250 MP)"),
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

  h1("5", "Whole-AOI Batch Processing Time (22 parallel VMs)"),
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

  h1("6", "Key Assumptions & Risks"),
  bullet("Planning basis: this project's AOI, collected and delivered quarterly, at 1 sortie/day, 1 aircraft, ~480 GB/sortie on the 150 MP camera — measured from a real project sortie, not estimated"),
  bullet("Assumes the RGB Minimal Touch Upgrade Road Map is complete and operating; one-time build/equipment costs are out of scope here — see the companion document"),
  bullet("Cloud figures reflect real, current metered rates for the existing pipeline; delivery storage is a shared account also used by other projects, not isolated to this pipeline"),

  new Paragraph({ children: [new PageBreak()] }),
  h1("A", "Appendix — Recurring Cost Detail"),
  body("Itemized detail behind the Section 1 recurring-cost rollup. One-time build/equipment costs behind these services are itemized separately in the companion RGB Minimal Touch Upgrade Road Map, Appendix A."),

  h2("A.1  FBO to Cloud", TEAL),
  equipmentTable([
    ["Internet circuit (1 Gbps)", "Carries the upload to the cloud", "1 / office", "$1,200/mo"],
    ["Cloud staging storage", "Holds raw images in the cloud while they wait to be processed", "usage-based", "~$260/mo"],
  ]),

  h2("A.2  Cloud to Delivery", TEAL),
  equipmentTable([
    ["Image conversion — 150 MP", "Converts raw camera files into working images. Cost derived from measured processing time (25–35 s/image) × this project's real total (215,000 images) — not yet a live production bill", "215,000 img / project", "$1,226–1,699 / project (~$409–566/mo)"],
    ["Image conversion — 250 MP", "Same conversion step on the higher-resolution camera. Per-image time extrapolated (not measured) from the 150→250 MP pixel ratio (1.63×); this project's real total is 37% fewer images, but total pixel volume is within ~2.5% of the 150 MP case, so cost comes out nearly identical", "135,000 img / project", "$1,254–1,744 / project (~$418–581/mo)"],
    ["Orthomosaic software license", "Stitches converted images into a seamless map; usage-based, no cap on capacity", "1 / org", "$1,597/mo base + $0.05/processing-hr"],
    ["Orthomosaic & file-finishing compute", "Cloud virtual machines that run the stitching and finishing steps; scale to zero when idle", "usage-based", "~$575/mo"],
    ["Image server", "Publishes finished imagery so it can be viewed and delivered", "1", "~$896/mo"],
    ["Web security gateway", "Protects and fronts the image server", "1", "~$437/mo"],
    ["Delivery storage & content delivery", "Stores and serves finished imagery to customers", "shared account", "~$1,457/mo"],
  ]),

  h2("A.3  Notes on Figures", TEAL),
  bullet("Image-server, gateway, and compute figures are the cloud provider's current metered rates for this workload"),
  bullet("Delivery storage is a shared-account rate, not isolated to this pipeline"),
  bullet("Image conversion's cost is derived (measured 25–35 s/image × the same VM rate used elsewhere in this pipeline × this project's real image totals — 215,000 for 150 MP, 135,000 for 250 MP), not a live production bill. See Sections 3–5 for the full 150 MP vs. 250 MP process-time and volume breakdown. Converting one sortie (~3,171 images, 150 MP) serially takes ~22–31 hours on a single instance — production needs roughly 11–16 parallel instances to clear a sortie in ~2 hours (cost is essentially unchanged by how many instances share the work; parallelism buys turnaround time, not savings)"),
];

writeDoc(buildDocument("Quarterly Permian Collection — Costs & Timelines", children), "Quarterly_Permian_Collection_Costs_Timelines.docx");
