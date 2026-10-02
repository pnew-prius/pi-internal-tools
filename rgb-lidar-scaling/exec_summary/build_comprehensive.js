const HELPERS_DIR = "C:/Users/pi/claude/pi-internal-tools/rgb-pipeline-roadmap/exec_summary";
const {
  NAVY, TEAL, AMBER, RUST, MUTED, PageBreak,
  docTitle, statRow, h1, h2, body, bullet, note,
  buildDocument, writeDoc,
} = require(HELPERS_DIR + "/docx_helpers");
const { Paragraph } = require(require.resolve("docx", { paths: [HELPERS_DIR] }));

const { children: softwareChildren } = require("./build_software");
const { children: hardwareChildren } = require("./build_hardware");
const { children: azureChildren } = require("./build_azure_costs");
const { children: strategyChildren } = require("./build_strategy");

const pageBreak = () => new Paragraph({ children: [new PageBreak()] });

const children = [
  ...docTitle(
    "RGB/LiDAR Scaling",
    "Comprehensive Executive Summary",
    "1 October 2026",
    "Scope",
    "Software, hardware, Azure costs, risks/alternatives, and implementation plan for scaling RGB and LiDAR aerial imagery processing. Each section below is also published as a standalone sub-report for topic-specific distribution."
  ),

  statRow([
    { number: "One Button", label: "Current recommendation \u2014 conditional, pending SimActive quote", color: NAVY },
    { number: "2 gaps", label: "LiDAR workflow + ingest-architecture reconciliation, both open", color: AMBER },
    { number: "4 reports", label: "This document breaks out into standalone Software / Hardware / Azure Cost / Strategy reports", color: TEAL },
  ]),

  h2("How to Use This Document", NAVY),
  body("This is the comprehensive version, assembled from four standalone sub-reports (each also available as its own file): Software Comparison, Hardware Comparison, Azure Cost Validation, and Risks/Alternatives/Implementation Plan. All four pull from the same findings files (pi-internal-tools/rgb-lidar-scaling/findings/), so there is no drift between this document and the standalone versions \u2014 update the findings file and rebuild to refresh both."),
  bullet("Software and hardware vendor/engine decisions are presented conditionally (sensitivity ranges, not single numbers) where a real vendor confirmation is still pending \u2014 see the Open Decisions list in the Risk section."),
  bullet("LiDAR-specific content is not yet included \u2014 the current LiDAR workflow has not been described by the user; see Risks, item 3."),

  pageBreak(),
  ...softwareChildren,

  pageBreak(),
  ...hardwareChildren,

  pageBreak(),
  ...azureChildren,

  pageBreak(),
  ...strategyChildren,
];

writeDoc(
  buildDocument("RGB/LiDAR Scaling — Comprehensive Executive Summary", children),
  "C:\\Users\\pi\\claude\\pi-internal-tools\\rgb-lidar-scaling\\exec_summary\\Comprehensive_Exec_Summary.docx"
);
