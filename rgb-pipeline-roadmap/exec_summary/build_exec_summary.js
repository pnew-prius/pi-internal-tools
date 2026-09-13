const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  Header, Footer, PageNumber, LevelFormat, VerticalAlign, PageBreak,
} = require("docx");
const fs = require("fs");

// ---- Brand (Prius Intelli — from theme1.xml, "Prius Intelli - Core") ----
const NAVY = "1F3D32";
const TEAL = "1E6F5C";
const AMBER = "E3B23C";
const RUST = "C1502E";
const MINT = "F2F6F4";
const SAGE = "9AA5A1";
const MUTED = "595959";
const INK = "0B0B0B";
const FONT = "Segoe UI";

const PAGE_W = 12240, PAGE_H = 15840; // US Letter, DXA
const MARGIN = 1440; // 1 in
const USABLE = PAGE_W - MARGIN * 2; // 9360

// ---------- helpers ----------
function docTitle() {
  return [
    new Paragraph({
      spacing: { before: 200, after: 40 },
      children: [new TextRun({ text: "PRIUS INTELLI", bold: true, color: TEAL, size: 18, font: FONT, characterSpacing: 20 })],
    }),
    new Paragraph({
      spacing: { after: 60 },
      children: [new TextRun({ text: "RGB Imagery Pipeline — Cloud Migration", bold: true, color: NAVY, size: 44, font: FONT })],
    }),
    new Paragraph({
      spacing: { after: 260 },
      border: { bottom: { color: AMBER, space: 6, style: BorderStyle.SINGLE, size: 12 } },
      children: [new TextRun({ text: "Executive Summary", color: TEAL, size: 26, font: FONT })],
    }),
    new Paragraph({
      spacing: { after: 40 },
      children: [new TextRun({ text: "Prepared", color: SAGE, size: 18, font: FONT }), new TextRun({ text: "   13 September 2026", color: INK, size: 18, font: FONT, bold: true })],
    }),
    new Paragraph({
      spacing: { after: 360 },
      children: [new TextRun({ text: "Scope", color: SAGE, size: 18, font: FONT }), new TextRun({ text: "   Aircraft capture through customer delivery — three legs", color: INK, size: 18, font: FONT, bold: true })],
    }),
  ];
}

function statCallout(number, label, color) {
  return new TableCell({
    width: { size: Math.floor(USABLE / 5), type: WidthType.DXA },
    shading: { type: ShadingType.CLEAR, fill: MINT },
    margins: { top: 160, bottom: 160, left: 140, right: 140 },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 4, color: "DDDDDD" },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: "DDDDDD" },
      left: { style: BorderStyle.SINGLE, size: 4, color: "DDDDDD" },
      right: { style: BorderStyle.SINGLE, size: 4, color: "DDDDDD" },
    },
    children: [
      new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: number, bold: true, color, size: 32, font: FONT })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 40 }, children: [new TextRun({ text: label, color: SAGE, size: 16, font: FONT })] }),
    ],
  });
}

function statRow() {
  return new Table({
    width: { size: USABLE, type: WidthType.DXA },
    columnWidths: [1, 1, 1, 1, 1].map(() => Math.floor(USABLE / 5)),
    rows: [new TableRow({ cantSplit: true, children: [
      statCallout("$64,100–153,300", "Total one-time investment", NAVY),
      statCallout("~$6,720–6,840/mo", "Recurring run cost", TEAL),
      statCallout("8–14 wks", "Fastest possible, fully parallel", AMBER),
      statCallout("3", "Pipeline legs — Collection, FBO, Cloud", MUTED),
      statCallout("Built", "Image conversion — core proven, tuning + orchestration remain", MUTED),
    ]})],
  });
}

function h1(number, title) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 420, after: 180 },
    keepNext: true,
    keepLines: true,
    border: { bottom: { color: TEAL, space: 5, style: BorderStyle.SINGLE, size: 6 } },
    children: [
      new TextRun({ text: `${number}   `, bold: true, color: TEAL, size: 26, font: FONT }),
      new TextRun({ text: title, bold: true, color: NAVY, size: 26, font: FONT }),
    ],
  });
}

