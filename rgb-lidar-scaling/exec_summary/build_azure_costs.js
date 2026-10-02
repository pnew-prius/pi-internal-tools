const HELPERS_DIR = "C:/Users/pi/claude/pi-internal-tools/rgb-pipeline-roadmap/exec_summary";
const {
  NAVY, TEAL, AMBER, RUST, MUTED,
  docTitle, statRow, h1, h2, h3sub, body, bullet, note,
  compareTable, equipmentTable, buildDocument, writeDoc,
} = require(HELPERS_DIR + "/docx_helpers");

const children = [
  ...docTitle(
    "RGB/LiDAR Scaling",
    "Azure Cost Validation",
    "1 October 2026",
    "Scope",
    "Methodology and findings behind the validated Azure cost figures used throughout this evaluation — real Cost Management data, confirmed rates, and the gap between bottom-up modeling and real spend. Full itemized recurring-cost tables live in Quarterly_Permian_Collection_Costs_Timelines.docx; this report summarizes the validation work, not the full line-item detail."
  ),

  statRow([
    { number: "~3.2x", label: "Real VM compute cost vs. build-hours-only model — now fully explained", color: NAVY },
    { number: "30 days", label: "Azure DevOps build-history retention — no year of history exists", color: AMBER },
    { number: "~$48/mo", label: "Confirmed waste — orphaned/idle disks on deallocated VMs", color: RUST },
  ]),

  h2("Standing Directive", NAVY),
  body("Validate RGB pipeline cost work against live Azure Cost Management data as the authoritative source, not just bottom-up per-image modeling — for this project and future ones. Long-term goal (not yet started): aggregate real spend over time, correlated with project metadata (area, resolution, camera), to predict future project costs."),

  h1("1", "Key Finding: Bottom-Up Models Undercount Real Spend — Now Fully Explained"),
  body("Real Cost Management MTD spend (Sept 1\u201315 2026) for rg_imageryprocessing_southcentralus = $180.93\u2013181.45 vs. a build-hours-only model's $20.34 \u2014 an initial ~7\u20139x apparent gap, resolved by itemizing:"),
  compareTable(
    ["Category", "15-day real cost", "What it is"],
    [
      ["Mosaic VM compute", "$47.74", "Real compute \u2014 ~3.2x the build-hours model alone"],
      ["GDAL VM compute", "$16.80", "Real compute"],
      ["piimageprocessing storage", "$41.49", "Raw staging \u2014 never modeled per-image"],
      ["imageproc02 orphaned disks", "$42.36", "Real waste \u2014 VM deallocated, disks still bill"],
      ["pi-blobsftp orphaned disk+IP", "$2.94", "Same pattern, smaller"],
      ["Private endpoints", "$7.06", "Real networking cost"],
      ["VMSS per-instance temp disks", "$17.72", "Real per-build overhead, never modeled"],
    ],
    [3400, 2080, 3880]
  ),
  note("The remaining ~3.2x gap in VM compute itself is Azure DevOps's own elastic-pool administrative overhead, not job overhead \u2014 confirmed via Activity Log caller identity: DevOps's service principal performs scheduled pool maintenance (an exact every-2-hour cycle observed) on both VM pools, independent of real job volume. This is real, recurring, shared-platform overhead that exists whether or not this project runs any jobs \u2014 correctly excluded from any single project's per-image rate."),

  h1("2", "Real, Confirmed Rates (Azure Retail Prices API)"),
  equipmentTable([
    ["Standard_F16s_v2", "One Button mosaic compute", "southcentralus", "$0.816/hr"],
    ["Standard_D16ds_v4", "GDAL pool", "southcentralus", "$1.175/hr"],
    ["Standard_NV36ads_A10_v5", "Correlator3D benchmark VM (full A10)", "southcentralus", "$3.84/hr"],
    ["Standard_NV6ads_A10_v5", "Smaller A10 slice", "southcentralus", "$0.545/hr"],
    ["Azure Bastion (Basic/Standard)", "Ingest/RDP access", "southcentralus", "$0.19\u2013$0.29/hr"],
  ]),
  body("One Button's blended mosaic rate: $0.866/hr ($0.816 compute + real $0.05/hr license usage). A prior $1.316/hr figure double-counted a $0.50/hr license placeholder against the real $1,597/mo+$0.05/hr contract \u2014 corrected."),

  h1("3", "Real VM Parallelism Ceilings"),
  body("The true ceiling is subscription-level vCPU quota per VM family, confirmed live via az vm list-usage \u2014 not VMSS sku.capacity, which is not a cap:"),
  compareTable(
    ["Pool", "Family", "Quota limit", "Headroom (point-in-time)"],
    [
      ["Mosaic (imageproc-vmss)", "Standard FSv2", "576 vCPU", "~33 more F16s_v2 VMs"],
      ["GDAL (gdalproc-vmss)", "Standard DDSv4", "256 vCPU", "~15 more D16ds_v4 VMs"],
    ],
    [3200, 2400, 1880, 1880]
  ),
  note("Point-in-time readings, not contractual ceilings \u2014 re-check before relying on them for a real production burst. Total compute cost is unaffected by VM count (fixed by volume \u00f7 per-image rate) \u2014 only turnaround time changes, so there's no cost reason to run fewer VMs than this headroom allows."),
  bullet("Real GDAL per-VM throughput (historical build data, one outlier excluded): 598.5\u2013895.9 img/hr/VM."),
  bullet("Real mosaic per-VM throughput: 17.24\u201317.98 img/hr/VM \u2014 same confirmed figure as the Software Comparison report."),

  h1("4", "Delivery Storage — Real Accumulation Model"),
  body("Five historical Permian seasonal deliveries (spring 2023\u20132026) remain in storage, none ever purged. Real measured stats: 238\u2013291 tiles/delivery (avg ~259), 6.51\u20137.05 GB/tile average (avg ~6.52 GB), confirmed 430-image max tile size."),
  bullet("Finding: delivery storage grows every quarter the project operates \u2014 it is not a flat monthly line."),
  bullet("Real added cost ~$37\u2013107/mo per quarter depending on resolution/camera; real steady-state cost after collection ends (4 quarters of accumulation) ~$147\u2013427/mo."),
  bullet("Rate: $0.018/GB/month, confirmed live against Azure Retail Prices."),

  h1("5", "Storage Line-Item Validation"),
  compareTable(
    ["Line item", "Status"],
    [
      ["Delivery storage & CDN (~$1,457/mo)", "Real, validated twice against live Cost Management pulls a month apart \u2014 trustworthy"],
      ["Image server (~$896/mo)", "Real GeoServer infra, cross-checked live (~$845/mo MTD extrapolated) \u2014 trustworthy"],
      ["Cloud staging storage ($260/mo)", "FLAGGED \u2014 no real GB-usage derivation ever found; real current actual is ~$83/mo, though not a true comparison to future production volume"],
    ],
    [4680, 4680]
  ),

  h1("6", "Known Data Limitations"),
  bullet("Azure DevOps build-history retention is 30 days \u2014 confirmed live (purgeRuns: 30). A full year of historical pipeline data does not exist and cannot be recovered."),
  bullet("The installed costmanagement CLI extension is corrupted on this machine, breaking every az command. Workaround: set AZURE_EXTENSION_DIR to an empty writable folder before calling az."),
  bullet("Cost Management Query API is rate-limited on a clienttype quota that grows its retry-after with concurrent use from other sessions on the same account \u2014 wait the real retry-after value rather than retrying in a tight loop."),
];

module.exports = { children };

if (require.main === module) {
  writeDoc(
    buildDocument("RGB/LiDAR Scaling — Azure Cost Validation", children),
    "C:\\Users\\pi\\claude\\pi-internal-tools\\rgb-lidar-scaling\\exec_summary\\Azure_Cost_Validation.docx"
  );
}
