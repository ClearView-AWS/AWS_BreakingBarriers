// Builds docs/pitch/Guided-Search-8min.pptx — the 8-minute, five-speaker pitch deck.
//
//   cd docs/pitch && npm install && npm run build
//
// Slides follow the speaker run order in speakers/README.md. Speaker notes are pulled from
// the "## Say" section of each speakers/0N-*.md file, so edit the script there and rebuild;
// if a speaker file is missing, the slide keeps a short fallback note instead.
// Numbers on slides come from impact.md and cost.md — change them there first.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import pptxgen from "pptxgenjs";
import JSZip from "jszip";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(HERE, "Guided-Search-8min.pptx");
const SPEAKERS = path.join(HERE, "speakers");
const LIVE_URL = "dvpvz48phigre.cloudfront.net";

const THEME = {
  name: "Guided Search",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "17252F", // ink
    lt1: "FFFFFF",
    dk2: "0E3B43", // deep teal (dark slides)
    lt2: "EAF2F1", // mist (cards on light slides)
    accent1: "F2A33A", // Unknown — amber
    accent2: "23855A", // Confirmed — green
    accent3: "3D7EA6", // Partial — blue
    accent4: "E4572E", // call-to-action coral
    accent5: "5F6F7A", // muted slate
    accent6: "9FD3C7", // seafoam, text on dark
    hlink: "3D7EA6",
    folHlink: "5F6F7A",
  },
};
const HEX = THEME.colors;

// ---------- speaker notes from speakers/*.md ----------