function h2(title, color) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 220, after: 100 },
    keepNext: true,
    keepLines: true,
    children: [new TextRun({ text: title, bold: true, color: color || TEAL, size: 21, font: FONT })],
  });
}

function body(text) {
  return new Paragraph({ spacing: { after: 140 }, children: [new TextRun({ text, color: INK, size: 21, font: FONT })] });
}

function bullet(text, opts) {
  opts = opts || {};
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    spacing: { after: 70 },
    keepNext: true,
    keepLines: true,
    children: [new TextRun({ text, color: opts.color || INK, size: 21, font: FONT, bold: !!opts.bold })],
  });
}

function note(text) {
  return new Paragraph({
    spacing: { before: 100, after: 100 },
    children: [new TextRun({ text, italics: true, color: SAGE, size: 18, font: FONT })],
  });
}

function cell(text, opts) {
  opts = opts || {};
  return new TableCell({
    width: { size: opts.w, type: WidthType.DXA },
    shading: opts.shade ? { type: ShadingType.CLEAR, fill: opts.shade } : undefined,
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 90, bottom: 90, left: 110, right: 110 },
    children: [new Paragraph({
      alignment: opts.align || AlignmentType.LEFT,
      children: [new TextRun({ text, bold: !!opts.bold, color: opts.color || INK, size: opts.size || 19, font: FONT })],
    })],
  });
}

function equipmentTable(rows, widths) {
  const w = widths || [2200, 3800, 1400, 1960];
  const header = new TableRow({
    tableHeader: true,
    cantSplit: true,
    children: [
      cell("Item", { w: w[0], shade: NAVY, color: "FFFFFF", bold: true, size: 18 }),
      cell("What it does", { w: w[1], shade: NAVY, color: "FFFFFF", bold: true, size: 18 }),
      cell("Qty", { w: w[2], shade: NAVY, color: "FFFFFF", bold: true, size: 18 }),
      cell("Price", { w: w[3], shade: NAVY, color: "FFFFFF", bold: true, size: 18, align: AlignmentType.RIGHT }),
    ],
  });
  const body = rows.map((r, i) => new TableRow({
    cantSplit: true,
    children: [
      cell(r[0], { w: w[0], shade: i % 2 ? MINT : "FFFFFF", bold: true, size: 18 }),
      cell(r[1], { w: w[1], shade: i % 2 ? MINT : "FFFFFF", size: 18, color: "3A4A44" }),
      cell(r[2], { w: w[2], shade: i % 2 ? MINT : "FFFFFF", size: 18 }),
      cell(r[3], { w: w[3], shade: i % 2 ? MINT : "FFFFFF", size: 18, align: AlignmentType.RIGHT, bold: true, color: r[3].includes("TBD") ? RUST : INK }),
    ],
  }));
  return new Table({ width: { size: USABLE, type: WidthType.DXA }, columnWidths: w, rows: [header, ...body] });
}

