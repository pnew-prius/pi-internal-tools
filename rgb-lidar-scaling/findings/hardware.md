# Hardware / Ingest Pipeline Comparison

Source sessions: "Scaling costs for RGB/LiDAR" (local_a7c459db, 2026-07-14/15 — early ingest-automation
design) and "RGB data processing roadmap" (local_58706f37, 2026-09-09 onward — later, more validated
architecture). The two sessions propose **different physical architectures for the same hop** (aircraft →
ground → Azure) and were never explicitly reconciled — flagged as an open item below, not silently resolved.

## Status: LiDAR — never designed

Both source sessions are RGB-only. The July session opened by asking for the current LiDAR workflow
(sensor/drive source, local processing software, final deliverable format) to design the equivalent Azure
path; the user said "let's focus on RGB first" and LiDAR was never picked back up, here or in the September
roadmap. **This is a real gap, not a finding** — if LiDAR scaling is in scope for the comprehensive report,
the LiDAR-equivalent workflow description needs to be gathered from the user before this section can be
written for LiDAR specifically.

## Current RGB physical workflow (as described by user, July session)

Aircraft laptop (writes images + IMU during flight) → external drive (Samsung T-series, plugged in after
landing) → sneakernet (drive walked from plane to ground physical machine) → physical machine (processing
starts). Two known failure modes: drives disconnecting mid-transfer ("going dark"), and no way to tell which
drives are cleared vs. still need data moved.

**Correction found during research**: the Samsung T-series in current use is USB 3.2 Gen 2x2 (20 Gbps), not
actually Thunderbolt as originally assumed.

## Design A — July session: dedicated ingestion workstation + physical drive dock

- **Root cause of "going dark," confirmed**: Windows USB selective suspend (power-saving), the documented
  cause in 80-90% of this failure class. Two free fixes: disable USB selective suspend in both power plans,
  and uncheck "allow the computer to turn off this device" on every USB Root Hub in Device Manager. If drops
  persist after that, it's a cable/bus-power issue, not the drive — use only short (≤0.8m) certified
  Thunderbolt/USB-C cables, and note the Samsung T-series is bus-powered (no external brick), which can brown
  out under sustained transfer on a marginal port.
- **Drive-clearance tracking (process fix, not hardware)**: two-bin physical system ("not yet offloaded" /
  "cleared"), a numbered drive fleet + shared log so drives aren't used interchangeably, and — the one that
  actually matters — tie "cleared" status to a **checksum-verified Azure upload**, not just "copied it
  somewhere."
- **Recommended hardware** (for a machine built solely to read multiple drives and push to Azure fast):
  - Workstation-class board/CPU with enough PCIe lanes for several *independent* Thunderbolt/USB4
    controllers running at full bandwidth simultaneously (AMD Threadripper Pro / Intel Xeon W) — a mainstream
    desktop board typically multiplexes 2-3 ports off one shared controller, which defeats the purpose.
  - **OWC ThunderBay 4 or 8** multi-bay Thunderbolt enclosure — each bay gets real independent throughput
    (vs. a cheap hub where one drive misbehaving can knock out the others).
  - Local NVMe staging array (RAID 0 / striped, PCIe Gen4/5) as a landing zone, decoupled from the upload
    pipe — `azcopy` uploads from staging as its own stream so drive-reading and uploading don't compete.
  - 10GbE NIC minimum.
  - **SanDisk Professional PRO-G40** as the field-side drive (true Thunderbolt 3, IP68, 3m drop/4,000lb crush
    rated, cooling core) — replaces the Samsung T-series, which is not actually Thunderbolt and is more
    consumer-grade for an aircraft-handling environment.
  - CalDigit TS4 dock considered and set aside — good single-drive-plus-peripherals dock (3× TB4/USB4 ports,
    40Gbps each, 2.5GbE, $399) but only one high-speed bay, not built for reading multiple drives at once.
- **Office uplink confirmed: 1,000 Mbps symmetric** — at this speed a 100GB flight uploads in ~13 minutes;
  the network is not the bottleneck, so the design priority is local read parallelism across drives, not
  fighting an uplink ceiling.
