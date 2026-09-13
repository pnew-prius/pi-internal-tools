const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, BorderStyle, ShadingType, AlignmentType, LevelFormat, convertInchesToTwip,
} = require("docx");

const PAGE_W = 12240, PAGE_H = 15840; // US Letter DXA
const MARGIN = 1440;
const USABLE = PAGE_W - MARGIN * 2; // 9360

function h1(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_1, spacing: { before: 320, after: 160 } });
}
function h2(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_2, spacing: { before: 240, after: 120 } });
}
function p(text, opts = {}) {
  return new Paragraph({ children: [new TextRun({ text, ...opts })], spacing: { after: 120 } });
}
function note(text) {
  return new Paragraph({
    children: [new TextRun({ text, italics: true, color: "555555", size: 20 })],
    spacing: { after: 160 },
  });
}
function bullet(text, level = 0) {
  return new Paragraph({ text, numbering: { reference: "bullets", level }, spacing: { after: 60 } });
}
function cell(text, width, opts = {}) {
  const { bold = false, shade = null, align = AlignmentType.LEFT } = opts;
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: shade ? { type: ShadingType.CLEAR, color: "auto", fill: shade } : undefined,
    children: [new Paragraph({
      alignment: align,
      children: [new TextRun({ text, bold, size: 20 })],
    })],
  });
}
function row(cells) {
  return new TableRow({ children: cells });
}

// ---- Table 1: Resource reuse vs new resources ----
const t1Widths = [2500, 1500, 5360];
const resourceTable = new Table({
  width: { size: USABLE, type: WidthType.DXA },
  columnWidths: t1Widths,
  rows: [
    row([
      cell("Resource", t1Widths[0], { bold: true, shade: "D9D9D9" }),
      cell("Status", t1Widths[1], { bold: true, shade: "D9D9D9" }),
      cell("Role in target architecture", t1Widths[2], { bold: true, shade: "D9D9D9" }),
    ]),
    row([cell("imageproc-vmss (Pipe 5)", t1Widths[0]), cell("Reused as-is", t1Widths[1]), cell("One-Button Mosaic, unchanged, event-triggered off tobeprocessed", t1Widths[2])]),
    row([cell("gdalproc-vmss (Pipe 12)", t1Widths[0]), cell("Reused as-is", t1Widths[1]), cell("GDAL merge/trim, unchanged, event-triggered off gdal-processing", t1Widths[2])]),
    row([cell("CompareContrast-start-Devops", t1Widths[0]), cell("Reused (in dev)", t1Widths[1]), cell("Azure-side contrast correction; already in development, adopted as-is once complete", t1Widths[2])]),
    row([cell("imageproc02", t1Widths[0]), cell("Repurposed", t1Widths[1]), cell("Idle Standard_F16s_v2 Windows VM with an existing unattached 1TB data disk (imageproc02_datadisk_1) — hosts iX Capture + PosPac, technician connects via RDP/Bastion", t1Widths[2])]),
    row([cell("pi-blobsftp", t1Widths[0]), cell("Reused as-is", t1Widths[1]), cell("Existing SFTP→blob gateway, candidate path for raw ingestion uploads", t1Widths[2])]),
    row([cell("piimageprocessing storage", t1Widths[0]), cell("Reused as-is", t1Widths[1]), cell("Existing storage account; gains one new container (raw-ingest)", t1Widths[2])]),
    row([cell("raw-ingest container", t1Widths[0]), cell("New", t1Widths[1]), cell("Landing zone for raw IIQ + IMU/GPS trajectory files uploaded from the ingest server", t1Widths[2])]),
    row([cell("Azure Bastion", t1Widths[0]), cell("New", t1Widths[1]), cell("Secure remote access to imageproc02 in place of open RDP", t1Widths[2])]),
  ],
});