function costTable() {
  const w = [3600, 2880, 2880];
  const head = new TableRow({
    tableHeader: true,
    cantSplit: true,
    children: [
      cell("Leg", { w: w[0], shade: NAVY, color: "FFFFFF", bold: true, size: 19 }),
      cell("One-time", { w: w[1], shade: NAVY, color: "FFFFFF", bold: true, size: 19, align: AlignmentType.RIGHT }),
      cell("Recurring", { w: w[2], shade: NAVY, color: "FFFFFF", bold: true, size: 19, align: AlignmentType.RIGHT }),
    ],
  });
  const rows = [
    ["1 · Collection to FBO", "$46,000–106,400", "—"],
    ["2 · FBO to Cloud", "$6,100–16,900", "$1,460/mo"],
    ["3 · Cloud to Delivery", "$12,000–30,000", "~$5,260–5,380/mo*"],
  ].map((r, i) => new TableRow({
    cantSplit: true,
    children: [
      cell(r[0], { w: w[0], shade: i % 2 ? MINT : "FFFFFF", bold: true, size: 19 }),
      cell(r[1], { w: w[1], shade: i % 2 ? MINT : "FFFFFF", size: 19, align: AlignmentType.RIGHT }),
      cell(r[2], { w: w[2], shade: i % 2 ? MINT : "FFFFFF", size: 19, align: AlignmentType.RIGHT }),
    ],
  }));
  const total = new TableRow({
    cantSplit: true,
    children: [
      cell("Total", { w: w[0], shade: AMBER, bold: true, size: 20 }),
      cell("$64,100–153,300", { w: w[1], shade: AMBER, bold: true, size: 20, align: AlignmentType.RIGHT }),
      cell("~$6,720–6,840/mo*", { w: w[2], shade: AMBER, bold: true, size: 20, align: AlignmentType.RIGHT }),
    ],
  });
  return new Table({ width: { size: USABLE, type: WidthType.DXA }, columnWidths: w, rows: [head, ...rows, total] });
}

function resourceTable() {
  const w = [3200, 6160];
  const head = new TableRow({
    tableHeader: true,
    cantSplit: true,
    children: [
      cell("Role", { w: w[0], shade: NAVY, color: "FFFFFF", bold: true, size: 19 }),
      cell("Responsible for", { w: w[1], shade: NAVY, color: "FFFFFF", bold: true, size: 19 }),
    ],
  });
  const rows = [
    ["Embedded Software Engineer", "Onboard capture integration and in-flight quality-check software"],
    ["Cloud / DevOps Engineer", "Upload automation, ingest verification, and monitoring"],
    ["Systems Integration Engineer", "Validates SDK sharpening, adds the still-missing clarity feature, and wires the existing conversion pipeline into the cloud"],
    ["Avionics Installation Technician", "Mounts and wires onboard equipment, per aircraft"],
  ].map((r, i) => new TableRow({
    cantSplit: true,
    children: [
      cell(r[0], { w: w[0], shade: i % 2 ? MINT : "FFFFFF", bold: true, size: 19 }),
      cell(r[1], { w: w[1], shade: i % 2 ? MINT : "FFFFFF", size: 19 }),
    ],
  }));
  return new Table({ width: { size: USABLE, type: WidthType.DXA }, columnWidths: w, rows: [head, ...rows] });
}

