const HELPERS_DIR = "C:/Users/pi/claude/pi-internal-tools/rgb-pipeline-roadmap/exec_summary";
const {
  NAVY, TEAL, AMBER, RUST, MUTED,
  docTitle, statRow, h1, h2, h3sub, body, bullet, note,
  equipmentTable, buildDocument, writeDoc,
} = require(HELPERS_DIR + "/docx_helpers");

const children = [
  ...docTitle(
    "RGB/LiDAR Scaling",
    "Hardware / Ingest Pipeline Comparison",
    "1 October 2026",
    "Scope",
    "Physical ingest architecture (aircraft to Azure), drive/dock hardware, and existing Azure infrastructure discovered along the way. Sub-report of the comprehensive RGB/LiDAR Scaling exec summary."
  ),

  statRow([
    { number: "1,000 Mbps", label: "Confirmed office uplink — not the bottleneck", color: NAVY },
    { number: "2 designs", label: "Unreconciled ingest architectures on record", color: AMBER },
    { number: "LiDAR", label: "Workflow never described — open gap", color: RUST },
  ]),

  h2("Status: LiDAR Never Designed", NAVY),
  body("Both source sessions are RGB-only. The earlier session asked for the LiDAR-equivalent workflow (sensor/drive source, local processing, deliverable format) to design its Azure path; the user deferred to RGB first and LiDAR was never revisited. This is a real gap — LiDAR-specific hardware content cannot be written until that workflow description is gathered."),

  h1("1", "Current RGB Physical Workflow"),
  body("Aircraft laptop (writes images + IMU during flight) → external drive (Samsung T-series, plugged in after landing) → sneakernet (drive walked from plane to ground machine) → physical machine. Two known failure modes: drives disconnecting mid-transfer (\"going dark\"), and no way to tell which drives are cleared."),
  note("Correction found during research: the Samsung T-series in current use is USB 3.2 Gen 2x2 (20 Gbps), not actually Thunderbolt as originally assumed."),

  h1("2", "Design A — Dedicated Ingestion Workstation + Physical Drive Dock"),
  h3sub("Root cause of \"going dark,\" confirmed"),
  body("Windows USB selective suspend — the documented cause in 80–90% of this failure class. Fix: disable USB selective suspend in both power plans, and uncheck \"allow the computer to turn off this device\" on every USB Root Hub. If drops persist, it's a cable/bus-power issue — use only short (\u2264 0.8m) certified cables; note the Samsung T-series is bus-powered and can brown out under sustained transfer on a marginal port."),
  h3sub("Drive-clearance tracking (process fix, not hardware)"),
  bullet("Two-bin physical system: \"not yet offloaded\" / \"cleared.\""),
  bullet("Numbered drive fleet + shared log, so drives aren't used interchangeably."),
  bullet("Clearance gated on a checksum-verified Azure upload — not just \"copied it somewhere.\""),
  h3sub("Recommended hardware"),
  equipmentTable([
    ["Workstation", "Workstation-class board/CPU with several independent Thunderbolt/USB4 controllers at full bandwidth each (Threadripper Pro / Xeon W) — a mainstream desktop board multiplexes 2-3 ports off one shared controller", "1", "TBD"],
    ["OWC ThunderBay 4/8", "Multi-bay Thunderbolt enclosure — each bay gets real independent throughput, unlike a cheap hub", "1+", "TBD"],
    ["NVMe staging array", "RAID 0 / striped, PCIe Gen4/5, decoupled from the upload pipe so reading and uploading don't compete", "1", "TBD"],
    ["10GbE NIC", "Minimum, to avoid the NIC becoming the bottleneck before the office uplink does", "1", "TBD"],
    ["SanDisk Professional PRO-G40", "Field-side drive replacement — true Thunderbolt 3, IP68, 3m drop / 4,000lb crush rated, cooling core", "per aircraft", "TBD"],
  ]),
  note("CalDigit TS4 dock considered and set aside — good single-drive-plus-peripherals dock but only one high-speed bay, not built for reading multiple drives at once."),
  body("Office uplink confirmed: 1,000 Mbps symmetric. At this speed a 100GB flight uploads in ~13 minutes — the network is not the bottleneck, so the design priority is local read parallelism across drives."),
  h3sub("Automation concept"),
  body("A permanent Windows WMI event subscription (Register-CimIndicationEvent on Win32_VolumeChangeEvent) fires a PowerShell script the instant a drive is docked — no polling. Reads a manifest.json written at capture (drive ID, flight date, project code), ignores unrecognized drives, copies via robocopy /Z (restartable), pushes via azcopy (MD5-verified) to raw-ingest/<FlightDate>/<ProjectCode>/<DriveID>/, writes a .cleared flag back to the drive once hash-confirmed, logs to a central audit log, and fires a toast notification to the technician."),

  h1("3", "Design B — Swappable NVMe Modules + Azure Data Box Gateway"),
  body("A later, more integrated design that supersedes Design A's \"carry a drive, run azcopy from a workstation\" model:"),
  bullet("Rugged CPU-only edge computer onboard (Azure Arc-managed Linux), fed every frame live via the Phase One capture SDK (capture/preview only, not the processing SDK). Runs onboard QC on the embedded preview."),
  bullet("Removable/swappable NVMe storage modules (raw IIQ + xxHash64 manifest per frame) — drive pool (4 modules/aircraft) + docking stations (2/office), chosen over a 10G tether so the method is identical at every office."),
  bullet("Azure Data Box Gateway (a VM on the existing FBO workstation, no new hardware) + 10TB local buffer + 1 Gbps fiber → resilient, resumable, encrypted upload."),
  bullet("Custody chain: manifest per frame, verified at every hop, no pipeline entry until Azure landing confirmed, no wipe until verified."),
  bullet("Onboard Starlink (optional): in-flight pre-load of ~11% (150MP) to ~35% (250MP) of a sortie during the flight — not bulk transport, but buys early-arriving flight lines and live QC."),

  h2("Open Item: Not Yet Reconciled", RUST),
  body("Design A and Design B are two different answers to the same problem, two months apart, and the later design's own documentation doesn't explicitly say Design A was superseded — it simply isn't mentioned. Confirm with the user which is the intended build before committing hardware spend. Design A's specific implementation pieces (WMI watcher script, drive-tracking bin/log system, USB-selective-suspend fix) remain useful regardless of which physical architecture is chosen, since Design B doesn't specify its own drive-detection mechanism at the same level of detail."),

  h1("4", "Existing Azure Infrastructure Discovered"),
  body("Found while inventorying what Azure already had, before designing anything new:"),
  equipmentTable([
    ["pi-blobsftp", "Existing blob-backed SFTP server in rg_imageryprocessing_southcentralus — could replace the external-drive-to-physical-machine hop directly. Also flagged separately as having an orphaned disk + public IP costing ~$6/mo while apparently idle", "1", "~$6/mo waste"],
    ["CompareContrast-start-Devops", "Existing Logic App watching a compareandcontrast container, auto-triggers a DevOps pipeline on zip upload — may already be Azure-side plumbing for the contrast-script step. Never confirmed live or reconciled against the current cloud-conversion design", "1", "n/a — status unconfirmed"],
    ["imageproc02", "Confirmed to already have a 1TB data disk attached, removing an assumed \"new disk needed\" cost line. Separately flagged as deallocated/idle while its disks still bill", "1", "~$42/mo waste"],
    ["Azure Bastion", "Pricing pulled live, not yet used in any cost model — Basic $0.19/hr, Standard $0.29/hr", "n/a", "$0.19\u2013$0.29/hr"],
  ]),

  h1("5", "GUI-Only Local Processing Steps (Confirmed)"),
  body("iX Capture (IIQ\u2192JPG) and PosPac (IMU/GPS post-processing) have no CLI/batch mode, confirmed directly with the user. This originally drove an RDP-into-a-cloud-VM design for both steps (via existing Azure Virtual Desktop infrastructure). Partially superseded: a real CLI tool, pi-1000-imageconverter (C++, Phase One Image SDK, free license), has since been built/consolidated for the IIQ\u2192JPEG step, removing the GUI/RDP need there. PosPac's cloud path remains unresolved and still GUI-only."),
];

module.exports = { children };

if (require.main === module) {
  writeDoc(
    buildDocument("RGB/LiDAR Scaling — Hardware Comparison", children),
    "C:\\Users\\pi\\claude\\pi-internal-tools\\rgb-lidar-scaling\\exec_summary\\Hardware_Comparison.docx"
  );
}