// ---- Table 2: Cost components per tile ----
const t2Widths = [3600, 2760, 3000];
const componentTable = new Table({
  width: { size: USABLE, type: WidthType.DXA },
  columnWidths: t2Widths,
  rows: [
    row([
      cell("Component", t2Widths[0], { bold: true, shade: "D9D9D9" }),
      cell("Basis", t2Widths[1], { bold: true, shade: "D9D9D9" }),
      cell("Cost per tile", t2Widths[2], { bold: true, shade: "D9D9D9", align: AlignmentType.RIGHT }),
    ]),
    row([cell("Pipe 5 / Pipe 12 (existing)", t2Widths[0]), cell("13-tile historical average, pipeline_runs.json", t2Widths[1]), cell("$22.54", t2Widths[2], { align: AlignmentType.RIGHT })]),
    row([cell("imageproc02 processing compute (new)", t2Widths[0]), cell("$0.816/hr × ~3.5 hrs (estimate)", t2Widths[1]), cell("$2.86", t2Widths[2], { align: AlignmentType.RIGHT })]),
    row([cell("Azure Bastion access (new)", t2Widths[0]), cell("$0.19/hr (Basic) × ~3.5 hrs", t2Widths[1]), cell("$0.67", t2Widths[2], { align: AlignmentType.RIGHT })]),
    row([cell("raw-ingest blob storage (new)", t2Widths[0]), cell("$0.018/GB-mo × 50–100GB × 1-mo retention", t2Widths[1]), cell("$0.90 – $1.80", t2Widths[2], { align: AlignmentType.RIGHT })]),
    row([cell("Total, new Azure spend", t2Widths[0], { bold: true }), cell("", t2Widths[1]), cell("$4.43 – $5.33", t2Widths[2], { bold: true, align: AlignmentType.RIGHT })]),
    row([cell("Total, all-in per tile", t2Widths[0], { bold: true }), cell("", t2Widths[1]), cell("$26.97 – $27.87", t2Widths[2], { bold: true, align: AlignmentType.RIGHT })]),
  ],
});

// ---- Table 3: Scaling scenarios ----
const t3Widths = [2200, 1500, 1900, 1900, 1860];
const scalingTable = new Table({
  width: { size: USABLE, type: WidthType.DXA },
  columnWidths: t3Widths,
  rows: [
    row([
      cell("Scenario", t3Widths[0], { bold: true, shade: "D9D9D9" }),
      cell("Tiles/mo", t3Widths[1], { bold: true, shade: "D9D9D9", align: AlignmentType.RIGHT }),
      cell("Existing (Pipe 5/12)", t3Widths[2], { bold: true, shade: "D9D9D9", align: AlignmentType.RIGHT }),
      cell("New Azure spend", t3Widths[3], { bold: true, shade: "D9D9D9", align: AlignmentType.RIGHT }),
      cell("Total/mo", t3Widths[4], { bold: true, shade: "D9D9D9", align: AlignmentType.RIGHT }),
    ]),
    row([cell("1× (current pace)", t3Widths[0]), cell("13", t3Widths[1], { align: AlignmentType.RIGHT }), cell("$293.02", t3Widths[2], { align: AlignmentType.RIGHT }), cell("$57.47 – $69.17", t3Widths[3], { align: AlignmentType.RIGHT }), cell("$350.49 – $362.19", t3Widths[4], { align: AlignmentType.RIGHT })]),
    row([cell("2×", t3Widths[0]), cell("26", t3Widths[1], { align: AlignmentType.RIGHT }), cell("$586.04", t3Widths[2], { align: AlignmentType.RIGHT }), cell("$114.95 – $138.35", t3Widths[3], { align: AlignmentType.RIGHT }), cell("$700.99 – $724.39", t3Widths[4], { align: AlignmentType.RIGHT })]),
    row([cell("4×", t3Widths[0]), cell("52", t3Widths[1], { align: AlignmentType.RIGHT }), cell("$1,172.08", t3Widths[2], { align: AlignmentType.RIGHT }), cell("$229.89 – $276.69", t3Widths[3], { align: AlignmentType.RIGHT }), cell("$1,401.97 – $1,448.77", t3Widths[4], { align: AlignmentType.RIGHT })]),
  ],
});

