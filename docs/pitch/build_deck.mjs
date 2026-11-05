// Builds docs/pitch/Guided-Search-8min.pptx — the 8-minute, five-speaker pitch deck.
//
//   cd docs/pitch && npm install && npm run build
//
// Slides follow the speaker run order and approved numbers in speakers/README.md. Speaker notes are pulled from
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

// The word-for-word section runs from its heading to the next "---" rule or "## " heading.
function sayText(file, heading = /^## Say\b.*$/m) {
  const p = path.join(SPEAKERS, file);
  if (!fs.existsSync(p)) return null;
  const md = fs.readFileSync(p, "utf8");
  const start = md.search(heading);
  if (start < 0) throw new Error(`${file}: no section matching ${heading}; update build_deck.mjs to the new script layout`);
  const body = md.slice(md.indexOf("\n", start) + 1);
  const end = body.search(/^(---\s*$|## )/m);
  return (end < 0 ? body : body.slice(0, end))
    .replace(/```\w*\n?/g, "")
    .replace(/\*\*|`/g, "")
    .replace(/(^|\s)\*([^*\n]+)\*/g, "$1$2")
    .replace(/[ \t]+$/gm, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

// Split one speaker's script across consecutive slides at the first words of each later part.
// A cut that no longer appears fails the build, so the slides can't drift from the script.
function splitSay(file, heading, ...cuts) {
  const text = sayText(file, heading);
  if (!text) return null;
  const parts = [];
  let rest = text;
  for (const cut of cuts) {
    const i = rest.indexOf(cut);
    if (i < 0) throw new Error(`${file}: split cue "${cut}" not found; update the cue in build_deck.mjs`);
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
    { placeholder: { options: { name: "title", type: "title", x: M, y: 1.9, w: 7.2, h: 2.0, margin: 0, fontSize: 54, bold: true, color: C.background1, align: "left", valign: "top" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: M, y: 4.1, w: 6.6, h: 1.5, margin: 0, fontSize: 20, color: C.accent6, valign: "top" }, text: "" } },
  ],
});

pres.defineSlideMaster({
  title: "Content",
  background: { color: C.background1 },
  objects: [
    { text: { text: "Guided Search · We investigate. You decide.", options: { x: M, y: 6.95, w: 8, h: 0.3, margin: 0, fontSize: 10, color: C.accent5, isTextBox: true } } },
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.45, w: W - 2 * M, h: 0.9, margin: 0, fontSize: 36, bold: true, color: C.text1, align: "left", valign: "middle" }, text: "" } },
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

const A = splitSay("01-host-impact.md", undefined, "We measured it.");
const E = splitSay("05-closer.md", /^## Part 2: Close.*$/m, "GreatSchools already has");

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
    who: "Person A — Host / Impact", clock: "0:00–0:35", advance: "on “We measured it.”",
    say: A?.[0], fallback: "Script: speakers/01-host-impact.md",
  });
}

// 2 — Host: the gap
{
  const s = pres.addSlide({ masterName: "Content", sectionTitle: "A · Host / Impact" });
  s.addText("The gap is the product", { placeholder: "title" });
  const hero = [
    ["68%", "of searches with a real need show at least one Unknown in the top 8", "23 / 34 eval searches"],
    ["25 / 25", "GreatSchools sample schools have no after-school care on file", "GreatSchools sample"],
    ["2,364", "Washington schools in state report-card data — none with after-school care", "WA OSPI · real data"],
  ];
  const cw = (W - 2 * M - 2 * 0.3) / 3, cy = 1.6, ch = 3.85;
  hero.forEach(([big, label, sub], i) => {
    const x = M + i * (cw + 0.3);
    card(s, x, cy, cw, ch, `stat ${big}`);
    text(s, big, { x: x + 0.35, y: cy + 0.3, w: cw - 0.7, h: 1.15, fontSize: 60, bold: true, fontFace: THEME.headFontFace, color: C.text2 });
    text(s, label, { x: x + 0.35, y: cy + 1.55, w: cw - 0.7, h: 1.2, fontSize: 18 });
    pill(s, x + 0.35, cy + ch - 0.75, "Unknown");
    text(s, sub, { x: x + 1.95, y: cy + ch - 0.75, w: cw - 2.3, h: 0.36, fontSize: 12, color: C.accent5, valign: "middle" });
  });
  text(s, [
    { text: "At GreatSchools scale:  ", options: { bold: true, color: C.text2 } },
    { text: "150k+", options: { bold: true, color: C.accent4, fontFace: THEME.headFontFace, fontSize: 28 } },
    { text: " school profiles   ·   " },
    { text: "~40M", options: { bold: true, color: C.accent4, fontFace: THEME.headFontFace, fontSize: 28 } },
    { text: " families a year" },
  ], { x: M, y: 5.7, w: W - 2 * M, h: 0.6, fontSize: 20, valign: "middle" });
  source(s, "Sources: docs/pitch/impact_counts.py on eval/queries.jsonl and Sample Data/ · data/wa/schools.json (OSPI) · GreatSchools About page");
  notes(s, {
    who: "Person A — Host / Impact", clock: "0:35–1:05", advance: "on “Here’s the live demo.” switch the screen to the live site and hand to Person B",
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
    ["1", "The brief is the contract", "Musts and preferences the parent can edit before we search"],
    ["2", "Hard filters", "Only city, grade and school type"],
    ["3", "Scored, not dropped", "Every other need moves the match %, with a citation"],
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
  text(s, [
    { text: "Unknown keeps the school on screen at half credit. Across our eval, missing data dropped " },
    { text: "0 schools", options: { bold: true } },
    { text: "." },
  ], { x: x + 0.35, y: 4.95, w: w - 0.7, h: 0.9, fontSize: 16 });
  source(s, "Seattle rows: public WA OSPI Report Card data · rules-path median first turn ≈ 0.01 s (README → Evaluation) · scores from backend/evidence/scorer.py");
  notes(s, {
    who: "Person B — Demo driver", clock: "1:05–3:00", advance: "backup only — stay on the live UI; show this slide if the demo site is down",
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
  lane("SEARCH · FOUR CDK STACKS, ONE ACCOUNT", 2.15);
  const sx = [M, 3.05, 5.5], sw = 2.05;
  node("Browser", "no login", sx[0], 2.15, sw);
  node("CloudFront", "React app on S3", sx[1], 2.15, sw);
  node("ECS Fargate", "API · rules engine", sx[2], 2.15, sw, C.text2, C.background1);
  arrow(s, sx[0] + sw + 0.05, 2.62, 0.3);
  arrow(s, sx[1] + sw + 0.05, 2.62, 0.3);
  // Services the API calls
  const svc = [["DynamoDB", "one table"], ["OpenSearch", "hybrid search"], ["Bedrock", "Haiku · Sonnet"]];
  svc.forEach(([l, sub], i) => node(l, sub, 8.15 + i * 1.55, 2.15, 1.45));
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

  text(s, [
    { text: "97% holdout recall", options: { bold: true, color: C.text2 } },
    { text: " with Bedrock on (96 / 99, never tuned) — still, a model never marks a fact Confirmed. Every service sits behind a flag with a local fallback; Guardrails strip PII from parent posts; Translate + Comprehend follow the parent’s language." },
  ], { x: M, y: 5.6, w: W - 2 * M, h: 0.75, fontSize: 14 });
  source(s, "docs/infra.md (GsAppStack, GsOpenSearchStack, GsGatewayStack, GsVoiceStack) · backend/config/models.yaml · README → Evaluation");
  notes(s, {
    who: "Person C — AWS architect", clock: "3:00–4:10", advance: "optional — flip here only if the deck is up; otherwise talk over the live results",
    say: sayText("03-aws-architect.md"), fallback: "Script: speakers/03-aws-architect.md",
  });
}

// 5 — Call lead (Person E answers the handset as the front office)
pres.addSection({ title: "D · Call lead" });
{
  const s = pres.addSlide({ masterName: "Content", sectionTitle: "D · Call lead" });
  s.addText("We call the school so the parent doesn’t", { placeholder: "title" });

  // Before → after on the top Seattle card
  card(s, M, 1.7, 5.6, 4.55, "the card");
  text(s, "TOP SEATTLE CARD", { x: M + 0.35, y: 1.95, w: 4.9, h: 0.3, fontSize: 12, bold: true, color: C.accent5, charSpacing: 2 });
  text(s, "After-school care", { x: M + 0.35, y: 2.45, w: 2.4, h: 0.36, valign: "middle", bold: true, fontSize: 18 });
  pill(s, M + 3.8, 2.45, "Unknown");
  s.addText("Have AI call · 1 question not on file", {
    objectName: "call button", shape: pres.ShapeType.roundRect, rectRadius: 0.12,
    x: M + 0.35, y: 3.1, w: 4.9, h: 0.6, margin: 0, align: "center", valign: "middle",
    fontSize: 14, bold: true, color: C.background1, fill: { color: C.accent4 }, isTextBox: true,
  });
  s.addShape(pres.ShapeType.line, { x: M + 2.8, y: 3.8, w: 0, h: 0.45, line: { color: C.text2, width: 2, endArrowType: "triangle" } });
  text(s, "What the school said", { x: M + 0.35, y: 4.35, w: 3.2, h: 0.36, valign: "middle", bold: true, fontSize: 18 });
  pill(s, M + 3.8, 4.35, "Confirmed");
  text(s, "“Yes, we have after-school care on campus until six\u00A0p.m. every school day.”", {
    x: M + 0.35, y: 4.85, w: 4.9, h: 0.8, fontSize: 16, italic: true, color: C.text2,
  });
  text(s, "Every parent who asks next gets it without a single extra call.", { x: M + 0.35, y: 5.7, w: 4.9, h: 0.4, fontSize: 14, color: C.accent5 });

  // Call timeline
  const x = 6.75, w = W - M - x;
  const steps = [
    ["Says it’s an AI, asks consent", "Washington and Florida both require every party’s consent to transcribe"],
    ["Asks the queued question", "Connect places the call · Polly speaks · Lex hears · Lambda asks Bedrock Haiku"],
    ["Code checks before the card changes", "The quote must be in the transcript; code parses “six p.m.”"],
  ];
  steps.forEach(([head, body], i) => {
    const y = 1.75 + i * 1.35;
    s.addText(String(i + 1), { shape: pres.ShapeType.ellipse, x, y, w: 0.55, h: 0.55, margin: 0, align: "center", valign: "middle", fontSize: 18, bold: true, color: C.background1, fill: { color: C.accent3 }, isTextBox: true });
    text(s, head, { x: x + 0.8, y: y - 0.02, w: w - 0.8, h: 0.34, fontSize: 18, bold: true });
    text(s, body, { x: x + 0.8, y: y + 0.36, w: w - 0.8, h: 0.6, fontSize: 14, color: C.accent5 });
  });
  text(s, "Backup: Jacksonville · Beauclerc STEM Middle — in our seeded demo data, 13 parents asked this same question. One call answers all of them.", {
    x, y: 5.6, w, h: 0.65, fontSize: 14, color: C.text1,
  });
  source(s, "backend/gaps/phone.py (the demo rings our own handset, never a real school) · seeded demand: data/synthetic/community_seed.json");
  notes(s, {
    who: "Person D — Call lead (Person E answers the handset; lines in 05-closer.md Part 1)", clock: "4:10–6:25",
    advance: "backup only — if the live call fails, show this slide while reading the backup line",
    say: sayText("04-call-lead.md"), fallback: "Script: speakers/04-call-lead.md",
  });
}

// 6 — Closer: what we measured, what it costs
pres.addSection({ title: "E · Closer" });
{
  const s = pres.addSlide({ masterName: "Content", sectionTitle: "E · Closer" });
  s.addText("Each answer gets cheaper as parents ask", { placeholder: "title" });
  const stats = [
    ["≈ $0.11", "a 3-minute AI school call at AWS list price"],
    ["0", "schools dropped for missing data in our eval"],
    ["2,364", "real Washington schools, deployed on AWS today"],
  ];
  stats.forEach(([big, label], i) => {
    const y = 1.7 + i * 1.5;
    text(s, big, { x: M, y, w: 4.6, h: 0.85, fontSize: 48, bold: true, fontFace: THEME.headFontFace, color: i === 0 ? C.accent4 : C.text2 });
    text(s, label, { x: M, y: y + 0.85, w: 4.6, h: 0.4, fontSize: 16 });
  });
  s.addChart(pres.ChartType.bar, [{ name: "Cost per parent (USD)", labels: ["1 parent", "5 parents", "13 parents"], values: [0.11, 0.022, 0.008] }], {
    objectName: "cost per parent chart",
    x: 5.6, y: 1.6, w: W - M - 5.6, h: 4.7, barDir: "col",
    chartColors: [HEX.accent3, HEX.accent3, HEX.accent4],
    showTitle: true, title: "One call’s cost, split across the parents it answers (USD)", titleFontSize: 16, titleColor: HEX.dk1, titleFontFace: "+mn-lt",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "$0.000", dataLabelFontSize: 14, dataLabelColor: HEX.dk1, dataLabelFontFace: "+mn-lt",
    catAxisLabelColor: HEX.accent5, catAxisLabelFontSize: 14, catAxisLabelFontFace: "+mn-lt",
    valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" },
    showLegend: false, barGapWidthPct: 60,
  });
  source(s, "docs/pitch/cost.md — priced, not billed: AWS list prices as of 2026-11-04 on a modeled 3-min call (Connect, Lex, Polly, Lambda, Haiku)");
  notes(s, {
    who: "Person E — Closer", clock: "6:25–7:25", advance: "after “…every service has a fallback.”",
    say: E?.[0], fallback: "Script: speakers/05-closer.md",
  });
}

// 7 — Closer: tagline + Q&A
{
  const s = pres.addSlide({ masterName: "Dark", sectionTitle: "E · Closer" });
  s.addText("ASK US ANYTHING", { placeholder: "kicker" });
  s.addText("We investigate.\nYou decide.", { placeholder: "title" });
  s.addText(`Try it live: ${LIVE_URL}`, { placeholder: "body" });
  const owners = [["Host · Impact", "A"], ["UI · demo", "B"], ["AWS · architecture", "C"], ["Voice · calls", "D"], ["Cost · feasibility", "E"]];
  const x = 8.35, w = 4.4;
  text(s, "Q&A — who takes what", { x, y: 1.35, w, h: 0.45, fontSize: 16, bold: true, color: C.accent1, charSpacing: 2 });
  owners.forEach(([topic, who], i) => {
    const y = 1.95 + i * 0.85;
    card(s, x, y, w, 0.68, topic, C.background1);
    s.addText(who, { shape: pres.ShapeType.ellipse, x: x + 0.2, y: y + 0.11, w: 0.46, h: 0.46, margin: 0, align: "center", valign: "middle", fontSize: 16, bold: true, color: C.background1, fill: { color: C.text2 }, isTextBox: true });
    text(s, topic, { x: x + 0.9, y: y + 0.11, w: w - 1.15, h: 0.46, fontSize: 18, bold: true, valign: "middle" });
  });
  notes(s, {
    who: "Person E — Closer", clock: "7:25–7:40, then Q&A to 8:00", advance: "stop talking after “questions”; Person A hosts Q&A (docs/pitch/judge-qa.md)",
    say: E?.[1], fallback: "Script: speakers/05-closer.md",
  });
}

// 8 — Appendix for Q&A: responsible AI
pres.addSection({ title: "Appendix · Q&A" });
{
  const s = pres.addSlide({ masterName: "Content", sectionTitle: "Appendix · Q&A" });
  s.addText("Responsible by default", { placeholder: "title" });
  const items = [
    ["AI disclosure", "Every call opens by saying it is an automated AI assistant"],
    ["Consent first", "Every party consents to transcription — if declined, we stop"],
    ["Code decides", "Model output is a draft until the rules engine checks it"],
    ["PII guardrails", "Bedrock Guardrails + local rules on parent posts"],
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
    who: "Q&A backup — not part of the 8-minute run", clock: "after 7:40",
    say: "Show only if a judge asks about safety, consent or privacy. Answers: docs/pitch/judge-qa.md and docs/pitch/responsible-ai.md.",
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
