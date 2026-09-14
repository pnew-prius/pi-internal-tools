const {
  NAVY, TEAL, AMBER, RUST, MUTED, USABLE, PageBreak,
  docTitle, statRow, h1, h2, h3sub, body, bullet, note,
  equipmentTable, buildDocument, writeDoc,
} = require("./docx_helpers");
const { Paragraph } = require("docx");

const children = [
  ...docTitle(
    "Upgrade Plan — Architecture, Capabilities & Equipment",
    "13 September 2026",
    "Scope",
    "Aircraft capture through customer delivery — three legs, one project's AOI, collected & delivered quarterly"
  ),

  statRow([
    { number: "3", label: "Pipeline legs — Collection, FBO, Cloud", color: NAVY },
    { number: "5", label: "Gaps to close to reach finished state", color: TEAL },
    { number: "Built", label: "Image conversion — core proven, tuning + orchestration remain", color: MUTED },
    { number: "$64,100–153,300", label: "Total one-time equipment & build cost (Appendix A)", color: AMBER },
  ]),

  h2("Key Notes", NAVY),
  bullet("This document covers what's being built and why, leg by leg, plus the itemized equipment and services behind each leg's cost. Resourcing, the rolled-up cost table, schedule, and process/collection-time comparisons live in the companion Cost & Timeline document."),
  bullet("Development figures throughout this document are rough engineering estimates, not vendor quotes — refine before committing budget."),
  bullet("All figures are scoped to this project's AOI (collected and delivered quarterly), not total company volume."),

  new Paragraph({ spacing: { before: 260 }, children: [] }),

  h1("1", "Work To Be Done — Scope"),
  body("Move RGB aerial-imagery processing off on-premise office workstations and onto cloud infrastructure, in three legs. The architecture below is the general approach for minimal-touch collection to delivery; the volumes and costs in this document are scoped to one project's AOI, collected and delivered quarterly — not total company volume:"),
  bullet("Collection to FBO — verified capture, in-flight quality checks, and physical transport of raw imagery from the aircraft to the office", { bold: true }),
  bullet("FBO to Cloud — reliable, automated upload of raw imagery from the office into cloud storage", { bold: true }),
  bullet("Cloud to Delivery — converting raw imagery into finished orthomosaics and publishing them to customers, entirely on cloud infrastructure", { bold: true }),

  h1("2", "Finished State Capabilities"),
  bullet("Photo quality is checked in flight — a bad flight line is caught and re-flown the same sortie"),
  bullet("Every image is checksummed at capture and verified at each handoff — a complete chain of custody from aircraft to cloud"),
  bullet("Aircraft turn around in minutes using swappable drive modules — no waiting on a copy"),
  bullet("Raw imagery uploads from the office to the cloud automatically, recovering on its own from any interruption"),
  bullet("Raw-image conversion, orthomosaic stitching, and file finishing all run on cloud compute that scales to zero between flights"),
  bullet("Finished imagery is published and delivered to customers without manual handling"),

  h1("3", "Current State Capabilities"),
  bullet("Orthomosaic stitching and file finishing already run on cloud compute — operating today"),
  bullet("The imagery server already publishes finished imagery — operating today"),
  bullet("Delivery storage and content delivery already serve customers — operating today"),
  bullet("Image capture handling, in-flight quality checking, drive management, and converting raw camera files into working images remain manual, on-premise steps on office workstations", { color: RUST }),

  h1("4", "Gaps"),
  body("Correlated to the three legs in Section 1:"),
  h2("Collection to FBO", TEAL),
  bullet("No onboard quality-check device"),
  bullet("No verified, swappable-drive capture system"),
  h2("FBO to Cloud", TEAL),
  bullet("No automated, self-healing upload pipeline from the office into the cloud"),
  h2("Cloud to Delivery", TEAL),
  bullet("Image-conversion pipeline (real GitHub repo) has core conversion, geometric correction, and ICC embedding proven on production imagery; SDK-native sharpening and a clarity feature are not yet built or tuned"),
  bullet("No automated pipeline wiring the landing point through conversion into the existing stitching and finishing steps"),

  new Paragraph({ children: [new PageBreak()] }),
  h1("A", "Appendix — Technical Addendum"),
  body("Equipment and services underlying the upgrade, by pipeline leg. Rolled-up totals and the schedule that follows from this scope are in the companion Cost & Timeline document."),

  h2("A.1  Collection to FBO", TEAL),
  body("This document assumes 1 aircraft and 1 FBO. Split below by what actually scales with what — an additional aircraft at the same FBO repeats only the per-aircraft rows; an additional FBO (serving any number of aircraft) repeats only the per-FBO rows; the software rows are built once, fleet-wide, and never repeat."),

  h3sub("Per aircraft — repeats for each additional plane"),
  equipmentTable([
    ["Onboard edge computer", "Ruggedized computer on the aircraft; checks each photo for quality — blur, exposure, coverage gaps — as it's taken; saves photos to a drive with a checksum", "1 / aircraft", "$2,000–4,000"],
    ["Camera-to-computer cabling", "Connects the camera to the onboard computer", "1 / aircraft", "$200–500"],
    ["Removable NVMe drives", "Swappable drives; full drive out, blank drive in after landing", "4 / aircraft", "$1,600–3,200"],
    ["Aircraft installation", "Mounting, wiring, power for the onboard computer", "1 / aircraft", "$2,000–8,000"],
  ]),
  note("Subtotal per aircraft: $5,800–15,700 one-time."),

  h3sub("Per FBO — shared across every aircraft based there, doesn't repeat per plane"),
  equipmentTable([
    ["Docking stations", "Reads the drive back in at the office", "2 / office", "$200–700"],
  ]),
  note("Subtotal per FBO: $200–700 one-time. A second aircraft at the same FBO does not add this cost again."),

  h3sub("Fleet-wide software — built once, regardless of fleet size"),
  equipmentTable([
    ["Camera software license", "Lets the onboard computer connect to the camera", "1 / fleet", "$0"],
    ["Onboard QC software development", "Camera-SDK integration, per-photo quality checks, coverage-vs-plan logic, checksum/manifest system", "1 (fleet-wide, one-time)", "$40,000–90,000"],
  ]),
  note("Built once and deployed to every aircraft and FBO — does not repeat as the fleet grows."),

  h2("A.2  FBO to Cloud", TEAL),
  equipmentTable([
    ["Office workstation", "Computer that stages the day's data and hosts the upload software", "1 / office", "$1,500–3,500"],
    ["10 TB local drive", "Buffer storage; holds data if the internet link is down", "1 / office", "$300–600"],
    ["10-gigabit network switch", "Network hardware linking docking stations and workstation", "1 / office", "$300–800"],
    ["Data Box Gateway", "Free software that uploads to the cloud and auto-retries on failure", "1 / office", "$0"],
    ["Internet circuit (1 Gbps)", "Carries the upload to the cloud", "1 / office", "$1,200/mo"],
    ["Cloud staging storage", "Holds raw images in the cloud while they wait to be processed", "usage-based", "~$260/mo"],
    ["Gateway setup & ingest automation", "Configures Data Box Gateway, upload verification, monitoring/alerting", "1 (one-time)", "$4,000–12,000"],
  ]),

  h2("A.3  Cloud to Delivery", TEAL),
  equipmentTable([
    ["Image conversion — 150 MP", "Converts raw camera files into working images. Real codebase (private GitHub repo); core conversion, geometric correction, and ICC embedding proven on production imagery. Native SDK sharpening and a clarity feature remain to be built/tuned. Cost derived from measured processing time (25–35 s/image) × this project's real total (215,000 images) — not yet a live production bill", "215,000 img / project", "$1,226–1,699 / project (~$409–566/mo)"],
    ["Image conversion — 250 MP", "Same conversion step on the higher-resolution camera. Per-image time extrapolated (not measured) from the 150→250 MP pixel ratio (1.63×); this project's real total is 37% fewer images, but total pixel volume is within ~2.5% of the 150 MP case, so cost comes out nearly identical", "135,000 img / project", "$1,254–1,744 / project (~$418–581/mo)"],
    ["Cloud pipeline integration", "Validates SDK sharpening, adds the clarity feature, strips debug/test code, and wires the already-dockerized conversion pipeline into mosaic → GDAL → publish end to end", "1 (one-time)", "$12,000–30,000"],
    ["Orthomosaic software license", "Stitches converted images into a seamless map; usage-based, no cap on capacity", "1 / org", "$1,597/mo base + $0.05/processing-hr"],
    ["Orthomosaic & file-finishing compute", "Cloud virtual machines that run the stitching and finishing steps; scale to zero when idle", "usage-based", "~$575/mo"],
    ["Image server", "Publishes finished imagery so it can be viewed and delivered", "1", "~$896/mo"],
    ["Web security gateway", "Protects and fronts the image server", "1", "~$437/mo"],
    ["Delivery storage & content delivery", "Stores and serves finished imagery to customers", "shared account", "~$1,457/mo"],
  ]),

  h2("A.4  Notes on Figures", TEAL),
  bullet("Image-server, gateway, and compute figures are the cloud provider's current metered rates for this workload"),
  bullet("Delivery storage is a shared-account rate, not isolated to this pipeline"),
  bullet("All equipment above is priced as new procurement — no reuse of existing hardware is assumed"),
  bullet("Development figures are rough engineering estimates pending real scoping"),
  bullet("Image conversion's remaining scope was re-costed against a real, private codebase (pi-1000-imageconverter) rather than a from-scratch estimate — it already runs and has build/run Docker environments defined"),
  bullet("Image conversion's cost is derived (measured 25–35 s/image × the same VM rate used elsewhere in this pipeline × this project's real image totals — 215,000 for 150 MP, 135,000 for 250 MP), not a live production bill. See the companion Cost & Timeline document's process-time and volume comparisons for the full 150 MP vs. 250 MP breakdown. Converting one sortie (~3,171 images, 150 MP) serially takes ~22–31 hours on a single instance — production needs roughly 11–16 parallel instances to clear a sortie in ~2 hours (cost is essentially unchanged by how many instances share the work; parallelism buys turnaround time, not savings)"),
];

writeDoc(buildDocument("RGB Imagery Pipeline — Cloud Migration · Upgrade Plan", children), "RGB_Pipeline_Upgrade_Plan.docx");
