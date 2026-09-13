const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3 x 7.5

// ---- Palette (Prius Intelli brand — pulled from theme1.xml in the 2026 General Template) ----
const NAVY = "1F3D32";       // dk2 — dominant dark forest green
const TEAL = "1E6F5C";       // accent1 — secondary
const AMBER = "E3B23C";      // accent6 — accent (gold)
const RUST = "4A8F8B";       // accent3 — 4th categorical track color (AI Workbench) — avoids brand red (accent5), which the template reserves for "what's wrong" warnings
const INK = "0B0B0B";        // dk1 — body text on light
const MUTED = "9AA5A1";      // accent4 — muted/caption text (matches template footer color exactly)
const LIGHT_BG = "F2F6F4";   // lt2 — brand off-white/mint background
const PANEL = "E6EFEB";      // light sage panel tint, derived from lt2
const WHITE = "FFFFFF";      // lt1
const MINT_TINT = "CFE8DC";  // light tint of accent2 (6BBF9C), for subtitle text on dark bg
const SAGE_ON_DARK = "AEBDB6"; // muted text on dark bg (tinted accent4)
const CARD_ON_DARK = "2C5245"; // lighter card fill on dark bg, derived from NAVY

const FONT_HEAD = "Segoe UI Semibold";
const FONT_BODY = "Segoe UI";

const LOGO_ICON = __dirname + "/brand_icon_teal_transparent.png"; // dark-green mark, transparent bg, for light backgrounds
const LOGO_WORDMARK_WHITE = __dirname + "/brand_wordmark_white.png"; // full lockup, white, for dark backgrounds

const W = 13.333, H = 7.5;

function bgSlide(dark) {
  const s = pres.addSlide();
  s.background = { color: dark ? NAVY : LIGHT_BG };
  return s;
}

// Matches the template's slide-master footer: centered copyright line (accent4, 9pt)
// plus the brand mark in the bottom-right corner at ~80% opacity.
function footer(s, label, dark) {
  s.addText("© 2026 Prius Intelli. All rights reserved.", {
    x: W / 2 - 2.5, y: H - 0.55, w: 5, h: 0.3,
    fontFace: FONT_BODY, fontSize: 9, color: dark ? SAGE_ON_DARK : MUTED,
    align: "center", margin: 0,
  });
  s.addText(label, {
    x: 0.5, y: H - 0.55, w: 5, h: 0.3,
    fontFace: FONT_BODY, fontSize: 9, color: dark ? SAGE_ON_DARK : MUTED,
    margin: 0,
  });
  s.addImage({ path: LOGO_ICON, x: W - 0.75, y: H - 0.72, w: 0.55, h: 0.55, transparency: 20 });
}

function iconCircle(s, x, y, d, fill, glyph, glyphColor) {
  s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { type: "none" } });
  s.addText(glyph, {
    x, y, w: d, h: d, align: "center", valign: "middle",
    fontFace: FONT_BODY, fontSize: d * 26, color: glyphColor || WHITE, bold: true, margin: 0,
  });
}

// =========================================================
// SLIDE 1 — Title
// =========================================================
{
  const s = bgSlide(true);

  // Subtle geometric texture: thin concentric-ish rings suggesting orbit/imagery scan
  for (let i = 0; i < 4; i++) {
    s.addShape(pres.shapes.OVAL, {
      x: 8.7 - i * 0.55, y: 0.9 - i * 0.55, w: 5 + i * 1.1, h: 5 + i * 1.1,
      fill: { type: "none" },
      line: { color: TEAL, width: 1, transparency: 55 + i * 8 },
    });
  }

  s.addImage({ path: LOGO_WORDMARK_WHITE, x: 0.85, y: 0.65, w: 1.15, h: 1.28 });

  s.addText("PLATFORM ROADMAP", {
    x: 0.9, y: 2.5, w: 10, h: 0.5,
    fontFace: FONT_BODY, fontSize: 15, color: AMBER, bold: true, charSpacing: 3, margin: 0,
  });
  s.addText("Mercator", {
    x: 0.85, y: 2.85, w: 10.7, h: 1.15,
    fontFace: FONT_HEAD, fontSize: 54, color: WHITE, bold: true, margin: 0,
  });
  s.addText("Order Management  ·  Data Portal  ·  AI Workbench  ·  Business Intelligence", {
    x: 0.9, y: 3.95, w: 10.7, h: 0.5,
    fontFace: FONT_BODY, fontSize: 15.5, color: MINT_TINT, margin: 0,
  });
  s.addText("A phased plan across four connected tracks", {
    x: 0.9, y: 4.5, w: 8, h: 0.5,
    fontFace: FONT_BODY, fontSize: 14, color: SAGE_ON_DARK, italic: true, margin: 0,
  });

  s.addShape(pres.shapes.LINE, {
    x: 0.9, y: 5.3, w: 3.2, h: 0, line: { color: TEAL, width: 1.5 },
  });
  s.addText("Executive Roadmap Briefing  ·  Trust what you see.", {
    x: 0.9, y: 5.45, w: 8, h: 0.4,
    fontFace: FONT_BODY, fontSize: 12, color: SAGE_ON_DARK, italic: true, margin: 0,
  });
}