- **Automation concept**: a permanent Windows WMI event subscription
  (`Register-CimIndicationEvent` on `Win32_VolumeChangeEvent`, `EventType=2` for arrival) fires a PowerShell
  script the instant a drive is docked — no polling. Script reads a `manifest.json` written at
  capture (drive ID, flight date, project code — same pattern as Pipe 5's input-zip metadata), ignores
  unrecognized drives, copies via `robocopy /Z` (restartable — a dropped connection resumes instead of
  restarting a 100GB copy), pushes to Azure via `azcopy` (MD5-verified) into a `raw-ingest` container keyed
  `raw-ingest/<FlightDate>/<ProjectCode>/<DriveID>/...`, writes a `.cleared` flag file back onto the physical
  drive once upload is hash-confirmed, logs the result to a central audit log, and fires a toast notification
  (`BurntToast` PowerShell module) to the technician. Drive removal mid-copy is logged distinctly from "never
  touched."

## Design B — September roadmap: swappable NVMe modules + Azure Data Box Gateway

Supersedes Design A's "carry a drive, run azcopy from a workstation" model with a more integrated design:

- Rugged CPU-only edge computer onboard (Azure Arc-managed Linux, ~$2-4k class) fed every frame live via the
  Phase One capture SDK (capture/preview access only — not the processing SDK). Runs onboard QC on the
  embedded preview (exposure, blur, haze, glint, coverage vs. flight plan).
- Removable/swappable NVMe storage modules (raw IIQ + xxHash64 manifest per frame) — a drive pool (4
  modules/aircraft) + docking stations (2/office), chosen deliberately over a 10G tether so the method is
  identical at every office with no airframe connector needed.
- **Azure Data Box Gateway** (a VM on the existing FBO workstation, no new hardware) + 10TB local buffer +
  1 Gbps fiber → resilient, resumable, encrypted upload to `raw-ingest`. This replaces Design A's
  plain-azcopy-from-a-workstation approach with a purpose-built gateway appliance.
- Custody chain: manifest per frame at capture, verified at every hop, no pipeline entry until Azure landing
  is confirmed, no local copy/module wipe until that's verified.
- Onboard Starlink (optional): in-flight pre-load of ~11% (150MP) to ~35% (250MP) of a sortie's data during
  the flight itself — not bulk transport, but buys early-arriving flight lines and live QC/trajectory data.

**Open item — not yet reconciled**: Design A (generic drives + dedicated workstation + WMI automation script)
and Design B (purpose-built swappable modules + Data Box Gateway) are two different answers to the same
problem, two months apart. The roadmap's own "open items" list does not explicitly say Design A was
superseded — it simply doesn't mention it. Confirm with the user which is the intended build before this
section of the comprehensive report states one as "the" design. Design A's specific implementation pieces
(the WMI watcher script, the drive-tracking bin/log system, the USB-selective-suspend root-cause fix) are
useful regardless of which physical architecture is chosen, since Design B doesn't specify its own
drive-detection/automation mechanism at the same level of detail.

## Existing Azure infrastructure discovered (not referenced in the roadmap)

Found while inventorying what Azure already had, before designing anything new — real, already-provisioned
resources that should be checked against the current design rather than re-built from scratch:

- **`pi-blobsftp`** — an existing blob-backed SFTP server already running in
  `rg_imageryprocessing_southcentralus`. Could replace the external-drive-to-physical-machine hop directly.
  Also separately flagged in `project_rgb_cost_intelligence` as having an orphaned disk + public IP costing
  ~$2.94/15 days (~$6/mo) while apparently idle — worth confirming whether it's actually in active use.
- **`CompareContrast-start-Devops`** — an existing Azure Logic App that watches a `compareandcontrast`
  container in the `piimageprocessing` storage account and auto-triggers a DevOps pipeline on zip upload.
  This looks like it may already be Azure-side plumbing for "run the contrast Python script on JPGs" —
  parallel to how Pipe 5/Pipe 12 work. Never confirmed live or reconciled against the roadmap's own
  cloud-conversion design (`pi-1000-imageconverter`), which doesn't mention it.
- **`imageproc02`** — confirmed to already have a 1TB data disk (`imageproc02_datadisk_1`, StandardSSD_LRS)
  attached, removing a "new disk needed" cost line that had been assumed. Separately flagged elsewhere
  (`project_rgb_cost_intelligence`) as deallocated/idle while its disks still bill ~$42/mo — a real,
  actionable cost-saving item unrelated to this scaling work.
- **Azure Bastion pricing** (pulled live, not yet used in any cost model): Basic $0.19/hr, Standard
  $0.29/hr, southcentralus.

## Both local processing steps are GUI-only (confirmed)

iX Capture (IIQ→JPG) and PosPac (IMU/GPS post-processing) have no CLI/batch mode — confirmed directly with
the user. This is why Design B's "move processing to Azure" originally assumed an RDP-into-a-cloud-VM model
(via existing Azure Virtual Desktop infra, `rg_wvd_southcentralus`/`rg_wvd-basic_southcentralus`) for these
two steps specifically. **This has since been partially superseded**: the roadmap later found/consolidated a
real CLI tool, `pi-1000-imageconverter` (C++, Phase One Image SDK, free license), for the IIQ→JPEG step —
removing the need for GUI/RDP access for that one step. PosPac's cloud path remains unresolved and still
GUI-only as of the roadmap's last "open items" list (Applanix APPS service / licensed cloud Windows VM /
Trimble RTX-PP are the three paths under consideration, none selected).
