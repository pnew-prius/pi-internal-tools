const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, AlignmentType, BorderStyle, VerticalAlign, PageOrientation,
  Header, Footer, PageNumber, NumberFormat,
} = require("docx");
const fs = require("fs");

const NAVY = "1F3D32";
const TEAL = "1E6F5C";
const AMBER = "E3B23C";
const RUST = "C1502E";
const INK = "1B2430";
const MUTED = "595959";
const LIGHT = "F2F6F4";
const WHITE = "FFFFFF";

const FONT = "Calibri";
const FONT_HEAD = "Cambria";

const PAGE_W = 12240, PAGE_H = 15840; // US Letter DXA
const MARGIN = 1080; // 0.75in
const CONTENT_W = PAGE_W - 2 * MARGIN;

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 320, after: 140 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: NAVY, space: 4 } },
    children: [new TextRun({ text, bold: true, color: NAVY, font: FONT_HEAD, size: 30 })],
  });
}

function h2(text, color = TEAL) {
  return new Paragraph({
    spacing: { before: 220, after: 100 },
    children: [new TextRun({ text, bold: true, color, font: FONT_HEAD, size: 24 })],
  });
}

function body(text, opts = {}) {
  return new Paragraph({
    spacing: { after: 140, line: 276 },
    children: [new TextRun({ text, font: FONT, size: 21, color: INK, ...opts })],
  });
}

function bullet(text, opts = {}) {
  return new Paragraph({
    numbering: { reference: "exec-bullets", level: 0 },
    spacing: { after: 80, line: 264 },
    children: [new TextRun({ text, font: FONT, size: 21, color: INK, ...opts })],
  });
}

function statCallout(number, label, color) {
  return new TableCell({
    width: { size: Math.floor(CONTENT_W / 4), type: WidthType.DXA },
    shading: { type: ShadingType.CLEAR, fill: LIGHT },
    margins: { top: 160, bottom: 160, left: 160, right: 160 },
    borders: allBorders("DDDDDD"),
    children: [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: number, bold: true, color, font: FONT_HEAD, size: 36 })],
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 40 },
        children: [new TextRun({ text: label, color: MUTED, font: FONT, size: 17 })],
      }),
    ],
  });
}

function allBorders(color, size = 4) {
  const b = { style: BorderStyle.SINGLE, size, color };
  return { top: b, bottom: b, left: b, right: b };
}

function tCell(text, { header = false, width, align = AlignmentType.LEFT, fill, color, bold, size = 19 } = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: fill ? { type: ShadingType.CLEAR, fill } : (header ? { type: ShadingType.CLEAR, fill: NAVY } : undefined),
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 90, bottom: 90, left: 120, right: 120 },
    borders: allBorders("D9D9D9"),
    children: [new Paragraph({
      alignment: align,
      children: [new TextRun({
        text, bold: header || bold, size: header ? 19 : size,
        color: color || (header ? WHITE : INK), font: FONT,
      })],
    })],
  });
}

function makeTable(headers, rows, widths) {
  const total = widths.reduce((a, b) => a + b, 0);
  const scale = CONTENT_W / total;
  const scaledWidths = widths.map(w => Math.floor(w * scale));
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: scaledWidths,
    rows: [
      new TableRow({
        tableHeader: true,
        children: headers.map((h, i) => tCell(h, { header: true, width: scaledWidths[i], align: i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER })),
      }),
      ...rows.map((r, ri) => new TableRow({
        children: r.map((c, i) => tCell(String(c), {
          width: scaledWidths[i],
          align: i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER,
          fill: ri % 2 === 1 ? "F7FAF9" : undefined,
          bold: r._bold,
        })),
      })),
    ],
  });
}

