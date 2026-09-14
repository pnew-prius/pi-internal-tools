const {
  NAVY, TEAL, AMBER, RUST, MUTED, USABLE, PageBreak,
  docTitle, statRow, h1, h2, h3sub, body, bullet, note,
  equipmentTable, buildDocument, writeDoc,
} = require("./docx_helpers");
const { Paragraph } = require("docx");

const children = [
  ...docTitle(
    "RGB Minimal Touch Upgrade Road Map",
    "Architecture, Capabilities & Equipment",
    "13 September 2026",
    "Scope",
    "Aircraft capture through customer delivery — three legs, one project's AOI, collected & delivered quarterly"
  ),

  statRow([
    { number: "3", label: "Pipeline legs — Collection, FBO, Cloud", color: NAVY },
    { number: "8", label: "Gaps to close to reach finished state", color: TEAL },
    { number: "Built", label: "Image conversion — core proven, tuning + orchestration remain", color: MUTED },
    { number: "$88,100–213,300", label: "Total one-time equipment & build cost (Appendix A)", color: AMBER },
  ]),

  h2("Key Notes", NAVY),
  bullet("This document covers what's being built and why, leg by leg, plus the itemized one-time equipment and build costs behind each leg. Recurring operating costs, flight-collection costs, and processing turnaround — all steady-state, post-upgrade figures — live in the companion Quarterly Permian Collection — Costs & Timelines document."),
  bullet("Development figures throughout this document are rough engineering estimates, not vendor quotes — refine before committing budget."),
  bullet("All figures are scoped to this project's AOI (collected and delivered quarterly), not total company operations."),
  bullet("Costs are broken out by what actually scales with what: per-aircraft costs repeat for each additional plane, per-FBO costs repeat only for each additional ground station (one FBO can serve several aircraft), and fleet-wide costs are built once regardless of fleet size."),

  new Paragraph({ spacing: { before: 260 }, children: [] }),

  h1("1", "Work To Be Done — Scope"),
  body("Move RGB aerial-imagery processing off on-premise office workstations and onto cloud infrastructure, in three legs. The architecture below is the general approach for minimal-touch collection to delivery; costs in this document are scoped to one project's AOI, collected and delivered quarterly, and separate what repeats per aircraft from what repeats per FBO — a single FBO can serve several aircraft:"),
  bullet("Collection to FBO — verified capture, in-flight quality checks, and physical transport of raw imagery from the aircraft to the office", { bold: true }),
  bullet("FBO to Cloud — reliable, automated upload of raw imagery from the office into cloud storage", { bold: true }),
  bullet("Cloud to Delivery — EO (trajectory) postprocessing, image conversion, packaging, and orthomosaic stitching, published as an automated web service, entirely on cloud infrastructure", { bold: true }),

  h1("2", "Finished State Capabilities"),
  bullet("Photo quality is checked in flight — a bad flight line is caught and re-flown the same sortie"),
  bullet("Every image is checksummed at capture and verified at each handoff — a complete chain of custody from aircraft to cloud"),
  bullet("Aircraft turn around in minutes using swappable drive modules — no waiting on a copy"),
  bullet("Raw imagery uploads from the office to the cloud automatically, recovering on its own from any interruption"),
  bullet("Raw-image conversion, EO (trajectory) postprocessing, geospatial packaging, orthomosaic stitching, and file finishing all run on cloud compute that scales to zero between flights"),
  bullet("New projects' imagery is automatically published as a GeoServer web service — no manual workspace/layer setup"),
  bullet("Finished imagery is published and delivered to customers without manual handling — delivery itself via the Mercator platform's Data Portal, outside this document's scope"),

  h1("3", "Current State Capabilities"),
  bullet("Orthomosaic stitching and file finishing already run on cloud compute — operating today"),
  bullet("The imagery server already publishes finished imagery — operating today"),
  bullet("Image capture handling, in-flight quality checking, drive management, converting raw camera files into working images, EO (trajectory) postprocessing, and packaging remain manual, on-premise steps on office workstations", { color: RUST }),
  bullet("GeoServer web-service creation is manual today — requires direct GeoServer access, not available via automated REST calls", { color: RUST }),
  bullet("Customer delivery is not in place — getting finished imagery to customers is a manual process today, not an automated handoff", { color: RUST }),
  note("Customer-facing, self-service delivery is being built separately as the Data Portal track of the Mercator platform — out of scope for this document. This roadmap covers Collection through publishing on the image server; it does not include a delivery build."),

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
  bullet("EO (trajectory) postprocessing still runs manually on desktop POSPac software — not yet relocated to the cloud or wired into the automated pipeline"),
  bullet("Packaging — assembling converted images and GPS/trajectory data into the processing package that feeds mosaic — is still a manual, on-prem step"),
  bullet("GeoServer web-service creation (workspace/layer/store per project) is still manual — no automation exists to publish new imagery as a service"),
  note("Customer delivery itself is a separate gap, owned by the Mercator platform's Data Portal track — not counted among this document's gaps or costs."),

  new Paragraph({ children: [new PageBreak()] }),
  h1("A", "Appendix — Technical Addendum"),
  body("One-time equipment, installation, and build costs underlying the upgrade, by pipeline leg — what it takes to reach finished state. Recurring operating costs, once the upgrade is live and running, are itemized in the companion Quarterly Permian Collection — Costs & Timelines document, not here. Each item below is labeled by what it scales with: per aircraft, per FBO (one FBO can serve several aircraft), or fleet-wide (built once regardless of fleet size)."),

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
  body("Per FBO — repeats for each additional ground station; a second aircraft based at the same FBO does not add this cost again:"),
  equipmentTable([
    ["Office workstation", "Computer that stages the day's data and hosts the upload software", "1 / office", "$1,500–3,500"],
    ["10 TB local drive", "Buffer storage; holds data if the internet link is down", "1 / office", "$300–600"],
    ["10-gigabit network switch", "Network hardware linking docking stations and workstation", "1 / office", "$300–800"],
    ["Data Box Gateway", "Free software that uploads to the cloud and auto-retries on failure", "1 / office", "$0"],
    ["Gateway setup & ingest automation", "Configures Data Box Gateway, upload verification, monitoring/alerting", "1 / office", "$4,000–12,000"],
  ]),
  note("Subtotal per FBO: $6,100–16,900 one-time. The internet circuit and cloud staging storage this gateway runs on are recurring operating costs — itemized in the companion Quarterly Permian Collection — Costs & Timelines document, not here."),

  h2("A.3  Cloud to Delivery", TEAL),
  body("Fleet-wide — built once in the cloud, regardless of aircraft or FBO count. Image conversion, orthomosaic processing, and delivery hosting are recurring, usage-based cloud services once the pipeline is live — itemized with the rest of steady-state operating cost in the companion Quarterly Permian Collection — Costs & Timelines document. The build costs on this leg are the integration and automation work to wire the pieces together:"),
  equipmentTable([
    ["Cloud pipeline integration", "Validates SDK sharpening, adds the clarity feature, strips debug/test code, and wires the already-dockerized conversion pipeline into mosaic → GDAL → publish end to end", "1 (fleet-wide, one-time)", "$12,000–30,000"],
    ["EO postprocessing — VM setup", "Stands up an Azure Windows Server VM and installs/configures the existing POSPac MMS + PP-RTX license for headless batch operation, assuming the license relocates seamlessly", "1 (fleet-wide, one-time)", "$2,000–5,000"],
    ["EO postprocessing — automation", "Builds automation around POSPacBatch.exe: feeds each sortie's GNSS/IMU log, retrieves and validates the trajectory output, wires it into the pipeline", "1 (fleet-wide, one-time)", "$8,000–20,000"],
    ["Geospatial packaging automation", "Automates producing today's package format (converted images + GPS/trajectory data as a zip) from cloud-landed data, triggering the existing One-Button Mosaic pipe the same way the current manual upload does", "1 (fleet-wide, one-time)", "$8,000–20,000"],
    ["GeoServer web-service automation", "Builds REST API automation to create a workspace/layer/store/style per project, running inside the VNet alongside GeoServer, triggered when new processed imagery lands", "1 (fleet-wide, one-time)", "$6,000–15,000"],
  ]),
  note("Subtotal, Cloud to Delivery: $36,000–90,000 one-time, fleet-wide — doesn't repeat per aircraft or per FBO."),

  h2("A.4  Notes on Figures", TEAL),
  bullet("All equipment above is priced as new procurement — no reuse of existing hardware is assumed"),
  bullet("Development figures are rough engineering estimates pending real scoping"),
  bullet("Image conversion's remaining scope was re-costed against a real, private codebase (pi-1000-imageconverter) rather than a from-scratch estimate — it already runs and has build/run Docker environments defined"),
  bullet("GeoServer web-service automation is scoped lower than the other new items because working REST-API connection code against this exact GeoServer instance already exists (geoserver_seed_cost.py, gsd_cost_table.py) — not a from-scratch integration"),
];

writeDoc(buildDocument("RGB Minimal Touch Upgrade Road Map", children), "RGB_Minimal_Touch_Upgrade_Road_Map.docx");
