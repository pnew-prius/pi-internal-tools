const HELPERS_DIR = "C:/Users/pi/claude/pi-internal-tools/rgb-pipeline-roadmap/exec_summary";
const {
  NAVY, TEAL, AMBER, RUST, MUTED,
  docTitle, statRow, h1, h2, h3sub, body, bullet, note,
  compareTable, buildDocument, writeDoc,
} = require(HELPERS_DIR + "/docx_helpers");
const { Paragraph } = require(require.resolve("docx", { paths: [HELPERS_DIR] }));

const children = [
  ...docTitle(
    "RGB/LiDAR Scaling",
    "Software / Processing Engine Comparison",
    "1 October 2026",
    "Scope",
    "One Button vs. Correlator3D vs. MicMac — licensing, throughput, and total cost of ownership. Sub-report of the comprehensive RGB/LiDAR Scaling exec summary."
  ),

  statRow([
    { number: "17.24 img/hr", label: "One Button — confirmed twice, real data", color: NAVY },
    { number: "152.7 img/hr", label: "Correlator3D working estimate — unconfirmed", color: AMBER },
    { number: "±$4.3M / 3yr", label: "TCO swing across the throughput uncertainty range", color: RUST },
  ]),

  h2("Status: Open — Conditional Recommendation Only", NAVY),
  body("The entire cost conclusion in this comparison hinges on one unconfirmed number: Correlator3D's real throughput at the team's actual 150MP camera resolution. Until a written SimActive sizing quote or a real trial on production imagery lands, this section presents a conditional recommendation with explicit sensitivity ranges — not a single committed number."),

  h1("1", "One Button (SkyIntelli) — Current Production Baseline"),
  bullet("Real 2025 total cost: $41,333.30/yr (base license $19,161/yr + $0.05/processing-hour usage, no concurrency cap)."),
  bullet("Real throughput: 17.24–17.25 img/hr/head — confirmed independently twice, from two different real datasets (12-tile and 33-tile regressions, r² 0.68 and 0.88). The single most solidly-confirmed number in this entire evaluation."),
  bullet("Demonstrated burst: 22 concurrent heads — not a contractual/technical ceiling (Azure scale-set max is 25, itself raisable). Real annual-parity need is closer to ~51 heads."),
  bullet("Confirmed via real build logs: requests a GPU, silently falls back to CPU every run. A real production GPU trial did not justify its added cost — the 17.24 img/hr baseline is a CPU-fallback number that already reflects a tested, not assumed, hardware choice."),
  bullet("Real all-in annual cost at annual-parity scale: ~$403,185/yr ($41,333 license + ~$361,852 Azure compute) — dramatically higher than the license-only headline figure."),

  h1("2", "Correlator3D (SimActive) — Leading Alternative"),
  bullet("Real vendor quote: $50,000/license per processing node, 20% annual maintenance. Rental ruled out (usage horizon is >1yr / Azure production expansion)."),
  bullet("GPU-mandatory by design (confirmed, vendor whitepaper) — not optional."),
  bullet("Real published benchmark (primary source): 1,000 images @ 42MP in ~1.1hr / <$30 on Standard_NV36ads_A10_v5."),
  bullet("The unconfirmed number: extrapolating 42MP→150MP needs a linear pixel-scaling assumption (909→254.5 img/hr) plus a 40% conservative haircut → working estimate 152.7 img/hr. Three layers removed from anything measured at 150MP."),
  bullet("Distributed processing requires a separate license per node (confirmed)."),
  bullet("Vendor's own recommended hardware (RTX 4070) has no Azure equivalent — Azure GPU VMs are datacenter-class only (A10/L4/T4/A100/H100)."),
  bullet("Quality: ASSUMED to pass per explicit working assumption, NOT independently tested — the same gate that already failed Metashape and Pix4D in-house."),

  h2("Throughput Sensitivity — the number the whole decision rests on", TEAL),
  compareTable(
    ["Scenario", "img/hr", "Result vs. One Button"],
    [
      ["Pessimistic (public FAQ benchmark)", "40", "~2x MORE expensive"],
      ["Breakeven", "81.1", "equal"],
      ["Working estimate (used throughout this evaluation)", "152.7", "~half the cost (compute only)"],
      ["Optimistic (whitepaper extrapolation, no haircut)", "254.5", "cheaper still"],
    ],
    [4680, 1800, 2880]
  ),
  note("At real annual-parity node counts (6 nodes, not the burst-sized 3), full 3-year TCO swings by roughly $4.3M across this range alone. This is not a minor sensitivity — it is the entire decision."),

  h1("3", "MicMac (Open-Source) — Secondary Thread"),
  bullet("GPU: real CUDA support exists in the dense-matching step, but an unresolved multi-year community report flags GPU memory overload at exactly the 200-1000+ image counts a production test would use — a worse failure mode than \"no GPU,\" since it could pass a small test and fail at scale."),
  bullet("RAM: confirmed real risk — not dense matching itself, but the orthomosaic/texturing stage. No public benchmark exists at 150MP."),
  bullet("Support: the official community forum domain has lapsed — no SLA and no functioning community channel."),
  bullet("Licensing ($0/head) is only an advantage vs. Correlator3D — One Button already scales free."),
  bullet("Recommendation: do not spend on a real MicMac benchmark until the GPU-at-scale and RAM-at-150MP questions are cheaply re-checked."),

  h1("4", "Also Evaluated and Ruled Out"),
  bullet("Metashape / Pix4D — already tested in-house, failed the quality bar vs. One Button."),
  bullet("WebODM — ruled out on RAM/compute-scaling grounds at large-format resolution."),
  bullet("Acquire the One Button codebase outright (\"Option C\") — no cost conversation with SkyIntelli has occurred. Rough, non-vendor-sourced estimate only: $120,000–$470,000+, 3–9+ months. Reverse-breakeven ceiling from license-avoidance alone: ~$124,000 (3yr) / ~$207,000 (5yr) / ~$413,000 (10yr)."),

  h1("5", "Recommendation"),
  body("Stay on One Button. It is the only option with a fully confirmed, real, end-to-end track record — real cost, real throughput (confirmed twice), demonstrated burst capacity, no per-head fee. Correlator3D's case rests on one confirmed fact (price) and two still-unconfirmed inputs (throughput, quality). Both need real numbers — not planning assumptions — before a switch decision."),
  h3sub("Next concrete action"),
  body("Request a written SimActive throughput/sizing estimate for 150MP on their recommended Azure GPU SKU (free, existing sales relationship). The request should specify: exact SKU/region/specs (don't let them choose silently), single-VM vs. distributed, a stage-by-stage timing breakdown matching their own whitepaper's module breakdown, actual Azure compute cost for the run, and the real output files for an independent quality check against One Button's result on the same imagery."),

  new Paragraph({ spacing: { before: 260 }, children: [] }),
  h2("Open Items Carried Into Risk Register", MUTED),
  bullet("SimActive sizing quote — not yet sent as of this writing."),
  bullet("Correlator3D quality — not independently tested."),
  bullet("SkyIntelli (OB codebase acquisition) — no cost conversation has occurred."),
  bullet("MicMac GPU-at-scale / RAM-at-150MP — not re-tested since initial cheap-check findings."),
];

module.exports = { children };

if (require.main === module) {
  writeDoc(
    buildDocument("RGB/LiDAR Scaling — Software Comparison", children),
    "C:\\Users\\pi\\claude\\pi-internal-tools\\rgb-lidar-scaling\\exec_summary\\Software_Comparison.docx"
  );
}
