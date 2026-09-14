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
function docTitle(mainTitle, subtitle, preparedDate, scopeLabel, scopeText) {
  return [
    new Paragraph({
      spacing: { before: 200, after: 40 },
      children: [new TextRun({ text: "PRIUS INTELLI", bold: true, color: TEAL, size: 18, font: FONT, characterSpacing: 20 })],
    }),
    new Paragraph({
      spacing: { after: 60 },
      children: [new TextRun({ text: mainTitle, bold: true, color: NAVY, size: 44, font: FONT })],
    }),
    new Paragraph({
      spacing: { after: 260 },
      border: { bottom: { color: AMBER, space: 6, style: BorderStyle.SINGLE, size: 12 } },
      children: [new TextRun({ text: subtitle, color: TEAL, size: 26, font: FONT })],
    }),
    new Paragraph({
      spacing: { after: 40 },
      children: [new TextRun({ text: "Prepared", color: SAGE, size: 18, font: FONT }), new TextRun({ text: `   ${preparedDate}`, color: INK, size: 18, font: FONT, bold: true })],
    }),
    new Paragraph({
      spacing: { after: 360 },
      children: [new TextRun({ text: scopeLabel, color: SAGE, size: 18, font: FONT }), new TextRun({ text: `   ${scopeText}`, color: INK, size: 18, font: FONT, bold: true })],
    }),
  ];
}

function statCallout(number, label, color, colWidth) {
  return new TableCell({
    width: { size: colWidth, type: WidthType.DXA },
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

function statRow(stats) {
  const colWidth = Math.floor(USABLE / stats.length);
  return new Table({
    width: { size: USABLE, type: WidthType.DXA },
    columnWidths: stats.map(() => colWidth),
    rows: [new TableRow({ cantSplit: true, children: stats.map((s) => statCallout(s.number, s.label, s.color, colWidth)) })],
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

function h3sub(title) {
  return new Paragraph({
    spacing: { before: 180, after: 80 },
    keepNext: true,
    keepLines: true,
    children: [new TextRun({ text: title, bold: true, italics: true, color: MUTED, size: 18, font: FONT })],
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
  const rowsOut = rows.map((r, i) => new TableRow({
    cantSplit: true,
    children: [
      cell(r[0], { w: w[0], shade: i % 2 ? MINT : "FFFFFF", bold: true, size: 18 }),
      cell(r[1], { w: w[1], shade: i % 2 ? MINT : "FFFFFF", size: 18, color: "3A4A44" }),
      cell(r[2], { w: w[2], shade: i % 2 ? MINT : "FFFFFF", size: 18 }),
      cell(r[3], { w: w[3], shade: i % 2 ? MINT : "FFFFFF", size: 18, align: AlignmentType.RIGHT, bold: true, color: r[3].includes("TBD") ? RUST : INK }),
    ],
  }));
  return new Table({ width: { size: USABLE, type: WidthType.DXA }, columnWidths: w, rows: [header, ...rowsOut] });
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
    ["3 · Cloud to Delivery", "$36,000–90,000", "~$5,370–5,530/mo*"],
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
      cell("$88,100–213,300", { w: w[1], shade: AMBER, bold: true, size: 20, align: AlignmentType.RIGHT }),
      cell("~$6,830–6,990/mo*", { w: w[2], shade: AMBER, bold: true, size: 20, align: AlignmentType.RIGHT }),
    ],
  });
  return new Table({ width: { size: USABLE, type: WidthType.DXA }, columnWidths: w, rows: [head, ...rows, total] });
}

function compareTable(headers, rows, widths, aligns) {
  const w = widths || [3200, 3080, 3080];
  const a = aligns || headers.map((_, i) => (i === 0 ? AlignmentType.LEFT : AlignmentType.RIGHT));
  const head = new TableRow({
    tableHeader: true, cantSplit: true,
    children: headers.map((h, i) => cell(h, { w: w[i], shade: NAVY, color: "FFFFFF", bold: true, size: 18, align: a[i] })),
  });
  const rowsOut = rows.map((r, i) => new TableRow({
    cantSplit: true,
    children: r.map((c, j) => cell(c, { w: w[j], shade: i % 2 ? MINT : "FFFFFF", size: 18, bold: j === 0, align: a[j] })),
  }));
  return new Table({ width: { size: USABLE, type: WidthType.DXA }, columnWidths: w, rows: [head, ...rowsOut] });
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

function buildDocument(headerText, children) {
  return new Document({
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
          children: [new TextRun({ text: headerText, color: SAGE, size: 16, font: FONT })],
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
      children,
    }],
  });
}

function writeDoc(doc, filename) {
  return Packer.toBuffer(doc).then((buf) => {
    fs.writeFileSync(filename, buf);
    console.log("written:", filename);
  });
}

module.exports = {
  NAVY, TEAL, AMBER, RUST, MINT, SAGE, MUTED, INK, FONT, USABLE,
  PageBreak,
  docTitle, statRow, h1, h2, h3sub, body, bullet, note, cell,
  equipmentTable, costTable, compareTable, resourceTable,
  buildDocument, writeDoc,
};
