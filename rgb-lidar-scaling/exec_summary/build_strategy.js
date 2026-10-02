const HELPERS_DIR = "C:/Users/pi/claude/pi-internal-tools/rgb-pipeline-roadmap/exec_summary";
const {
  NAVY, TEAL, AMBER, RUST, MUTED,
  docTitle, statRow, h1, h2, h3sub, body, bullet, note,
  compareTable, buildDocument, writeDoc,
} = require(HELPERS_DIR + "/docx_helpers");

const children = [
  ...docTitle(
    "RGB/LiDAR Scaling",
    "Risks, Alternatives & Implementation Plan",
    "1 October 2026",
    "Scope",
    "Open decisions, confirmed risks, alternatives ruled out, and a draft phased implementation sequence. Sub-report of the comprehensive RGB/LiDAR Scaling exec summary."
  ),

  statRow([
    { number: "7", label: "Open decisions blocking a final recommendation", color: RUST },
    { number: "6", label: "Confirmed, already-observed risks", color: AMBER },
    { number: "4", label: "Implementation phases, dependency-ordered", color: NAVY },
  ]),

  h1("1", "Open / Unresolved Decisions"),
  bullet("Correlator3D throughput at 150MP \u2014 unconfirmed; the entire software-engine cost conclusion swings ~$4.3M over 3 years on this one number. Next action: written SimActive sizing quote."),
  bullet("Correlator3D output quality \u2014 assumed to pass, not tested; the same gate that already failed Metashape and Pix4D."),
  bullet("LiDAR workflow \u2014 never described or designed; explicitly deferred mid-session and never resumed. Blocks any LiDAR-specific content until gathered from the user."),
  bullet("Two incompatible physical ingest architectures on record (generic-drive-dock-workstation vs. swappable-NVMe-module + Data Box Gateway), two months apart, never explicitly reconciled."),
  bullet("PosPac cloud path \u2014 still GUI-only, no CLI equivalent found. Three candidate paths, none selected."),
  bullet("CompareContrast-start-Devops Logic App \u2014 may already be live Azure-side plumbing for the contrast step; never confirmed live or reconciled against the current design."),
  bullet("One Button codebase acquisition (\u201cOption C\u201d) \u2014 no cost conversation has occurred with SkyIntelli; only a rough benchmark-only range exists."),

  h1("2", "Confirmed Risks"),
  bullet("Real VM compute cost runs ~3.2x higher than a build-hours-only model for reasons now fully explained (DevOps elastic-pool administrative overhead) \u2014 any future bottom-up model needs this context."),
  bullet("Azure DevOps build-history retention is 30 days \u2014 a full year of historical pipeline data does not exist and cannot be recovered."),
  bullet("Orphaned/idle Azure resources actively billing: imageproc02 (~$42/mo) and pi-blobsftp (~$3/mo) \u2014 small individually, real and actionable, unrelated to this project's own scaling work."),
  bullet("One cost line in the current Permian doc is unreconciled: Cloud staging storage ($260/mo) has no real derivation behind it."),
  bullet("Drive \u201cgoing dark\u201d root cause is a known, fixable Windows power-management default (USB selective suspend) \u2014 not a hardware defect; low-cost fix regardless of which ingest architecture is chosen."),
  bullet("OAuth-based integrations left in a provider's \u201cTesting\u201d mode can silently expire on a short cycle (observed elsewhere: 7 days) \u2014 worth a quick check on any new RGB/LiDAR integration using OAuth."),

  h1("3", "Alternatives Considered and Ruled Out"),
  compareTable(
    ["Alternative", "Reason ruled out"],
    [
      ["Metashape, Pix4D", "Already tested in-house, failed quality bar vs. One Button"],
      ["WebODM", "RAM/compute-scaling grounds at large-format resolution"],
      ["MicMac", "Not ruled out \u2014 gated behind two unresolved cheap pre-checks (GPU-at-scale, RAM-at-150MP) and a dead community-support channel"],
      ["10G tether (aircraft\u2192ground)", "Rejected for a swappable-module drive pool \u2014 works identically at every office, no airframe connector needed"],
      ["Bulk transfer over onboard Starlink", "Too slow (28\u2013111 hrs/sortie) \u2014 retained only as a QC/pre-load channel"],
      ["Correlator3D 3-month node rental", "Removed once usage horizon was set >1yr (buy-vs-rent breakeven ~1.01 years)"],
    ],
    [3200, 6160]
  ),

  h1("4", "Recommended Spend Framing"),
  body("Given the open state of several decisions above, this report presents cost ranges and sensitivity tables rather than single committed figures wherever an item is still open \u2014 specifically the software-engine decision (see the 3-scenario sensitivity table in the Software Comparison report) and anything LiDAR-related (flagged as pending input, not estimated)."),

  h1("5", "Draft Implementation Sequence"),
  note("Dependency-ordered draft \u2014 not yet reviewed or approved by the user."),

  h2("Phase 0 \u2014 Close open decisions that block everything else", TEAL),
  bullet("Reconcile the two ingest architectures \u2014 pick one before buying hardware."),
  bullet("Gather the current LiDAR workflow description from the user."),
  bullet("Send the SimActive sizing-quote request \u2014 free, doesn't block other phases, but vendor turnaround can be slow."),
  bullet("Confirm whether pi-blobsftp and CompareContrast-start-Devops are live/in-use."),

  h2("Phase 1 \u2014 Ingest pipeline (cheapest, highest-certainty wins first)", TEAL),
  bullet("Fix the confirmed root cause of drive \u201cgoing dark\u201d (disable USB selective suspend) \u2014 zero cost, fixes a real problem immediately."),
  bullet("Stand up the drive-tracking process fix (two-bin system + numbered drive log)."),
  bullet("Build/deploy whichever ingest architecture Phase 0 selects."),
  bullet("Wire pi-1000-imageconverter (already built, free-licensed) into production for IIQ\u2192JPEG."),

  h2("Phase 2 \u2014 Processing engine decision", TEAL),
  bullet("Hold at One Button until SimActive's quote and a quality test land."),
  bullet("Re-run the throughput sensitivity table with the real figure once available, before any capital commitment."),
  bullet("Separately scope PosPac's three candidate cloud paths once the ingest pipeline is stable."),

  h2("Phase 3 \u2014 Cost tracking / prediction system (standing directive, not yet started)", TEAL),
  body("Once per-project cost tagging exists in production, build toward a real spend-by-area/resolution/camera prediction system, validated against live Cost Management data. A distinct deliverable from this report."),

  h2("Cost Summary by Phase (placeholder)", AMBER),
  compareTable(
    ["Phase", "One-time", "Recurring", "Depends on"],
    [
      ["0 \u2014 Decisions", "$0 (research/quotes only)", "\u2014", "none"],
      ["1 \u2014 Ingest", "TBD \u2014 depends on Design A vs. B", "TBD", "Phase 0.1"],
      ["2 \u2014 Engine", "$0 now (stay on OB) / up to ~$300k+ if switching", "OB: ~$41k/yr license, ~$403k/yr all-in", "Phase 0.3"],
      ["3 \u2014 Cost system", "Not yet scoped", "\u2014", "Phase 1 live"],
    ],
    [2000, 3000, 2800, 1560]
  ),
  note("LiDAR-equivalent phases cannot be filled in until Phase 0.2 is resolved."),
];

module.exports = { children };

if (require.main === module) {
  writeDoc(
    buildDocument("RGB/LiDAR Scaling — Risks, Alternatives & Implementation Plan", children),
    "C:\\Users\\pi\\claude\\pi-internal-tools\\rgb-lidar-scaling\\exec_summary\\Risks_Alternatives_Implementation.docx"
  );
}