// =========================================================
// SLIDE 2 — Executive Summary (data-flow diagram)
// =========================================================
function arrow(s, x1, y1, x2, y2, color, width, dashed) {
  const x = Math.min(x1, x2), y = Math.min(y1, y2);
  const w = Math.abs(x2 - x1) || 0.001, h = Math.abs(y2 - y1) || 0.001;
  s.addShape(pres.shapes.LINE, {
    x, y, w, h, flipH: x2 < x1, flipV: y2 < y1,
    line: { color, width, endArrowType: "triangle", dashType: dashed ? "dash" : "solid" },
  });
}

{
  const s = bgSlide(false);
  s.addText("Four initiatives, one platform: Mercator", {
    x: 0.6, y: 0.5, w: 12.1, h: 0.7,
    fontFace: FONT_HEAD, fontSize: 30, color: NAVY, bold: true, margin: 0,
  });
  s.addText(
    "Each track solves a distinct problem today, but all four share one foundation: clean, connected data about our projects, our orders, and our imagery. Sequencing them together lets each phase reinforce the next.",
    { x: 0.6, y: 1.25, w: 12.1, h: 0.5, fontFace: FONT_BODY, fontSize: 14, color: MUTED, margin: 0 }
  );

  const flow = [
    { glyph: "OM", color: NAVY, title: "Order Management", body: "Clients track their own orders directly, all pulling from one connected, API-ready source of truth." },
    { glyph: "DP", color: AMBER, title: "Data Portal", body: "Clients log in to browse every project they've ordered, explore it on a map, and pull finished imagery on demand." },
    { glyph: "AI", color: RUST, title: "AI Workbench", body: "AI spots what's changed on the ground, extracts the features that matter, and forecasts what's next for every client." },
  ];
  const bi = { glyph: "BI", color: TEAL, title: "Business Intelligence", body: "Turns operational data into the numbers leadership needs — cost, revenue, and what's coming next — so decisions are backed by evidence, not guesswork." };

  const rowY = 2.4, rowH = 1.55, boxW = 3.2, gap = 0.65;
  const totalW = 3 * boxW + 2 * gap;
  const startX = (W - totalW) / 2;
  const centers = flow.map((_, i) => startX + i * (boxW + gap) + boxW / 2);

  // Grouping container: OMS, Data Portal, and AI Workbench are the client-facing tracks
  const groupPad = 0.22;
  const groupX = startX - groupPad, groupY = rowY - groupPad - 0.16;
  const groupW = totalW + 2 * groupPad, groupH = rowH + 2 * groupPad + 0.16;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: groupX, y: groupY, w: groupW, h: groupH, rectRadius: 0.1,
    fill: { type: "none" }, line: { color: MUTED, width: 1.25, dashType: "dash" },
  });
  const groupLabelW = 1.85;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: groupX + 0.25, y: groupY - 0.14, w: groupLabelW, h: 0.28, rectRadius: 0.05,
    fill: { color: LIGHT_BG }, line: { type: "none" },
  });
  s.addText("CLIENT-FACING", {
    x: groupX + 0.25, y: groupY - 0.14, w: groupLabelW, h: 0.28, align: "center", valign: "middle",
    fontFace: FONT_BODY, fontSize: 10, color: MUTED, bold: true, charSpacing: 1.2, margin: 0,
  });

  flow.forEach((c, i) => {
    const x = startX + i * (boxW + gap);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x, y: rowY, w: boxW, h: rowH, rectRadius: 0.08,
      fill: { color: PANEL }, line: { type: "none" },
      shadow: { type: "outer", color: INK, opacity: 0.1, blur: 6, offset: 2, angle: 90 },
    });
    iconCircle(s, x + 0.24, rowY + 0.22, 0.55, c.color, c.glyph, WHITE);
    s.addText(c.title, {
      x: x + 0.94, y: rowY + 0.2, w: boxW - 1.15, h: 0.6, valign: "middle",
      fontFace: FONT_HEAD, fontSize: 14.5, color: NAVY, bold: true, margin: 0, lineSpacingMultiple: 1.0,
    });
    s.addText(c.body, {
      x: x + 0.24, y: rowY + 0.88, w: boxW - 0.48, h: rowH - 1.0,
      fontFace: FONT_BODY, fontSize: 10.3, color: INK, margin: 0, lineSpacingMultiple: 1.12, valign: "top",
    });
  });

  // Horizontal arrows: OMS -> Data Portal -> AI Workbench
  const midY = rowY + rowH / 2;
  arrow(s, startX + boxW, midY, startX + boxW + gap, midY, MUTED, 2.25);
  arrow(s, startX + 2 * boxW + gap, midY, startX + 2 * boxW + 2 * gap, midY, MUTED, 2.25);

  // Business Intelligence — a real initiative, same visual weight as the three tracks
  // above, just wider (it aggregates all three) and positioned downstream in the flow.
  const biW = 6.5, biH = 1.55, biX = centers[1] - biW / 2, biY = rowY + rowH + 0.7;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: biX, y: biY, w: biW, h: biH, rectRadius: 0.08,
    fill: { color: PANEL }, line: { type: "none" },
    shadow: { type: "outer", color: INK, opacity: 0.1, blur: 6, offset: 2, angle: 90 },
  });
  iconCircle(s, biX + 0.24, biY + 0.22, 0.55, bi.color, bi.glyph, WHITE);
  s.addText(bi.title, {
    x: biX + 0.94, y: biY + 0.2, w: biW - 1.15, h: 0.6, valign: "middle",
    fontFace: FONT_HEAD, fontSize: 14.5, color: NAVY, bold: true, margin: 0,
  });
  s.addText(bi.body, {
    x: biX + 0.24, y: biY + 0.88, w: biW - 0.48, h: biH - 1.0,
    fontFace: FONT_BODY, fontSize: 11, color: INK, margin: 0, lineSpacingMultiple: 1.15, valign: "top",
  });

  // Converging arrows: data flows in from all three tracks
  arrow(s, centers[0], rowY + rowH, biX + biW * 0.2, biY, TEAL, 2);
  arrow(s, centers[1], rowY + rowH, centers[1], biY, TEAL, 2);
  arrow(s, centers[2], rowY + rowH, biX + biW * 0.8, biY, TEAL, 2);

  footer(s, "Executive Summary", false);
}