const doc = new Document({
  numbering: {
    config: [{
      reference: "exec-bullets",
      levels: [{ level: 0, format: "bullet", text: "\u2022", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 360, hanging: 260 } } } }],
    }],
  },
  styles: {
    default: { document: { run: { font: FONT, size: 21, color: INK } } },
  },
  sections: [{
    properties: {
      page: {
        size: { width: PAGE_W, height: PAGE_H },
        margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "D9D9D9", space: 4 } },
          children: [new TextRun({ text: "Mercator Platform — Executive Summary", color: MUTED, size: 16, font: FONT })],
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({ text: "Prius Intelli · Confidential · ", color: MUTED, size: 16, font: FONT }),
            new TextRun({ text: "Page ", color: MUTED, size: 16, font: FONT }),
            new TextRun({ children: [PageNumber.CURRENT], color: MUTED, size: 16, font: FONT }),
            new TextRun({ text: " of ", color: MUTED, size: 16, font: FONT }),
            new TextRun({ children: [PageNumber.TOTAL_PAGES], color: MUTED, size: 16, font: FONT }),
          ],
        })],
      }),
    },
    children: [
      // ===== Title block =====
      new Paragraph({
        spacing: { after: 40 },
        children: [new TextRun({ text: "PRIUS INTELLI", bold: true, color: AMBER, font: FONT, size: 18, characterSpacing: 20 })],
      }),
      new Paragraph({
        spacing: { after: 60 },
        children: [new TextRun({ text: "Mercator Platform", bold: true, color: NAVY, font: FONT_HEAD, size: 52 })],
      }),
      new Paragraph({
        spacing: { after: 260 },
        children: [new TextRun({ text: "Executive Summary — Scope, Capabilities, Resourcing & Cost", color: TEAL, font: FONT_HEAD, size: 26, italics: true })],
      }),

      // ===== Top-line stat callouts =====
      new Table({
        width: { size: CONTENT_W, type: WidthType.DXA },
        columnWidths: [Math.floor(CONTENT_W/5), Math.floor(CONTENT_W/5), Math.floor(CONTENT_W/5), Math.floor(CONTENT_W/5), Math.floor(CONTENT_W/5)],
        rows: [new TableRow({ children: [
          statCallout("$617,915", "On-Shore — total program cost", NAVY),
          statCallout("$193,835", "Off-Shore — total program cost", TEAL),
          statCallout("8 weeks", "Fastest possible, fully parallel", AMBER),
          statCallout("4", "Workstreams (3 tracks + cloud migration)", MUTED),
          statCallout("$2,980", "Monthly run cost, post-launch", RUST),
        ]}) ],
      }),

      h2("Key Notes"),
      bullet("The AI Workbench is not part of this document.", { bold: true, color: RUST }),
      bullet("Data Operations views this project as important and one that should ultimately be completed — though it may be worth considering that Mercator's direct revenue impact is comparatively limited relative to higher-revenue initiatives such as LiDAR and AI products, so its progress ideally wouldn't come at the expense of those efforts."),
      bullet("Before any of this timeline starts, each contractor needs a bit of runway to get onboarded — contract signed, background check cleared, system access set up. That's typically a few business days for someone based in the U.S., or one to two weeks for someone based in India, and it happens ahead of the 8 weeks above rather than adding to it."),
      bullet("The $2,980 monthly run cost reflects baseline infrastructure only — this figure will grow as client data is hosted on the platform and storage volume increases."),

      new Paragraph({ spacing: { before: 260 }, children: [] }),

      // ===== 1. Work To Be Done — Scope =====
      h1("1. Work To Be Done — Scope"),
      body("Mercator is Prius Intelli's online platform for customers to order and receive aerial and geospatial data, plus the internal tools staff use to run that business day to day. It's built around four parts: Order Management, a Data Portal, an AI Workbench, and Business Intelligence, which turns information from the other three into insight for running the company."),
      body("This plan covers finishing three of those four parts — Order Management, the Data Portal, and Business Intelligence — and moving the whole platform onto Prius Intelli's own cloud hosting. Each of the three carries more work than first assumed, including two especially complex pieces inside Order Management: automatic price quoting and automatic flight-plan creation, neither of which exists anywhere in the platform today."),
      bullet("Move the platform onto Prius Intelli's own cloud hosting, alongside the company's other systems."),
      bullet("Finish Order Management — add automatic price quoting and automatic flight-plan creation, complete the payment processing so orders can actually be paid for online, connect it to the company's other business systems, and open it up so outside partners can connect in."),
      bullet("Finish the Data Portal — give customers a real, secure way to upload and download their files, and let the company's AI tools work with that data safely."),
      bullet("Build real Business Intelligence — turn today's basic activity counts into real revenue tracking, cost tracking, and forecasting."),
      body("The AI Workbench, the platform's fourth planned part, hasn't been started and is not included in this plan.", { italics: true, color: MUTED }),

      // ===== 2. Finished State Capabilities =====
      h1("2. Finished State Capabilities"),
      body("This is what each part of the platform will be able to do once this plan is complete."),
      makeTable(
        ["Part", "Once Finished"],
        [
          ["Cloud Hosting", "The whole platform runs on Prius Intelli's own cloud hosting, alongside the company's other systems, instead of a third-party host."],
          ["Order Management", "A customer can request a project, get an automatic price quote back within minutes, receive an automatically generated flight plan, place and pay for the order, and track it the whole way through. Staff see the same order information alongside the company's other systems, and outside partners can connect to the platform directly."],
          ["Data Portal", "Customers can securely upload and download their project files, trust that their data is protected, and let the company's AI tools work with that data without it ever being exposed publicly."],
          ["Business Intelligence", "Leadership can see real revenue, true cost per project, and forward-looking forecasts drawn from the platform's own data — not just a count of orders."],
          ["AI Workbench", "Not part of this plan — still to be defined, scoped, and costed separately."],
        ],
        [22, 78]
      ),

      // ===== 3. Current State Capabilities =====
      h1("3. Current State Capabilities"),
      body("This is what the platform can already do today, before any of the work in this plan."),
      makeTable(
        ["Part", "Today"],
        [
          ["Shared Foundation", "Customers and staff can already log in and manage their accounts and companies. Staff have internal tools to see and manage every customer's orders in one place."],
          ["Order Management", "Customers can already create an account and place an order, and can see their order's status along the way. Paying for an order online is not fully working yet."],
          ["Data Portal", "Customers can already upload their project files and see them on a map. There's no way yet to actually deliver finished data back to them."],
          ["Business Intelligence", "Staff can see basic activity counts — how many orders, from which companies — but nothing that adds up to real revenue or forecasting numbers yet."],
          ["AI Workbench", "Nothing built yet."],
        ],
        [22, 78]
      ),

      // ===== 4. Gaps =====
      h1("4. Gaps"),
      body("The gap between where the platform is today (Section 3) and where it needs to be (Section 2) is what this plan builds. Each line below maps directly to the scope in Section 1."),
      makeTable(
        ["Part", "What's Missing"],
        [
          ["Cloud Hosting", "The platform runs on a different hosting provider today, not Prius Intelli's own cloud — moving it over is a project in itself."],
          ["Order Management", "No automatic price quoting — pricing is worked out manually today. No automatic flight-plan creation. Payment processing is not fully working yet, so orders can't reliably be paid for online. No connection yet to the company's other business systems. No way for outside partners to connect in."],
          ["Data Portal", "There's no real secure file storage behind the scenes yet, so large-scale upload and download aren't possible today. There's no way yet to actually deliver finished data back to customers, and safe AI-tool access to that data isn't possible either."],
          ["Business Intelligence", "What exists today is just a count of activity, not real numbers — there's no revenue tracking, no cost-per-project view, and no forecasting."],
        ],
        [22, 78]
      ),

      // ===== 5. Resources =====
      h1("5. Resources"),
      h2("Team & Roles"),
      body("Staffing reflects the engagement brief: fastest achievable delivery under unlimited budget, meaning market-rate contract talent staffed immediately rather than a multi-month hiring cycle. Rates are directional 2026 market estimates.", { italics: true, color: MUTED }),
      makeTable(
        ["Role", "Rate", "Used on"],
        [
          ["Delivery Lead / TPM", "$150/hr", "All 4 workstreams"],
          ["Senior Backend Engineer", "$140/hr", "Cloud Migration, Order Mgmt, Data Portal"],
          ["Business / Systems Analyst", "$125/hr", "Order Management (defining the automated quoting logic)"],
          ["Senior Frontend Engineer", "$130/hr", "Data Portal (visualize & download UI)"],
          ["DevOps / Cloud Engineer", "$145/hr", "Cloud Migration, Order Mgmt, Data Portal"],
          ["Security Consultant", "$200/hr", "Cloud Migration, Order Management, Data Portal"],
          ["QA Engineer", "$95/hr", "All 4 workstreams"],
          ["GIS / Geospatial Engineer", "$160/hr", "Order Management (flight planning), Data Portal"],
          ["Data Engineer", "$145/hr", "Data Portal, Business Intelligence"],
          ["Analytics Engineer", "$135/hr", "Business Intelligence"],
          ["BI Developer", "$120/hr", "Business Intelligence"],
          ["Data Scientist", "$170/hr", "Business Intelligence"],
        ],
        [40, 20, 40]
      ),
      body("The specific tools, cloud services, and cost detail behind each task are broken out in the Technical Addendum.", { italics: true, color: MUTED }),

      // ===== 6. Cost & Timeline Summary =====
      h1("6. Cost & Timeline Summary"),
      makeTable(
        ["Workstream", "Duration", "People Cost", "Hardware/Software", "Total Cost", "Post-Launch Monthly"],
        [
          ["Cloud Migration", "3 weeks", "$67,800", "$1,360", "$69,160", "$1,360"],
          ["Order Management", "8 weeks", "$189,000", "$2,000", "$191,000", "$1,000"],
          ["Data Portal", "5 weeks", "$137,200", "$155", "$137,355", "$120"],
          ["Business Intelligence", "8 weeks", "$219,400", "$1,000", "$220,400", "$500"],
          Object.assign(["Program Total (parallel)", "8 weeks", "$613,400", "$4,515", "$617,915", "$2,980"], { _bold: true }),
        ],
        [26, 13, 15, 16, 15, 15]
      ),
      body("Duration reflects all four workstreams staffed and run fully in parallel — the program timeline is the longest single track (Order Management and Business Intelligence, each 8 weeks), not a sum of all four. Order Management's flight-planning estimate is explicitly flagged as a floor, not a ceiling — see Key Assumptions & Risks.", { italics: true, color: MUTED }),
      body("Cloud Migration's cost reflects reusing Prius Intelli's existing Azure infrastructure where it's a clean fit — its network, an existing web firewall, and an existing content-delivery profile — instead of provisioning new equivalents from scratch. See the Technical Addendum for exactly what's reused versus new, and the trade-offs involved.", { italics: true, color: MUTED }),

      // ===== 7. US vs. India Delivery Comparison =====
      h1("7. US vs. India Delivery Comparison"),
      body("Same roles, same hours, same hardware — only the delivery location's labor rate changes. Cloud infrastructure cost is identical regardless of where the team sits, so only the People portion of each workstream's cost shifts. The comparison below is fully-onshore vs. fully-offshore; a blended/hybrid staffing model (for example, a US-based Delivery Lead and Security Consultant with an India-based engineering team) would land between the two columns."),
      makeTable(
        ["Workstream", "US Total Cost", "India Total Cost", "Savings ($)", "Savings (%)"],
        [
          ["Cloud Migration", "$69,160", "$22,840", "$46,320", "67%"],
          ["Order Management", "$191,000", "$60,240", "$130,760", "68%"],
          ["Data Portal", "$137,355", "$42,435", "$94,920", "69%"],
          ["Business Intelligence", "$220,400", "$68,320", "$152,080", "69%"],
          Object.assign(["Program Total", "$617,915", "$193,835", "$424,080", "69%"], { _bold: true }),
        ],
        [26, 19, 19, 18, 18]
      ),
      new Paragraph({ spacing: { before: 200 }, children: [] }),
      new Table({
        width: { size: CONTENT_W, type: WidthType.DXA },
        columnWidths: [Math.floor(CONTENT_W/2), Math.floor(CONTENT_W/2)],
        rows: [new TableRow({ children: [
          statCallout("$424,080", "Total program savings, India delivery", TEAL),
          statCallout("69%", "Reduction in program cost vs. fully-onshore", RUST),
        ]}) ],
      }),
      new Paragraph({ spacing: { before: 200 }, children: [] }),
      body("India rates use a narrower discount for scarcer specialized skills (Security Consultant, GIS/Geospatial Engineer, Data Scientist) than for generalist roles (Backend, QA, DevOps), consistent with real offshore market patterns rather than a flat percentage off every role. See the Rate Card for the full role-by-role US/India breakdown.", { italics: true, color: MUTED }),
      body("Personnel onboarding declaration: the durations above assume every contractor is fully onboarded — contract executed, background/security check complete, and system access provisioned — before Day 1 of their workstream. Typical lead time to reach that state is 3–5 business days for a US-based contractor and 1–2 weeks for an India-based offshore resource, since cross-border engagements add security review and access-provisioning steps. This is a pre-program kickoff dependency, not an extension of the 8-week delivery window modeled above.", { italics: true, color: MUTED }),

      // ===== 8. Key Assumptions & Risks =====
      h1("8. Key Assumptions & Risks"),
      bullet("\u201CFastest possible\u201D assumes unlimited budget and immediate contractor staffing, not existing-team bandwidth — actual timeline will extend if staffed internally or sequentially."),
      bullet("Automated flight planning (Order Management) is the single highest-uncertainty item in this plan: it is heavily variable-dependent, involves capability not yet built in any form, and is expected to need several build/validation iterations before it's production-ready. Its 7-week phase estimate should be treated as a floor, not a ceiling."),
      bullet("Automated quoting (Order Management) involves complex pricing logic and extensive variables that must be fully defined and validated before it can be automated — undocumented edge cases in today's process could extend this."),
      bullet("Personnel onboarding (contracting, security/background checks, system access) is assumed complete before each workstream's Day 1 and is not counted inside the 8-week program total — budget 3–5 business days for this per US-based resource, 1–2 weeks per India-based resource, as a kickoff dependency ahead of the timeline above."),
      bullet("All role rates — US and India — are directional market estimates, not vendor quotes; confirm with actual contracting partners before finalizing budget."),
      bullet("The India comparison reflects labor rate only. It does not account for time zone overlap with the US team, data-residency/security review for client geospatial data, or the coordination overhead of a distributed team — factor these in before treating the 69% figure as a net savings guarantee."),
      bullet("Migration risk is low: confirmed no production customer data exists in the current hosting database, so this is a fresh deploy onto new infrastructure rather than a live cutover."),
      bullet("AI Workbench remains unscoped and uncosted in this plan — recommend a follow-up costing pass once its requirements are defined."),

      // ===== Appendix A: Technical Addendum =====
      new Paragraph({ children: [new TextRun({ text: "", break: 1 })], pageBreakBefore: true }),
      h1("Appendix A: Technical Addendum — Technology & Cost Detail"),
      body("This appendix breaks each workstream down to the task level: the specific technology or tooling used to build it, the Azure service (or existing shared infrastructure) it runs on, and — for every new paid service — the standalone monthly rate, how many months of the build phase it's billed for, and the resulting build-phase cost. Cloud service costs are Azure list-price estimates for the tiers named; confirm against the Azure Pricing Calculator before finalizing budget.", { italics: true, color: MUTED }),

      h2("A.1 Azure Migration"),
      makeTable(
        ["Task", "Technology / Tools", "Azure Service"],
        [
          ["Provision core infrastructure", "Azure App Service, Bicep/Terraform IaC — joins existing vnet_pi_southcentralus", "App Service (Premium P2v3)"],
          ["Deploy database schema", "Prisma migrate deploy, PostGIS extension, seed test data", "Database for PostgreSQL Flexible Server"],
          ["Configure file storage", "Azure Blob Storage SDK, SAS tokens", "Blob Storage (Hot LRS)"],
          ["Reconfigure integrations & secrets", "Stripe webhook re-registration, Resend domain verify, secrets stored in existing Key Vault", "kv-priusintelli-web (existing, reused)"],
          ["DNS cutover & custom domain", "New listener on existing Application Gateway; new endpoint on existing CDN profile; managed cert", "appgw_aptus_southcentralus (WAF_v2, existing), cdn-priusintelli (existing)"],
          ["Regression testing", "Playwright E2E suite (existing 20+ specs), Vitest", "Staging slot on new infra"],
        ],
        [26, 42, 32]
      ),
      new Paragraph({ spacing: { before: 140 }, children: [] }),
      makeTable(
        ["Service / Item", "Monthly Cost", "Build Months", "Build-Phase Cost"],
        [
          ["Azure App Service Plan (Premium P2v3, 2 instances)", "$500", "1", "$500"],
          ["Azure Database for PostgreSQL Flexible Server (Gen. Purpose, PostGIS)", "$600", "1", "$600"],
          ["Azure Blob Storage (Hot LRS, project files)", "$100", "1", "$100"],
          ["Application Gateway capacity increment (reuse existing appgw_aptus_southcentralus, WAF_v2)", "$60", "1", "$60"],
          ["CDN endpoint on existing cdn-priusintelli profile (usage-based, no fixed minimum)", "$0", "1", "$0"],
          ["Azure Application Insights (linked to existing la-pi-aptus Log Analytics workspace)", "$100", "1", "$100"],
          Object.assign(["Subtotal — Post-launch run rate $1,360/mo", "$1,360/mo", "", "$1,360"], { _bold: true }),
        ],
        [46, 18, 18, 18]
      ),
      body("Reuse scan of the live Azure subscription (2026-08): joins the existing vnet_pi_southcentralus VNet rather than a new one; reuses the existing appgw_aptus_southcentralus Application Gateway (WAF_v2) with a new listener instead of a new Azure Front Door + WAF profile — modeled as a capacity increment ($60/mo) instead of a full $250/mo Front Door+WAF line, trading away Front Door's global edge caching; reuses the existing cdn-priusintelli CDN profile via a new endpoint (usage-based, no fixed cost); reuses the existing kv-priusintelli-web Key Vault, removing that line item entirely; and links Application Insights to the existing la-pi-aptus Log Analytics workspace (same modeled cost — this saves setup effort, not $/mo). NOT reused: the App Service Plan (existing asp-dev1/asp-prod1 are Basic tier, no deployment slots or autoscale) and the Postgres Flexible Server (existing pi-pgsql-prod/dev are Burstable B1ms already shared by wikijs and Aptus OMS — adding a database there is a lower-cost fallback, not the default, given the shared-resource risk to a production system). Blob Storage could technically live in the existing pigisstorage4361 account, but its current containers use public blob access, which does not meet this plan's SAS-scoped security bar — kept as a separate line.", { italics: true, color: MUTED }),

      h2("A.2 Order Management"),
      makeTable(
        ["Task", "Technology / Tools", "Azure Service"],
        [
          ["Data consolidation pipeline", "Azure Data Factory, Python, SQL, tRPC ingestion routes", "Azure Data Factory"],
          ["Public API & partner integration layer", "Azure API Management, API keys/OAuth2, OpenAPI spec", "Azure API Management (Standard)"],
          ["Complete payment processing", "Stripe Checkout/Payment Intents integration, webhook handling, payment-confirmation flow via Resend email", "Stripe (existing), Resend (existing) — no new Azure service"],
          ["Automated quoting — define & build", "Requirements analysis of current pricing logic, then a Node/tRPC rules engine to automate it", "None (runs on existing App Service)"],
          ["Automated flight planning — geospatial engine", "Custom geospatial algorithm (coverage/overlap/altitude), Python/Turf.js, iterative validation against real flight data", "Compute on existing App Service; no new Azure service"],
          ["Security review of new public API", "Auth/rate-limit review, penetration spot-check", "None additional"],
          ["Regression testing", "Playwright/Vitest existing suite + new API/quoting/flight-plan tests", "Staging slot"],
        ],
        [26, 42, 32]
      ),
      new Paragraph({ spacing: { before: 140 }, children: [] }),
      makeTable(
        ["Service / Item", "Monthly Cost", "Build Months", "Build-Phase Cost"],
        [
          ["Azure API Management (Standard tier) — new public API layer", "$700", "2", "$1,400"],
          ["Azure Data Factory (data consolidation pipeline)", "$300", "2", "$600"],
          Object.assign(["Subtotal — Post-launch run rate $1,000/mo", "$1,000/mo", "", "$2,000"], { _bold: true }),
        ],
        [46, 18, 18, 18]
      ),
      body("Payment processing, automated quoting, and automated flight planning add no new Azure services — all three run as application logic on the App Service compute already provisioned in Azure Migration.", { italics: true, color: MUTED }),

      h2("A.3 Data Portal"),
      makeTable(
        ["Task", "Technology / Tools", "Azure Service"],
        [
          ["Customer upload & download to Blob (fast transfer)", "Azure Blob SDK parallel block transfer; AzCopy for bulk/CLI-driven transfers; resumable multipart upload for large files", "Azure Blob Storage (shared, from Azure Migration)"],
          ["Data visualization & download UI", "Portal view listing each project's files in Blob storage, with preview and one-click download via short-lived SAS links", "Azure Blob Storage (shared, list + SAS generation)"],
          ["Azure-native AI-tool egress path", "Azure Private Endpoint + VNet integration (keeps traffic off the public internet), metadata cataloging for AI consumption", "Private Endpoint, Blob Storage (shared)"],
          ["Data security hardening", "SSE encryption at rest (default) + TLS in transit; short-lived scoped SAS tokens; Azure AD RBAC for internal access; per-tenant container isolation", "Azure Defender for Storage, Key Vault (shared)"],
          ["Regression & security testing", "Playwright existing map/file specs + upload/egress penetration spot-check", "Staging slot"],
        ],
        [26, 42, 32]
      ),
      new Paragraph({ spacing: { before: 140 }, children: [] }),
      makeTable(
        ["Service / Item", "Monthly Cost", "Build Months", "Build-Phase Cost"],
        [
          ["CARTO basemap API subscription", "$50", "1", "$50"],
          ["Azure Private Endpoint (secure AI-tool access to Blob, no public egress)", "$30", "1.5", "$45"],
          ["Azure Defender for Storage (malware scanning on customer uploads)", "$40", "1.5", "$60"],
          Object.assign(["Subtotal — Post-launch run rate $120/mo", "$120/mo", "", "$155"], { _bold: true }),
        ],
        [46, 18, 18, 18]
      ),
      body("Blob Storage itself is not billed again here — it's the same Azure Blob Storage account provisioned once under Azure Migration; Data Portal's new cost is the security/access layer on top of it (CARTO, Private Endpoint, Defender for Storage).", { italics: true, color: MUTED }),
      new Paragraph({ spacing: { before: 140 }, children: [] }),
      h2("Fast Blob-to-file transfer — options considered"),
      body("For moving customer data between Azure Blob Storage and a file system quickly and securely:"),
      bullet("AzCopy — Microsoft's purpose-built CLI for bulk transfer in or out of Blob, using parallel chunked uploads/downloads; the default choice for large batch jobs and scriptable pipelines."),
      bullet("Azure Blob SDK parallel block transfer — for in-app transfers (e.g., a customer clicking \u201Cdownload\u201D in the portal), the SDK's parallel block upload/download gives AzCopy-like throughput without shelling out to a separate process."),
      bullet("Blobfuse2 / Azure ML datastore mount — lets AI compute (including Azure ML training jobs) read Blob data directly as a mounted file system, avoiding a full copy before processing."),
      bullet("Azure Data Box — only relevant for a one-time, terabyte-scale migration; not needed for this platform's file sizes (100MB per upload) or ongoing operation."),
      bullet("Azure Front Door / CDN with SAS tokens and HTTP range requests — for customer-facing download speed at the edge, without exposing the storage account directly."),

      h2("A.4 Business Intelligence"),
      makeTable(
        ["Task", "Technology / Tools", "Azure Service"],
        [
          ["Design decision-support & revenue data model", "Dimensional data modeling on the existing Postgres schema", "None (design phase)"],
          ["Real decision-support & revenue-visibility views", "Analytics Engineer semantic layer + BI Developer report/dashboard build (replaces today's basic stat cards)", "Existing App Service (shared)"],
          ["Cost allocation engine", "SQL/tRPC procedures against existing order/company data", "Existing Postgres (shared)"],
          ["Forecasting models", "Azure ML, Python (scikit-learn/Prophet)", "Azure ML workspace + training compute"],
          ["Integrate into existing dashboard", "Extend existing internal dashboard components (Epic 7.6)", "Existing App Service (shared)"],
          ["Validation & UAT", "Manual reconciliation against known figures", "None additional"],
        ],
        [26, 42, 32]
      ),
      new Paragraph({ spacing: { before: 140 }, children: [] }),
      makeTable(
        ["Service / Item", "Monthly Cost", "Build Months", "Build-Phase Cost"],
        [
          ["Azure ML workspace + training compute (forecasting)", "$500", "2", "$1,000"],
          Object.assign(["Subtotal — Post-launch run rate $500/mo", "$500/mo", "", "$1,000"], { _bold: true }),
        ],
        [46, 18, 18, 18]
      ),
      body("Decision support, revenue visibility, and cost allocation are built on the existing Postgres schema and App Service — only forecasting (Azure ML) introduces a new billed service.", { italics: true, color: MUTED }),

      new Paragraph({ spacing: { before: 200 }, children: [] }),
      h2("A.5 Combined recurring run cost, post-launch"),
      makeTable(
        ["Workstream", "Recurring Monthly Cost"],
        [
          ["Azure Migration (core platform)", "$1,360"],
          ["Order Management", "$1,000"],
          ["Data Portal", "$120"],
          ["Business Intelligence", "$500"],
          Object.assign(["Total", "$2,980/mo"], { _bold: true }),
        ],
        [60, 40]
      ),
      body("This is the standing Azure/third-party service bill once everything is live — it does not include ongoing engineering, support, or maintenance labor.", { italics: true, color: MUTED }),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("C:\\Users\\pi\\claude\\mercator_cost_model\\exec_summary\\Mercator_Executive_Summary.docx", buf);
  console.log("saved");
});