// ---------- document ----------
const doc = new Document({
  numbering: {
    config: [{
      reference: "bullets",
      levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 420, hanging: 260 } } } }],
    }],
  },
  sections: [{
    properties: {
      page: { size: { width: PAGE_W, height: PAGE_H }, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } },
    },
    headers: {
      default: new Header({ children: [new Paragraph({
        border: { bottom: { color: SAGE, space: 4, style: BorderStyle.SINGLE, size: 4 } },
        children: [new TextRun({ text: "RGB Imagery Pipeline — Cloud Migration", color: SAGE, size: 16, font: FONT })],
      })] }),
    },
    footers: {
      default: new Footer({ children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [
          new TextRun({ text: "© 2026 Prius Intelli   ·   ", color: SAGE, size: 15, font: FONT }),
          new TextRun({ text: "Page ", color: SAGE, size: 15, font: FONT }),
          new TextRun({ children: [PageNumber.CURRENT], color: SAGE, size: 15, font: FONT }),
        ],
      })] }),
    },
    children: [
      ...docTitle(),

      statRow(),

      h2("Key Notes", NAVY),
      bullet("Development figures throughout this document are rough engineering estimates, not vendor quotes — refine before committing budget."),
      bullet("Before the timeline in Section 6 starts, hardware needs to be ordered — no committed lead time yet."),
      bullet("The ~$6,720–6,840/month recurring figure reflects the 1-sortie/day planning basis; real 2025 usage implies materially higher volume, so this number should be revisited once that gap is resolved (Section 7)."),

      new Paragraph({ spacing: { before: 260 }, children: [] }),

      h1("1", "Work To Be Done — Scope"),
      body("Move RGB aerial-imagery processing off on-premise office workstations and onto cloud infrastructure, in three legs:"),
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

      h1("5", "Resources"),
      body("Roles required to close the gaps above. Rates and total hours are not yet scoped — see Section 6."),
      resourceTable(),

      h1("6", "Cost & Timeline"),
      body("Figures are planning estimates by pipeline leg. See Appendix A for the underlying equipment and service breakdown."),
      costTable(),
      note("*Cloud to Delivery recurring cost now includes a derived estimate for image conversion (~$300–420/mo, see Appendix A.3) alongside current metered rates for a shared-tenant workload; see Appendix A.4."),
      h2("Indicative timeline (parallel workstreams)", NAVY),
      bullet("Collection to FBO — 8–14 weeks (largest engineering scope; bounds the overall timeline)"),
      bullet("FBO to Cloud — 1–2 weeks"),
      bullet("Cloud to Delivery — 4–8 weeks"),
      body("Running in parallel, overall duration is bounded by Collection to FBO: approximately 8–14 weeks."),

      h1("7", "Key Assumptions & Risks"),
      bullet("Planning basis: 1 sortie/day, 1 aircraft, ~480 GB/sortie on the 150 MP camera — measured from a real project sortie, not estimated"),
      bullet("Development figures are rough engineering estimates pending detailed scoping, not vendor quotes"),
      bullet("Cloud figures reflect real, current metered rates for the existing pipeline; delivery storage is a shared account also used by other projects, not isolated to this pipeline"),
      bullet("Scaling beyond 1 sortie/day is not yet resolved — real historical usage implies materially higher volume, and would change cloud compute sizing before this plan is finalized", { color: RUST }),

      new Paragraph({ children: [new PageBreak()] }),
      h1("A", "Appendix — Technical Addendum"),
      body("Equipment and services underlying the Section 6 cost table, by pipeline leg."),

      h2("A.1  Collection to FBO", TEAL),
      equipmentTable([
        ["Onboard edge computer", "Ruggedized computer on the aircraft; checks each photo for quality — blur, exposure, coverage gaps — as it's taken; saves photos to a drive with a checksum", "1 / aircraft", "$2,000–4,000"],
        ["Camera-to-computer cabling", "Connects the camera to the onboard computer", "1 / aircraft", "$200–500"],
        ["Removable NVMe drives", "Swappable drives; full drive out, blank drive in after landing", "4 / aircraft", "$1,600–3,200"],
        ["Docking stations", "Reads the drive back in at the office", "2 / office", "$200–700"],
        ["Aircraft installation", "Mounting, wiring, power for the onboard computer", "1 / aircraft", "$2,000–8,000"],
        ["Camera software license", "Lets the onboard computer connect to the camera", "1 / fleet", "$0"],
        ["Onboard QC software development", "Camera-SDK integration, per-photo quality checks, coverage-vs-plan logic, checksum/manifest system", "1 (fleet-wide, one-time)", "$40,000–90,000"],
      ]),
      note("Software is built once and deployed fleet-wide; each additional aircraft adds only the hardware rows above."),

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
        ["Image conversion", "Converts raw camera files into working images. Real codebase (private GitHub repo); core conversion, geometric correction, and ICC embedding proven on production imagery. Native SDK sharpening and a clarity feature remain to be built/tuned. Cost derived from measured processing time (25–35 s/image) on the same VM class as the rest of the pipeline — not yet a live production bill", "usage-based", "~$300–420/mo (derived)"],
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
      bullet("Image conversion's ~$300–420/mo is derived (measured 25–35 s/image × the same VM rate used elsewhere in this pipeline × ~634,000 images/year), not a live production bill. Converting one sortie (~3,171 images) serially takes ~22–31 hours on a single instance — production needs roughly 11–16 parallel instances to clear a sortie in ~2 hours (cost is essentially unchanged by how many instances share the work; parallelism buys turnaround time, not savings)"),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("RGB_Pipeline_Executive_Summary.docx", buf);
  console.log("written");
});