// =========================================================
// SLIDE 3 — Capabilities at a glance
// =========================================================
{
  const s = bgSlide(false);
  s.addText("Capabilities at a glance", {
    x: 0.6, y: 0.5, w: 12, h: 0.7,
    fontFace: FONT_HEAD, fontSize: 30, color: NAVY, bold: true, margin: 0,
  });
  s.addText("Four tracks, sixteen core capabilities, one shared foundation.", {
    x: 0.6, y: 1.2, w: 12, h: 0.4,
    fontFace: FONT_BODY, fontSize: 14, color: MUTED, margin: 0,
  });

  const tracks = [
    { name: "Order Management", color: NAVY, capabilities: ["Customer Self Service", "Project Visibility", "Data Consolidation", "API Integration"] },
    { name: "Data Portal", color: AMBER, capabilities: ["Product Delivery", "Data Hosting", "Project Inventory", "Data Visualization"] },
    { name: "AI Workbench", color: RUST, capabilities: ["Client Interaction", "Change Detection", "Feature Extraction", "Predictive Modeling"] },
    { name: "Business Intelligence", color: TEAL, capabilities: ["Decision Support", "Forecasting", "Cost Allocation", "Revenue Visibility"] },
  ];

  const gridX = 2.55, gridY = 2.0, labelW = 1.55, rowH = 0.95, gapY = 0.22, chipGap = 0.15;
  const chipsAreaX = gridX + labelW, chipsAreaW = W - 0.6 - chipsAreaX;

  tracks.forEach((t, r) => {
    const rowY = gridY + r * (rowH + gapY);
    s.addText(t.name, {
      x: 0.6, y: rowY, w: labelW + 1.6, h: rowH,
      fontFace: FONT_HEAD, fontSize: 13.5, color: NAVY, bold: true, valign: "middle", margin: 0,
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x: gridX + labelW - 0.12, y: rowY, w: 0.05, h: rowH, fill: { color: t.color }, line: { type: "none" },
    });
    const n = t.capabilities.length;
    const chipW = (chipsAreaW - (n - 1) * chipGap) / n;
    t.capabilities.forEach((cap, c) => {
      const x = chipsAreaX + c * (chipW + chipGap);
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
        x, y: rowY, w: chipW, h: rowH, rectRadius: 0.06,
        fill: { color: t.color }, line: { type: "none" },
      });
      s.addText(cap, {
        x: x + 0.16, y: rowY, w: chipW - 0.32, h: rowH, valign: "middle",
        fontFace: FONT_BODY, fontSize: n > 3 ? 11.5 : 12.5, color: WHITE, bold: true, margin: 0, lineSpacingMultiple: 1.05,
      });
    });
  });

  footer(s, "Capabilities Overview", false);
}

