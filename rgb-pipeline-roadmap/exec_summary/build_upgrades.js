const {
  NAVY, TEAL, AMBER, RUST, MUTED, USABLE, PageBreak,
  docTitle, statRow, h1, h2, h3sub, body, bullet, note,
  equipmentTable, compareTable, costTable, buildDocument, writeDoc,
} = require("./docx_helpers");
const { Paragraph, AlignmentType } = require("docx");

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
    { number: "$88,100–213,300", label: "Capital cost to build", color: AMBER },
    { number: "~$6,830–6,990/mo", label: "Ongoing equipment & cloud cost", color: MUTED },
  ]),

  h1("1", "Work To Be Done — Scope"),
  body("Move RGB aerial-imagery processing off on-premise office workstations and onto cloud infrastructure, in three legs:"),
  bullet("Collection to FBO — verified capture, in-flight quality checks, and physical transport of raw imagery from the aircraft to the office", { bold: true }),
  bullet("FBO to Cloud — reliable, automated upload of raw imagery from the office into cloud storage", { bold: true }),
  bullet("Cloud to Delivery — turning raw imagery into finished, ready-to-view maps and publishing them online automatically, entirely on cloud infrastructure", { bold: true }),

  h1("2", "Finished State Capabilities"),
  bullet("Photo quality is checked in flight — a bad flight line is caught and re-flown the same sortie"),
  bullet("Every image is checksummed at capture and verified at each handoff — a complete chain of custody from aircraft to cloud"),
  bullet("Aircraft turn around in minutes using swappable drive modules — no waiting on a copy"),
  bullet("Raw imagery uploads from the office to the cloud automatically, recovering on its own from any interruption"),
  bullet("Converting, correcting, and stitching imagery into finished maps all run on cloud computers that turn off automatically when not in use"),
  bullet("Each new project's imagery is automatically published online — no manual setup required"),
  bullet("Finished imagery is published and delivered to customers without manual handling — delivery itself via the Mercator platform's Data Portal"),

  h1("3", "Current State Capabilities"),
  bullet("Orthomosaic stitching and file finishing already run on cloud compute — operating today"),
  bullet("The imagery server already publishes finished imagery — operating today"),
  bullet("Image capture handling, in-flight quality checking, drive management, converting raw camera files into working images, correcting flight-position data, and bundling files for the next step remain manual, on-premise steps on office workstations", { color: RUST }),
  bullet("Publishing a new project's imagery online is manual today — someone has to set it up by hand", { color: RUST }),
  bullet("Customer delivery is not in place — getting finished imagery to customers is a manual process today, not an automated handoff", { color: RUST }),
  note("Customer-facing, self-service delivery is being built separately as the Data Portal track of the Mercator platform."),

  h1("4", "Gaps"),
  body("Correlated to the three legs in Section 1:"),
  h2("Collection to FBO", TEAL),
  bullet("No onboard quality-check device"),
  bullet("No verified, swappable-drive capture system"),
  h2("FBO to Cloud", TEAL),
  bullet("No automated, self-healing upload pipeline from the office into the cloud"),
  h2("Cloud to Delivery", TEAL),
  bullet("The image-conversion software already works for the basics, proven on real project imagery — a couple of picture-quality refinements still need to be finished"),
  bullet("No automated connection from where raw imagery lands in the cloud, through conversion, into the existing stitching and finishing steps"),
  bullet("Correcting flight-position data (from GPS/inertial sensors) still happens manually on desktop software — not yet moved to the cloud or automated"),
  bullet("Bundling processed images and flight data together for the next processing step is still done by hand"),
  bullet("Publishing each new project's imagery online is still manual — nothing does this automatically yet"),
  note("Customer delivery itself is a separate gap, owned by the Mercator platform's Data Portal track."),

  h1("5", "Resources"),
  body("Roles needed to close the gaps above."),
  compareTable(
    ["Role", "Responsible for"],
    [
      ["Embedded Software Engineer", "Builds the onboard camera and quality-check software"],
      ["Cloud / DevOps Engineer", "Automates the cloud upload, sets up cloud servers, and monitors everything"],
      ["Systems Integration Engineer", "Finishes the image-processing software and connects every automated step into one pipeline"],
      ["Avionics Installation Technician", "Installs and wires the onboard equipment on each aircraft"],
    ],
    [3200, 6160],
    [AlignmentType.LEFT, AlignmentType.LEFT]
  ),
  note("Rates and total hours are not yet scoped."),

  h1("6", "Cost"),
  body("Capital and ongoing cost, by leg."),
  costTable(),
  note("*Ongoing cost here is equipment and cloud operating cost only — internet circuit, cloud storage, image processing, hosting. It does not include flight operations (crew, fuel, aircraft time); that cost is tracked separately in the companion Quarterly Permian Collection — Costs & Timelines document."),
  note("Collection to FBO isn't one number — it's an aircraft cost plus a ground-station cost, and one ground station can support several aircraft. FBO to Cloud is a ground-station cost too. Cloud to Delivery is a single cloud-side cost that doesn't repeat no matter how many aircraft or ground stations you add. Full technical detail and itemized pricing are in Appendix A."),

  new Paragraph({ children: [new PageBreak()] }),
  h1("A", "Appendix — Technical Addendum"),
  body("One-time equipment, installation, and build costs underlying the upgrade, by pipeline leg — what it takes to reach finished state, with the specific technologies involved and how each piece works. Recurring operating costs, once the upgrade is live and running, are itemized in the companion Quarterly Permian Collection — Costs & Timelines document, not here. Each item below is labeled by what it scales with: per aircraft, per FBO (one FBO can serve several aircraft), or fleet-wide (built once regardless of fleet size)."),

  h2("A.1  Collection to FBO", TEAL),
  body("This document assumes 1 aircraft and 1 FBO. Split below by what actually scales with what — an additional aircraft at the same FBO repeats only the per-aircraft rows; an additional FBO (serving any number of aircraft) repeats only the per-FBO rows; the software rows are built once, fleet-wide, and never repeat."),

  h3sub("Per aircraft — repeats for each additional plane"),
  equipmentTable([
    ["Onboard edge computer", "Ruggedized computer on the aircraft; checks each photo for quality — blur, exposure, coverage gaps — as it's taken; saves photos to a drive with a checksum (e.g., a fanless industrial PC, x86 or ARM, running Linux)", "1 / aircraft", "$2,000–4,000"],
    ["Camera-to-computer cabling", "Connects the camera to the onboard computer (e.g., 10GBASE-T copper or SFP+ fiber, matching the camera's native 10G Ethernet port)", "1 / aircraft", "$200–500"],
    ["Removable NVMe drives", "Swappable drives; full drive out, blank drive in after landing (e.g., U.2 or M.2 NVMe in a hot-swap carrier/sled)", "4 / aircraft", "$1,600–3,200"],
    ["Aircraft installation", "Mounting, wiring, power for the onboard computer", "1 / aircraft", "$2,000–8,000"],
  ]),
  note("Subtotal per aircraft: $5,800–15,700 one-time."),

  h3sub("Per FBO — shared across every aircraft based there, doesn't repeat per plane"),
  equipmentTable([
    ["Docking stations", "Reads the drive back in at the office (e.g., a USB-C or Thunderbolt NVMe dock matching the drive's carrier)", "2 / office", "$200–700"],
  ]),
  note("Subtotal per FBO: $200–700 one-time. A second aircraft at the same FBO does not add this cost again."),

  h3sub("Fleet-wide software — built once, regardless of fleet size"),
  equipmentTable([
    ["Camera software license", "Lets the onboard computer connect to the camera", "1 / fleet", "$0"],
    ["Onboard QC software development", "Camera-SDK integration (Phase One capture SDK over 10G Ethernet), per-photo quality checks against the ~2–5 MP embedded preview, coverage-vs-flight-plan logic, checksum/manifest system", "1 (fleet-wide, one-time)", "$40,000–90,000"],
  ]),
  note("Built once and deployed to every aircraft and FBO — does not repeat as the fleet grows."),

  h2("A.2  FBO to Cloud", TEAL),
  body("Per FBO — repeats for each additional ground station; a second aircraft based at the same FBO does not add this cost again:"),
  equipmentTable([
    ["Office workstation", "Computer that stages the day's data and hosts the upload software (e.g., a workstation-class PC with a 10-gigabit NIC and enough local disk to buffer a full sortie)", "1 / office", "$1,500–3,500"],
    ["10 TB local drive", "Buffer storage; holds data if the internet link is down (e.g., a NAS or direct-attached RAID array)", "1 / office", "$300–600"],
    ["10-gigabit network switch", "Network hardware linking docking stations and workstation (e.g., a managed switch with SFP+ or 10GBASE-T ports)", "1 / office", "$300–800"],
    ["Data Box Gateway", "Free software that uploads to the cloud and auto-retries on failure", "1 / office", "$0"],
    ["Gateway setup & ingest automation", "Configures Data Box Gateway, upload verification, monitoring/alerting (e.g., Azure Monitor alerts on a stalled or failed transfer)", "1 / office", "$4,000–12,000"],
  ]),
  note("Subtotal per FBO: $6,100–16,900 one-time. The internet circuit and cloud staging storage this gateway runs on are recurring operating costs — itemized in the companion Quarterly Permian Collection — Costs & Timelines document, not here."),

  h2("A.3  Cloud to Delivery", TEAL),
  body("Fleet-wide — built once in the cloud, regardless of aircraft or FBO count. Image conversion, orthomosaic processing, and delivery hosting are recurring, usage-based cloud services once the pipeline is live — itemized with the rest of steady-state operating cost in the companion Quarterly Permian Collection — Costs & Timelines document. The build costs on this leg are the integration and automation work to wire the pieces together:"),
  equipmentTable([
    ["Cloud pipeline integration", "Validates SDK sharpening, adds the clarity feature, strips debug/test code, and wires the already-dockerized conversion pipeline (Phase One Image SDK, C++) into mosaic → GDAL → publish end to end", "1 (fleet-wide, one-time)", "$12,000–30,000"],
    ["EO postprocessing — VM setup", "Stands up an Azure Windows Server VM and installs/configures the existing POSPac MMS + PP-RTX license for headless batch operation via POSPacBatch.exe, assuming the license relocates seamlessly", "1 (fleet-wide, one-time)", "$2,000–5,000"],
    ["EO postprocessing — automation", "Builds automation around POSPacBatch.exe (Applanix POSPac MMS batch command-line mode): feeds each sortie's GNSS/IMU log, retrieves and validates the trajectory (EO) output, wires it into the pipeline", "1 (fleet-wide, one-time)", "$8,000–20,000"],
    ["Geospatial packaging automation", "Automates producing today's package format (converted images + GPS/trajectory CSV + KML + metadata.json, zipped) from cloud-landed data, triggering the existing One-Button Mosaic pipe the same way the current manual upload does", "1 (fleet-wide, one-time)", "$8,000–20,000"],
    ["GeoServer web-service automation", "Builds automation against the GeoServer REST API to create a workspace/coverage store/layer/style per project (exposed as WMS/WMTS), running inside the Azure VNet alongside the GeoServer VM, triggered when new processed imagery lands", "1 (fleet-wide, one-time)", "$6,000–15,000"],
  ]),
  note("Subtotal, Cloud to Delivery: $36,000–90,000 one-time, fleet-wide — doesn't repeat per aircraft or per FBO."),

  h3sub("How the new automation works"),
  bullet("EO postprocessing: an Azure-hosted Windows VM runs Applanix POSPac MMS headlessly via POSPacBatch.exe, consuming each sortie's raw GNSS/IMU log plus PP-RTX correction, and producing the trajectory (exterior orientation, or EO) file the mosaic step needs"),
  bullet("Packaging: a small cloud service watches for a sortie's converted images and trajectory output to both land, then assembles the same package format already used today — images + GPS/trajectory CSV + KML + metadata.json, zipped — and drops it where the existing One-Button Mosaic pipe already expects it"),
  bullet("GeoServer publishing: a cloud service inside the same Azure VNet as the GeoServer VM calls its REST API to create a workspace, coverage store, layer, and style per project and expose it as a WMS/WMTS web service — the same steps done by hand today through the GeoServer web UI"),

  h2("A.4  Notes on Figures", TEAL),
  bullet("All equipment above is priced as new procurement — no reuse of existing hardware is assumed"),
  bullet("Equipment examples (specific interconnects, drive form factors, etc.) are illustrative, not vendor-mandated — any equivalent spec meeting the stated function works"),
  bullet("Image conversion's remaining scope was re-costed against a real, private codebase (pi-1000-imageconverter) rather than a from-scratch estimate — it already runs and has build/run Docker environments defined"),
  bullet("GeoServer web-service automation is scoped lower than the other new items because working REST-API connection code against this exact GeoServer instance already exists (geoserver_seed_cost.py, gsd_cost_table.py) — not a from-scratch integration"),
];

writeDoc(buildDocument("RGB Minimal Touch Upgrade Road Map", children), "RGB_Minimal_Touch_Upgrade_Road_Map.docx");