function sayText(file) {
  const p = path.join(SPEAKERS, file);
  if (!fs.existsSync(p)) return null;
  const md = fs.readFileSync(p, "utf8");
  const start = md.search(/^## Say\b.*$/m);
  if (start < 0) return null;
  const body = md.slice(md.indexOf("\n", start) + 1);
  const end = body.search(/^(---\s*$|## (?!Say\b))/m);
  return (end < 0 ? body : body.slice(0, end))
    .replace(/```\w*\n?/g, "")
    .replace(/\*\*|`/g, "")
    .replace(/(^|\s)\*([^*\n]+)\*/g, "$1$2")
    .replace(/[ \t]+$/gm, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

// Split one speaker's script across consecutive slides at the first line of each later part.
function splitSay(file, ...cuts) {
  const text = sayText(file);
  if (!text) return null;
  const parts = [];
  let rest = text;
  for (const cut of cuts) {
    const i = rest.indexOf(cut);
    if (i < 0) { parts.push(null); continue; }
    parts.push(rest.slice(0, i).trim());
    rest = rest.slice(i);
  }
  parts.push(rest.trim());
  return parts;
}

function notes(slide, { who, clock, advance, say, fallback }) {
  const head = [`${who} · ${clock}`, advance ? `Advance: ${advance}` : null].filter(Boolean).join("\n");
  slide.addNotes(`${head}\n\n${say || fallback}`);
}

// ---------- deck ----------

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
pres.title = "Guided Search — 8-minute pitch";
pres.subject = "We investigate. You decide.";
pres.author = "ClearView-AWS";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const W = 13.333;
const M = 0.6;

pres.defineSlideMaster({
  title: "Dark",
  background: { color: C.text2 },
  objects: [
    { text: { text: LIVE_URL, options: { x: M, y: 6.75, w: 6, h: 0.35, margin: 0, fontSize: 12, color: C.accent6, isTextBox: true } } },
    { placeholder: { options: { name: "kicker", type: "body", x: M, y: 1.35, w: 7.2, h: 0.45, margin: 0, fontSize: 16, bold: true, color: C.accent1, charSpacing: 2 }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: M, y: 1.9, w: 7.2, h: 2.0, margin: 0, fontSize: 54, bold: true, color: C.background1, valign: "top" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: M, y: 4.1, w: 6.6, h: 1.5, margin: 0, fontSize: 20, color: C.accent6, valign: "top" }, text: "" } },
  ],
});

pres.defineSlideMaster({
  title: "Content",
  background: { color: C.background1 },
  objects: [
    { text: { text: "Guided Search · We investigate. You decide.", options: { x: M, y: 6.95, w: 8, h: 0.3, margin: 0, fontSize: 10, color: C.accent5, isTextBox: true } } },
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.45, w: W - 2 * M, h: 0.9, margin: 0, fontSize: 36, bold: true, color: C.text1, valign: "middle" }, text: "" } },
  ],
  slideNumber: { x: W - M - 0.6, y: 6.95, w: 0.6, h: 0.3, fontSize: 10, color: C.accent5, align: "right" },
});

const STATUS = {
  Confirmed: { fill: C.accent2, text: C.background1 },
  Partial: { fill: C.accent3, text: C.background1 },
  Unknown: { fill: C.accent1, text: C.text1 },
  "Needs attention": { fill: C.accent4, text: C.background1 },
};

// The deck's one motif: the evidence status pill parents see on every card.
function pill(slide, x, y, status, w = 1.45) {
  const s = STATUS[status];
  slide.addText(status, {
    objectName: `pill ${status}`, shape: pres.ShapeType.roundRect, rectRadius: 0.18,
    x, y, w, h: 0.36, margin: 0, align: "center", valign: "middle",
    fontSize: 12, bold: true, color: s.text, fill: { color: s.fill }, isTextBox: true,
  });
}

function card(slide, x, y, w, h, name, fill = C.background2) {
  slide.addShape(pres.ShapeType.roundRect, { objectName: name, x, y, w, h, rectRadius: 0.12, fill: { color: fill }, line: { type: "none" } });
}

function text(slide, str, opts) {
  slide.addText(str, { margin: 0, isTextBox: true, color: C.text1, fontSize: 16, valign: "top", ...opts });
}

function arrow(slide, x, y, w, color = C.accent5) {
  slide.addShape(pres.ShapeType.line, { x, y, w, h: 0, line: { color, width: 2, endArrowType: "triangle" } });
}

function source(slide, str) {
  text(slide, str, { x: M, y: 6.5, w: W - 2 * M, h: 0.3, fontSize: 10, color: C.accent5 });
}

const A = splitSay("01-host-impact.md", "GreatSchools already reaches");
const E = splitSay("05-closer.md", "No login.", "We investigate. You decide.");

// 1 — Host: hook
pres.addSection({ title: "A · Host / Impact" });
{
  const s = pres.addSlide({ masterName: "Dark", sectionTitle: "A · Host / Impact" });
  s.addText("GUIDED SEARCH FOR GREATSCHOOLS", { placeholder: "kicker" });
  s.addText("We investigate.\nYou decide.", { placeholder: "title" });
  s.addText("Missing facts stay on the screen. When parents share a question, we get the answer once — for everyone.", { placeholder: "body" });

  // Illustrative school card: the gap is visible, not hidden.
  const x = 8.35, y = 1.35, w = 4.4;
  card(s, x, y, w, 4.75, "school card", C.background1);
  text(s, "School card · illustrative", { x: x + 0.35, y: y + 0.3, w: 3.7, h: 0.3, fontSize: 12, color: C.accent5 });
  text(s, "Seattle middle school", { x: x + 0.35, y: y + 0.6, w: 3.7, h: 0.45, fontSize: 20, bold: true, fontFace: THEME.headFontFace });
  const rows = [["Gifted program", "Confirmed"], ["Small school", "Partial"], ["After-school care", "Unknown"]];
  rows.forEach(([need, status], i) => {
    const ry = y + 1.35 + i * 0.7;
    text(s, need, { x: x + 0.35, y: ry, w: 2.3, h: 0.36, valign: "middle" });
    pill(s, x + w - 0.35 - 1.45, ry, status);
  });
  s.addText("Have AI call · 1 question not on file", {
    objectName: "call button", shape: pres.ShapeType.roundRect, rectRadius: 0.12,
    x: x + 0.35, y: y + 3.75, w: w - 0.7, h: 0.6, margin: 0, align: "center", valign: "middle",
    fontSize: 14, bold: true, color: C.background1, fill: { color: C.accent4 }, isTextBox: true,
  });
  notes(s, {
    who: "Person A — Host / Impact", clock: "0:00–0:30", advance: "after “…a second job.”",
    say: A?.[0], fallback: "Script: speakers/01-host-impact.md",
  });
}

// 2 — Host: the gap
{
  const s = pres.addSlide({ masterName: "Content", sectionTitle: "A · Host / Impact" });
  s.addText("The gap is the product", { placeholder: "title" });
  const hero = [
    ["68%", "of need-bearing searches show at least one Unknown in the top 8 results", "23 / 34 eval searches"],
    ["25 / 25", "GreatSchools sample schools have no after-school care on file", "real GreatSchools sample"],
  ];
  hero.forEach(([big, label, sub], i) => {
    const x = M + i * 4.15, y = 1.75, w = 3.85, h = 4.4;
    card(s, x, y, w, h, `stat ${big}`);
    text(s, big, { x: x + 0.35, y: y + 0.4, w: w - 0.7, h: 1.3, fontSize: 66, bold: true, fontFace: THEME.headFontFace, color: C.text2 });
    text(s, label, { x: x + 0.35, y: y + 1.85, w: w - 0.7, h: 1.4, fontSize: 18 });
    pill(s, x + 0.35, y + h - 0.85, "Unknown");
    text(s, sub, { x: x + 1.95, y: y + h - 0.85, w: w - 2.3, h: 0.36, fontSize: 12, color: C.accent5, valign: "middle" });
  });
  const scaleX = M + 2 * 4.15 + 0.15;
  text(s, "At GreatSchools scale", { x: scaleX, y: 1.8, w: 3.7, h: 0.4, fontSize: 18, bold: true, color: C.text2 });
  [["150k+", "school profiles"], ["~40M", "families reached each year"]].forEach(([big, label], i) => {
    const y = 2.4 + i * 1.75;
    text(s, big, { x: scaleX, y, w: 3.7, h: 0.9, fontSize: 48, bold: true, fontFace: THEME.headFontFace, color: C.accent4 });
    text(s, label, { x: scaleX, y: y + 0.9, w: 3.7, h: 0.4, fontSize: 16 });
  });
  source(s, "Sources: docs/pitch/impact.md (eval/queries.jsonl via impact_counts.py; GreatSchools About page)");
  notes(s, {
    who: "Person A — Host / Impact", clock: "0:30–1:10", advance: "hand to Person B on “Over to our driver.” (switch screen to live demo)",
    say: A?.[1], fallback: "Script: speakers/01-host-impact.md",
  });
}

// 3 — Demo driver
pres.addSection({ title: "B · Demo driver" });
{
  const s = pres.addSlide({ masterName: "Content", sectionTitle: "B · Demo driver" });
  s.addText("Plain language in. Honest cards out.", { placeholder: "title" });
  text(s, "FIRST EXAMPLE CHIP", { x: M, y: 1.7, w: 6.4, h: 0.3, fontSize: 12, bold: true, color: C.accent5, charSpacing: 2 });
  card(s, M, 2.1, 6.4, 1.35, "prompt", C.text2);
  text(s, "Middle school in Seattle that must have a gifted program and after-school care. Prefer a small school.", {
    x: M + 0.3, y: 2.25, w: 5.8, h: 1.05, fontSize: 18, color: C.background1, valign: "middle",
  });
  const steps = [
    ["1", "Brief", "Parents edit must / nice / avoid before we search"],
    ["2", "Hard filters", "Only city, grade and school type"],
    ["3", "Scored, not dropped", "Every other need moves the match %"],
  ];
  steps.forEach(([n, head, body], i) => {
    const y = 3.85 + i * 0.85;
    s.addText(n, { shape: pres.ShapeType.ellipse, x: M, y, w: 0.55, h: 0.55, margin: 0, align: "center", valign: "middle", fontSize: 18, bold: true, color: C.background1, fill: { color: C.accent3 }, isTextBox: true });
    text(s, head, { x: M + 0.8, y: y - 0.02, w: 5.6, h: 0.32, fontSize: 16, bold: true });
    text(s, body, { x: M + 0.8, y: y + 0.28, w: 5.6, h: 0.3, fontSize: 14, color: C.accent5 });
  });

  // Score each status earns toward the match % (backend/evidence/scorer.py).
  const x = 7.6, w = W - M - x;
  card(s, x, 1.7, w, 4.55, "scoring");
  text(s, "What each fact is worth", { x: x + 0.35, y: 1.95, w: w - 0.7, h: 0.4, fontSize: 18, bold: true, color: C.text2 });
  const scale = [["Confirmed", 1.0], ["Partial", 0.6], ["Unknown", 0.5]];
  const barX = x + 2.05, barW = w - 2.05 - 1.0;
  scale.forEach(([status, v], i) => {
    const y = 2.65 + i * 0.75;
    pill(s, x + 0.35, y, status);
    s.addShape(pres.ShapeType.rect, { objectName: `bar ${status}`, x: barX, y: y + 0.06, w: barW * v, h: 0.24, fill: { color: STATUS[status].fill }, line: { type: "none" } });
    text(s, v.toFixed(1), { x: barX + barW * v + 0.12, y, w: 0.6, h: 0.36, fontSize: 16, bold: true, valign: "middle" });
  });
  text(s, "Unknown after-school care keeps the school on screen at half credit — it is never filtered out.", {
    x: x + 0.35, y: 4.95, w: w - 0.7, h: 0.9, fontSize: 16,
  });
  source(s, "Seattle rows: public WA OSPI Report Card data (~2,300 schools) · rules-first search median ≈ 0.02 s · scores from backend/evidence/scorer.py");
  notes(s, {
    who: "Person B — Demo driver", clock: "1:10–3:25", advance: "backup only — stay on the live UI; show this slide if the demo site is down",
    say: sayText("02-demo-driver.md"), fallback: "Script: speakers/02-demo-driver.md",
  });
}

// 4 — AWS architect
pres.addSection({ title: "C · AWS architect" });
{
  const s = pres.addSlide({ masterName: "Content", sectionTitle: "C · AWS architect" });
  s.addText("Model drafts. Code decides.", { placeholder: "title" });
  const node = (label, sub, x, y, w, fill = C.background2, color = C.text1) => {
    s.addText([
      { text: label, options: { bold: true, fontSize: 16, breakLine: !!sub } },
      ...(sub ? [{ text: sub, options: { fontSize: 12 } }] : []),
    ], { objectName: label, shape: pres.ShapeType.roundRect, rectRadius: 0.1, x, y, w, h: 0.95, margin: 4, align: "center", valign: "middle", color, fill: { color: fill }, isTextBox: true });
  };
  const lane = (label, y) => text(s, label, { x: M, y: y - 0.45, w: 6, h: 0.35, fontSize: 12, bold: true, color: C.accent5, charSpacing: 2 });

  // Search lane
  lane("SEARCH", 2.15);
  const sx = [M, 3.05, 5.5], sw = 2.05;
  node("Browser", "no login", sx[0], 2.15, sw);
  node("CloudFront", "", sx[1], 2.15, sw);
  node("Fargate API", "rules engine", sx[2], 2.15, sw, C.text2, C.background1);
  arrow(s, sx[0] + sw + 0.05, 2.62, 0.3);
  arrow(s, sx[1] + sw + 0.05, 2.62, 0.3);
  // Services the API calls
  const svc = [["OpenSearch", "when enabled"], ["DynamoDB", "sessions · overlays"], ["Bedrock", "drafts · behind flags"]];
  svc.forEach(([l, sub], i) => node(l, sub, 8.15 + i * 1.55 - 0.0, 2.15, 1.45));
  arrow(s, sx[2] + sw + 0.05, 2.62, 0.5);

  // Voice lane
  lane("VOICE LOOP", 4.3);
  const voice = [["Connect", "places call"], ["Polly", "speaks"], ["Lex", "speech → text"], ["Lambda", "next turn"], ["Bedrock Haiku", "drafts line"]];
  const vw = 1.75, vg = 0.4;
  voice.forEach(([l, sub], i) => {
    const x = M + i * (vw + vg);
    node(l, sub, x, 4.3, vw);
    arrow(s, x + vw + 0.05, 4.77, vg - 0.1);
  });
  node("Code check", "then card flips", M + 5 * (vw + vg), 4.3, W - M - (M + 5 * (vw + vg)), C.accent2, C.background1);

  text(s, "Also on the path: Translate + Comprehend follow the parent’s language · Bedrock Guardrails screen community posts for PII · local rules fallback keeps an empty sandbox running", {
    x: M, y: 5.6, w: W - 2 * M, h: 0.7, fontSize: 14, color: C.text1,
  });
  source(s, "Architecture: docs/how-it-works.md · infra/lib/app-stack.ts");
  notes(s, {
    who: "Person C — AWS architect", clock: "3:25–4:25", advance: "optional — flip here only if the deck is up; otherwise talk over the live results",
    say: sayText("03-aws-architect.md"), fallback: "Script: speakers/03-aws-architect.md",
  });
}

// 5 — Call lead
pres.addSection({ title: "D · Call lead" });
{
  const s = pres.addSlide({ masterName: "Content", sectionTitle: "D · Call lead" });
  s.addText("One call answers every parent who asked", { placeholder: "title" });

  // 13 parents → 1 call (Beauclerc after-care seed)
  card(s, M, 1.7, 5.6, 4.55, "shared question");
  text(s, "13", { x: M + 0.35, y: 1.9, w: 1.9, h: 1.1, fontSize: 72, bold: true, fontFace: THEME.headFontFace, color: C.text2 });
  text(s, "parents asked Beauclerc STEM Middle about after-school care this month", { x: M + 2.2, y: 2.05, w: 3.1, h: 0.95, fontSize: 16 });
  for (let i = 0; i < 13; i++) {
    const col = i % 5, row = Math.floor(i / 5);
    s.addShape(pres.ShapeType.ellipse, { objectName: `parent ${i + 1}`, x: M + 0.45 + col * 0.5, y: 3.45 + row * 0.5, w: 0.34, h: 0.34, fill: { color: C.accent1 }, line: { type: "none" } });
  }
  arrow(s, M + 3.05, 3.95, 0.7, C.text2);
  s.addText("1 AI call", { shape: pres.ShapeType.ellipse, x: M + 3.9, y: 3.35, w: 1.25, h: 1.25, margin: 0, align: "center", valign: "middle", fontSize: 16, bold: true, color: C.background1, fill: { color: C.accent4 }, isTextBox: true });
  text(s, "Without Guided Search: 13 office calls during work hours. With it: one call, ≈2.6 parent-hours back.", { x: M + 0.35, y: 5.1, w: 4.9, h: 0.9, fontSize: 14, color: C.accent5 });

  // Call timeline
  const x = 6.75, w = W - M - x;
  const steps = [
    ["Discloses AI, asks consent", "Florida all-party consent before any question; a no means stop and email instead"],
    ["Asks every queued question", "Connect · Polly · Lex · Lambda · Bedrock Haiku"],
    ["Code checks the answer", "A fluent wrong answer cannot become a Confirmed fact"],
  ];
  steps.forEach(([head, body], i) => {
    const y = 1.75 + i * 1.05;
    s.addText(String(i + 1), { shape: pres.ShapeType.ellipse, x, y, w: 0.55, h: 0.55, margin: 0, align: "center", valign: "middle", fontSize: 18, bold: true, color: C.background1, fill: { color: C.accent3 }, isTextBox: true });
    text(s, head, { x: x + 0.8, y: y - 0.02, w: w - 0.8, h: 0.34, fontSize: 18, bold: true });
    text(s, body, { x: x + 0.8, y: y + 0.34, w: w - 0.8, h: 0.55, fontSize: 14, color: C.accent5 });
  });
  text(s, "After-school care", { x, y: 5.1, w: 2.2, h: 0.36, valign: "middle", bold: true });
  pill(s, x + 2.25, 5.1, "Unknown");
  arrow(s, x + 3.8, 5.28, 0.45, C.text2);
  pill(s, x + 4.35, 5.1, "Confirmed");
  text(s, "with the school’s own quote — shared with every parent who asked", { x, y: 5.6, w, h: 0.4, fontSize: 14, color: C.accent5 });
  source(s, "Demand: data/synthetic/community_seed.json · parent-hours: docs/pitch/impact.md (12 min/call assumption) · demo dials +1 206-535-0596 only");
  notes(s, {
    who: "Person D — Call lead", clock: "4:25–6:40", advance: "backup only — if the live call fails, show this slide while reading the backup line",
    say: sayText("04-call-lead.md"), fallback: "Script: speakers/04-call-lead.md",
  });
}

// 6 — Closer: unit economics
pres.addSection({ title: "E · Closer" });
{
  const s = pres.addSlide({ masterName: "Content", sectionTitle: "E · Closer" });
  s.addText("Under a cent per family", { placeholder: "title" });
  const stats = [
    ["≈ $0.11", "variable AWS cost of one 3-minute AI school call"],
    ["$0.008", "per parent when 13 share the answer"],
    ["0.02 s", "median rules-first search turn"],
  ];
  stats.forEach(([big, label], i) => {
    const y = 1.7 + i * 1.5;
    text(s, big, { x: M, y, w: 4.4, h: 0.85, fontSize: 48, bold: true, fontFace: THEME.headFontFace, color: i === 1 ? C.accent4 : C.text2 });
    text(s, label, { x: M, y: y + 0.85, w: 4.4, h: 0.4, fontSize: 16 });
  });
  s.addChart(pres.ChartType.bar, [{ name: "Cost per parent (USD)", labels: ["1 parent", "5 parents", "13 parents"], values: [0.11, 0.022, 0.008] }], {
    objectName: "cost per parent chart",
    x: 5.6, y: 1.6, w: W - M - 5.6, h: 4.7, barDir: "col",
    chartColors: [HEX.accent3, HEX.accent3, HEX.accent4],
    showTitle: true, title: "Cost per parent served by one call (USD)", titleFontSize: 16, titleColor: HEX.dk1, titleFontFace: "+mn-lt",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "$0.000", dataLabelFontSize: 14, dataLabelColor: HEX.dk1, dataLabelFontFace: "+mn-lt",
    catAxisLabelColor: HEX.accent5, catAxisLabelFontSize: 14, catAxisLabelFontFace: "+mn-lt",
    valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" },
    showLegend: false, barGapWidthPct: 60,
  });
  source(s, "docs/pitch/cost.md — AWS public pricing as of 2026-11-04; call shape (3 min, 6 turns, 800 chars) is an assumption");
  notes(s, {
    who: "Person E — Closer / Feasibility", clock: "6:40–7:05", advance: "after “…without hiding schools when a field is blank.”",
    say: E?.[0], fallback: "Script: speakers/05-closer.md",
  });
}

// 7 — Closer: responsible by default
{
  const s = pres.addSlide({ masterName: "Content", sectionTitle: "E · Closer" });
  s.addText("Responsible by default", { placeholder: "title" });
  const items = [
    ["AI disclosure", "Every call opens by saying it is an automated AI assistant"],
    ["Consent first", "Fla. § 934.03 all-party consent — if declined, we stop"],
    ["Code decides", "Model output is a draft until the rules engine checks it"],
    ["PII guardrails", "Bedrock Guardrails + local rules on community posts"],
    ["No login", "Parents search without an account"],
    ["Citations", "Every Confirmed fact names its source field"],
  ];
  const cw = (W - 2 * M - 2 * 0.3) / 3, ch = 2.15;
  items.forEach(([head, body], i) => {
    const x = M + (i % 3) * (cw + 0.3), y = 1.7 + Math.floor(i / 3) * (ch + 0.3);
    card(s, x, y, cw, ch, head);
    s.addShape(pres.ShapeType.ellipse, { x: x + 0.35, y: y + 0.35, w: 0.42, h: 0.42, fill: { color: C.accent2 }, line: { type: "none" } });
    text(s, "✓", { x: x + 0.35, y: y + 0.35, w: 0.42, h: 0.42, align: "center", valign: "middle", fontSize: 16, bold: true, color: C.background1 });
    text(s, head, { x: x + 0.95, y: y + 0.35, w: cw - 1.3, h: 0.42, fontSize: 20, bold: true, valign: "middle" });
    text(s, body, { x: x + 0.35, y: y + 1.0, w: cw - 0.7, h: 0.95, fontSize: 16 });
  });
  source(s, "docs/pitch/responsible-ai.md (not legal advice) · backend/gaps/phone.py · backend/community/safety.py");
  notes(s, {
    who: "Person E — Closer / Feasibility", clock: "7:05–7:20", advance: "after “…Guardrails on community text.”",
    say: E?.[1], fallback: "Script: speakers/05-closer.md",
  });
}

// 8 — Closer: tagline + Q&A
{
  const s = pres.addSlide({ masterName: "Dark", sectionTitle: "E · Closer" });
  s.addText("ASK US ANYTHING", { placeholder: "kicker" });
  s.addText("We investigate.\nYou decide.", { placeholder: "title" });
  s.addText(`Try it live: ${LIVE_URL}`, { placeholder: "body" });
  const owners = [["Host · Impact", "A"], ["UI · demo", "B"], ["AWS · architecture", "C"], ["Voice · calls", "D"]];
  const x = 8.35, w = 4.4;
  text(s, "Q&A — who takes what", { x, y: 1.35, w, h: 0.45, fontSize: 16, bold: true, color: C.accent1, charSpacing: 2 });
  owners.forEach(([topic, who], i) => {
    const y = 2.0 + i * 0.95;
    card(s, x, y, w, 0.75, topic, C.background1);
    s.addText(who, { shape: pres.ShapeType.ellipse, x: x + 0.2, y: y + 0.13, w: 0.5, h: 0.5, margin: 0, align: "center", valign: "middle", fontSize: 16, bold: true, color: C.background1, fill: { color: C.text2 }, isTextBox: true });
    text(s, topic, { x: x + 0.95, y: y + 0.13, w: w - 1.2, h: 0.5, fontSize: 18, bold: true, valign: "middle" });
  });
  notes(s, {
    who: "Person E — Closer / Feasibility", clock: "7:20–7:40, then Q&A to 8:00", advance: "stop talking; Person A hosts Q&A (docs/pitch/judge-qa.md)",
    say: E?.[2], fallback: "Script: speakers/05-closer.md",
  });
}

await pres.writeFile({ fileName: OUT });
await applyTheme(OUT, THEME);
console.log(`Wrote ${path.relative(process.cwd(), OUT) || OUT}`);

// pptxgenjs writes Office's stock palette into the theme; swap in THEME.colors so scheme
// colors resolve to ours (and stay restyleable in PowerPoint's Design tab).
async function applyTheme(file, theme) {
  const slots = ["dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6", "hlink", "folHlink"];
  const zip = await JSZip.loadAsync(fs.readFileSync(file));
  const part = "ppt/theme/theme1.xml";
  const scheme = `<a:clrScheme name="${theme.name}">` + slots.map((k) => `<a:${k}><a:srgbClr val="${theme.colors[k]}"/></a:${k}>`).join("") + "</a:clrScheme>";
  const xml = (await zip.file(part).async("string"))
    .replace(/<a:clrScheme\b[\s\S]*?<\/a:clrScheme>/, () => scheme)
    .replace(/(<a:(?:theme|fontScheme)\b[^>]*?\bname=")[^"]*"/g, (_, head) => `${head}${theme.name}"`);
  zip.file(part, xml);
  for (const name of Object.keys(zip.files)) {
    if (!name.endsWith(".xml")) continue;
    const bad = (await zip.file(name).async("string")).match(/<a:srgbClr val="((?![0-9A-Fa-f]{6}")[^"]*)"/);
    if (bad) throw new Error(`${name}: <a:srgbClr val="${bad[1]}"> — a scheme color was passed to a hex-only option`);
  }
  fs.writeFileSync(file, await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" }));
}