// =========================================================
// Helper: build a "track detail" slide
// =========================================================
function trackSlide({ eyebrow, title, current, color, phases, calloutLabel = "Now" }) {
  const s = bgSlide(false);

  s.addText(eyebrow, {
    x: 0.6, y: 0.45, w: 8, h: 0.35,
    fontFace: FONT_BODY, fontSize: 13, color, bold: true, charSpacing: 2, margin: 0,
  });
  s.addText(title, {
    x: 0.6, y: 0.78, w: 12, h: 0.65,
    fontFace: FONT_HEAD, fontSize: 28, color: NAVY, bold: true, margin: 0,
  });

  // Current state panel
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.6, y: 1.65, w: 12.15, h: 1.0, rectRadius: 0.07,
    fill: { color: PANEL }, line: { type: "none" },
  });
  s.addText(calloutLabel.toUpperCase(), {
    x: 0.9, y: 1.65, w: 1.6, h: 1.0, valign: "middle",
    fontFace: FONT_BODY, fontSize: 11, color, bold: true, charSpacing: 1, margin: 0,
  });
  s.addText(current, {
    x: 2.5, y: 1.65, w: 9.9, h: 1.0, valign: "middle",
    fontFace: FONT_BODY, fontSize: 13.5, color: INK, margin: 0, lineSpacingMultiple: 1.15,
  });

  // Phase cards
  const cardW = 3.85, gap = 0.35, startX = 0.6, cardY = 2.95, cardH = 3.6;
  phases.forEach((p, i) => {
    const x = startX + i * (cardW + gap);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x, y: cardY, w: cardW, h: cardH, rectRadius: 0.08,
      fill: { color: i === 0 ? color : PANEL }, line: { type: "none" },
      shadow: { type: "outer", color: INK, opacity: 0.1, blur: 6, offset: 2, angle: 90 },
    });
    const onColor = i === 0 ? WHITE : NAVY;
    const bodyColor = i === 0 ? MINT_TINT : INK;
    const mutedOn = i === 0 ? MINT_TINT : MUTED;

    s.addText(["NEXT", "THEN", "LATER"][i], {
      x: x + 0.28, y: cardY + 0.25, w: cardW - 0.56, h: 0.3,
      fontFace: FONT_BODY, fontSize: 11, color: mutedOn, bold: true, charSpacing: 1.5, margin: 0,
    });
    s.addText(`Phase ${i + 1} — ${p.name}`, {
      x: x + 0.28, y: cardY + 0.6, w: cardW - 0.56, h: 0.75,
      fontFace: FONT_HEAD, fontSize: 16, color: onColor, bold: true, margin: 0, lineSpacingMultiple: 1.05,
    });
    s.addText(p.bullets.map((b, bi) => ({
      text: b,
      options: { bullet: { code: "2022", indent: 14 }, color: bodyColor, breakLine: bi < p.bullets.length - 1, paraSpaceAfter: 8 },
    })), {
      x: x + 0.28, y: cardY + 1.45, w: cardW - 0.56, h: cardH - 1.65,
      fontFace: FONT_BODY, fontSize: 11.5, margin: 0, valign: "top", lineSpacingMultiple: 1.1,
    });
  });

  footer(s, eyebrow, false);
  return s;
}


pres.writeFile({ fileName: "C:\\Users\\pi\\claude\\roadmap_deck\\Platform_Roadmap.pptx" }).then(() => {
  console.log("done");
});