const doc = new Document({
  numbering: {
    config: [{
      reference: "bullets",
      levels: [
        { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 480, hanging: 260 } } } },
        { level: 1, format: LevelFormat.BULLET, text: "◦", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 900, hanging: 260 } } } },
      ],
    }],
  },
  sections: [{
    properties: { page: { size: { width: PAGE_W, height: PAGE_H }, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } } },
    children: [
      new Paragraph({ text: "RGB Workflow → Azure Migration Model", heading: HeadingLevel.TITLE, spacing: { after: 80 } }),
      new Paragraph({ children: [new TextRun({ text: "Prius Intelli LLC — COPECODE26 pipeline", italics: true, size: 24 })], spacing: { after: 40 } }),
      new Paragraph({ children: [new TextRun({ text: "Design document and scaling cost model — no Azure resources created or modified in this pass", size: 20, color: "555555" })], spacing: { after: 320 } }),

      h1("Executive Summary"),
      p("The RGB imagery pipeline is currently split between manual, GUI-only processing on a physical machine (Phase One iX Capture and Trimble/Applanix PosPac) and existing Azure automation (One-Button Mosaic / Pipe 5, GDAL merge-trim / Pipe 12). This document proposes a target architecture that moves the remaining manual steps into Azure by repurposing an already-idle VM, adds an automated drive-detection and ingest pipeline to address two operational pain points (drives disconnecting mid-transfer, and no reliable tracking of which field drives are cleared), and projects scaling costs across three flight-volume scenarios."),
      note("This pass covers design and cost projection only. No PowerShell/Bicep deployment scripts were written and no Azure resources were created or modified — explicitly scoped by the customer."),

      h1("Current State"),
      h2("Field & Ground Workflow (Physical)"),
      bullet("In-flight: onboard aircraft laptop collects images + IMU data during the flight."),
      bullet("Post-flight: data copied from the laptop to an external drive (currently a Samsung T-series drive, USB 3.2 — not true Thunderbolt)."),
      bullet("The drive is carried by hand from the aircraft to the ground physical machine, then copied drive → physical machine."),
      bullet("IIQ (Phase One raw) → JPEG via iX Capture — manual, GUI-only, no CLI/batch mode."),
      bullet("Contrast-correction Python script run on the JPEGs."),
      bullet("IMU/GPS post-processing via PosPac — manual, GUI-only, separate application from iX Capture, no batch mode."),
      bullet("Images + GPS data packaged into a zip and uploaded to the tobeprocessed container, which triggers Pipe 5."),

      h2("Known Issues"),
      bullet("Drives disconnecting mid-transfer at the physical machine (“going dark”) — most likely Windows USB selective-suspend power management, the documented root cause in roughly 80–90% of similar cases."),
      bullet("No reliable way to tell which drives have already been offloaded versus which still need transfer, creating risk of skipped or duplicate transfers."),

      h2("Existing Azure Pipeline (reused as-is)"),
      bullet("imageproc-vmss — Pipe 5, One-Button Mosaic, Standard_F16s_v2, triggered by blob upload to tobeprocessed."),
      bullet("gdalproc-vmss — Pipe 12, GDAL merge/trim, Standard_D16ds_v4, triggered by blob upload to gdal-processing."),
      bullet("CompareContrast-start-Devops — an Azure-side version of the contrast-correction step, currently in development, triggered by zip upload to the compareandcontrast container."),
      bullet("piimageprocessing storage account — containers: blobsftp, compareandcontrast, gdal-processing, mosaicing-sensorpixelsize, software, tobeprocessed."),
      bullet("imageproc02 — an idle Standard_F16s_v2 Windows VM with an existing but unattached 1TB StandardSSD_LRS data disk (imageproc02_datadisk_1), confirmed unused — the strongest reuse candidate for the relocated processing steps."),
      bullet("pi-blobsftp — existing Linux SFTP→blob gateway, a candidate ingestion path."),

      h1("Target Architecture"),
      h2("1. Physical Hardware Chain"),
      p("Flight laptop → field drive → Thunderbolt hub (ground station) → ingest server (local NVMe staging + 10GbE). The physical hand-off cannot be virtualized — a real machine must still read the drive — but everything downstream of that hand-off can move to Azure."),

      h2("2. Automated Ingest Pipeline (triggered on drive arrival)"),
      p("A PowerShell background watcher registered on a WMI Win32_VolumeChangeEvent fires the instant a drive mounts — no polling, no human has to notice."),
      bullet("Identify & validate — reads a manifest.json on the drive (drive ID, flight date, project code) to confirm it is a known field drive; unrecognized volumes are ignored."),
      bullet("Categorize by date — uses the flight date embedded in the manifest, not file modified/created timestamps, which can be inconsistent after multiple copy hops."),
      bullet("Copy to staging — robocopy /Z (restartable) into a date/project/drive folder structure on local NVMe; a mid-copy disconnect resumes instead of restarting."),
      bullet("Upload to Azure — azcopy pushes the same folder structure into the new raw-ingest container as a blob prefix (raw-ingest/<FlightDate>/<ProjectCode>/<DriveID>/...)."),
      bullet("Verify — MD5 checksum, local staging versus the uploaded blob."),
      bullet("Mark cleared — writes a .cleared flag with timestamp back onto the physical drive and safely ejects it, so the drive itself carries proof of its own status."),
      bullet("Log + notify — appends drive ID/date/project/status to a central audit log and raises a toast notification telling the technician the drive is safe to reuse."),

      h2("3. IIQ → JPG + IMU/GPS Processing"),
      p("imageproc02 is repurposed to host iX Capture and PosPac; the technician connects via RDP/Bastion instead of sitting at the local machine. The VM’s existing 1TB data disk is reused — no new disk purchase required."),

      h2("4. Packaging, Handoff & Downstream"),
      p("A PowerShell script on imageproc02 zips the iX Capture/PosPac output and uploads it to the compareandcontrast container, picked up automatically by the existing (in-development) CompareContrast pipeline. From there, output flows into tobeprocessed → Pipe 5 → Pipe 12 exactly as today, unchanged."),

      h2("5. Phase 2 (future work, not committed)"),
      p("Investigate UI-automation scripting (e.g. AutoHotkey or PowerShell UI Automation) to reduce manual RDP time on iX Capture/PosPac, contingent on whether the vendors expose any automatable hooks."),

      h1("Ingestion Hardware Recommendations"),
      note("Capital purchase, outside the Azure recurring cost model. No vendor quotes obtained — not priced in detail."),
      bullet("Field drive: SanDisk Professional PRO-G40 — true Thunderbolt 3 (40 Gbps), IP68/crush/drop-rated, cooled core. Replaces the Samsung T-series (USB 3.2, not Thunderbolt) for better field ruggedness and fewer thermal-throttle disconnects."),
      bullet("Ground-station dock: OWC Thunderbolt Hub — independent per-port power, so one drive dropping or reconnecting does not disturb the others; enables reading multiple drives in parallel."),
      bullet("Ingest server: workstation-class board/CPU with enough PCIe lanes to run the hub at full bandwidth, local NVMe staging storage, and a 10GbE NIC matched to the confirmed 1,000 Mbps office uplink."),
      bullet("Immediate no-cost fix: disable Windows USB selective suspend (Power Options + Device Manager) — resolves roughly 80–90% of reported disconnect cases independent of any hardware change."),

      h1("Resource Reuse vs. New Resources"),
      resourceTable,

      h1("Cost Model"),
      h2("Constants"),
      bullet("COMPUTE_RATE = $0.816/hr (Standard_F16s_v2 PAYG, southcentralus)"),
      bullet("STORAGE_RATE = $0.018/GB/month (Hot LRS blob)"),
      bullet("Azure Bastion = $0.19/hr (Basic tier, southcentralus; Standard tier is $0.29/hr)"),
      bullet("Pipe 5/12 historical average = $22.54/tile (13-tile dataset, pipeline_runs.json)"),

      h2("Cost per Tile"),
      componentTable,

      h2("Scaling Scenarios"),
      p("Scaled from the current 13-tile pace documented in the COPECODE26 cost report. “New Azure spend” and “Total/mo” are shown as ranges reflecting the 50–100GB per-flight data volume range."),
      scalingTable,

      h1("Open Items / Risks"),
      bullet("iX Capture and PosPac software license portability to an Azure VM — unresolved, a vendor/licensing question outside Azure cost, not verified in this pass."),
      bullet("Technician processing time on iX Capture + PosPac — used as ~3.5 hrs/tile based on a “3+ hours” estimate, not a measured figure. Refine with real timesheet data before treating cost figures as final."),
      bullet("raw-ingest data volume — modeled as a 50–100GB/flight range based on a stated estimate, not a precise per-flight measurement."),
      bullet("raw-ingest retention window — modeled at 1 month as a proposed default; confirm actual retention policy."),
      bullet("Ingestion hardware capital cost — not priced; no vendor quotes obtained for the recommended drive/hub/server."),
      bullet("Phase 2 GUI automation for iX Capture/PosPac — flagged as future work, not committed, contingent on vendor tooling."),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("C:/Users/pi/claude/RGB_Azure_Migration_Model.docx", buf);
  console.log("done");
});
