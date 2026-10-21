#!/usr/bin/env node
/* Build the three "The Chip That Says No" posts as .docx from the Markdown in ../ (the blog folder).
 * Usage: node build.js [outdir]      (default: the blog folder; figures resolve relative to each .md)
 * Needs the `docx` npm package (npm install in this folder, or a global install).
 */
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, ImageRun, ExternalHyperlink, Footer, Header, PageNumber,
  LevelFormat, PageBreak, LineRuleType,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const OUT = path.resolve(process.argv[2] || ROOT);
fs.mkdirSync(OUT, { recursive: true });

const PAGE_W = 12240, PAGE_H = 15840, MARGIN = 1440;
const CONTENT_W = PAGE_W - 2 * MARGIN; // 9360 DXA = 6.5in
const IMG_W_PX = 624; // 6.5in at 96 dpi

const FONT_BODY = "Georgia", FONT_HEAD = "Arial", FONT_CODE = "Consolas";
const INK = "2C2C2A", QUIET = "5F5E5A", RULE = "C9C7BE", HEAD = "1F2A44", LINK = "185FA5";

const POSTS = [
  { src: "02-the-chip-that-says-no-1-plain-english.md", series: "The Chip That Says No · Part 1 of 4" },
  { src: "03-the-chip-that-says-no-2-with-the-technical-detail.md", series: "The Chip That Says No · Part 2 of 4" },
  { src: "04-the-chip-that-says-no-3-the-silicon-design.md", series: "The Chip That Says No · Part 3 of 4" },
  { src: "05-the-chip-that-says-no-4-the-governor-in-the-rack.md", series: "The Chip That Says No · Part 4 of 4" },
  { src: "06-the-chip-that-says-no-5-what-the-first-experiments-found.md", series: "The Chip That Says No · Part 5: what the first experiments found" },
].map((p) => ({ ...p, out: p.src.replace(/\.md$/, ".docx") }));

// ------------------------------------------------------------------ inline markdown
function inline(text, base = {}) {
  const runs = [];
  const re = /(\*\*[^*]+\*\*|\*[^*\n]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;
  let last = 0, m;
  const push = (t, extra = {}) => { if (t) runs.push(new TextRun({ text: t, ...base, ...extra })); };
  while ((m = re.exec(text)) !== null) {
    push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) push(tok.slice(2, -2), { bold: true });
    else if (tok.startsWith("`")) push(tok.slice(1, -1), { font: FONT_CODE, size: (base.size || 22) - 2 });
    else if (tok.startsWith("[")) {
      const mm = /\[([^\]]+)\]\(([^)]+)\)/.exec(tok);
      runs.push(new ExternalHyperlink({
        link: mm[2],
        children: inline(mm[1], { ...base, style: "Hyperlink" }),   // link text may hold *italics*, **bold**, `code`
      }));
    } else push(tok.slice(1, -1), { italics: true });
    last = m.index + tok.length;
  }
  push(text.slice(last));
  return runs;
}

// ------------------------------------------------------------------ helpers
function pngSize(buf) {
  return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) };
}

function colWidths(rows) {
  const n = rows[0].length;
  const lens = new Array(n).fill(0), tok = new Array(n).fill(0);
  for (const r of rows) r.forEach((c, i) => {
    const plain = c.replace(/[*`]/g, "");
    lens[i] = Math.max(lens[i], Math.min(plain.length, 80));
    for (const w of plain.split(/\s+/)) tok[i] = Math.max(tok[i], w.length);
  });
  // minimum width: the longest unbreakable token at ~105 DXA per character, plus cell margins
  const mins = tok.map((t) => Math.max(1200, t * 105 + 260));
  const weights = lens.map((l) => Math.pow(Math.max(l, 1), 0.75));
  const sumW = weights.reduce((a, b) => a + b, 0);
  let w = weights.map((x, i) => Math.max(mins[i], Math.round((CONTENT_W * x) / sumW)));
  let total = w.reduce((a, b) => a + b, 0);
  if (total > CONTENT_W) {
    const slack = w.map((x, i) => x - mins[i]);
    const sumSlack = slack.reduce((a, b) => a + b, 0);
    const excess = total - CONTENT_W;
    if (sumSlack >= excess) w = w.map((x, i) => x - Math.round((excess * slack[i]) / sumSlack));
    else w = w.map((x) => Math.round((x * CONTENT_W) / total));
  } else if (total < CONTENT_W) {
    const rem = CONTENT_W - total;
    w = w.map((x, i) => x + Math.round((rem * weights[i]) / sumW));
  }
  total = w.reduce((a, b) => a + b, 0);
  w[n - 1] += CONTENT_W - total;
  return w;
}

function makeTable(rows) {
  const widths = colWidths(rows);
  const border = { style: BorderStyle.SINGLE, size: 4, color: RULE };
  const trs = rows.map((cells, ri) => new TableRow({
    tableHeader: ri === 0,
    cantSplit: true,
    children: cells.map((c, ci) => new TableCell({
      width: { size: widths[ci], type: WidthType.DXA },
      margins: { top: 70, bottom: 70, left: 100, right: 100 },
      shading: ri === 0 ? { type: ShadingType.CLEAR, fill: "E9E8E2", color: "auto" } : undefined,
      children: [new Paragraph({
        spacing: { after: 0, line: 252, lineRule: LineRuleType.AUTO },
        children: inline(c, { size: 18, font: FONT_BODY, bold: ri === 0 ? true : undefined, color: INK }),
      })],
    })),
  }));
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: widths,
    borders: { top: border, bottom: border, left: border, right: border, insideHorizontal: border, insideVertical: border },
    rows: trs,
  });
}

// ------------------------------------------------------------------ block parser
function parse(md, srcDir, state) {
  const lines = md.split(/\r?\n/);
  const out = [];
  let i = 0;
  let para = [];
  const flushPara = () => {
    if (para.length) {
      out.push(new Paragraph({ children: inline(para.join(" ")), spacing: { after: 160, line: 276, lineRule: LineRuleType.AUTO } }));
      para = [];
    }
  };
  while (i < lines.length) {
    const line = lines[i];
    const t = line.trim();

    if (t === "") { flushPara(); i++; continue; }

    if (t.startsWith("```")) {
      flushPara();
      i++;
      const code = [];
      while (i < lines.length && !lines[i].trim().startsWith("```")) { code.push(lines[i]); i++; }
      i++;
      code.forEach((c, k) => out.push(new Paragraph({
        shading: { type: ShadingType.CLEAR, fill: "F3F2EE", color: "auto" },
        spacing: { before: k === 0 ? 120 : 0, after: k === code.length - 1 ? 200 : 0, line: 252, lineRule: LineRuleType.AUTO },
        indent: { left: 240, right: 240 },
        children: [new TextRun({ text: c.length ? c : " ", font: FONT_CODE, size: 18, color: INK })],
      })));
      continue;
    }

    if (t === "<<<pagebreak>>>") { flushPara(); out.push(new Paragraph({ children: [new PageBreak()] })); i++; continue; }

    if (t === "---") {
      flushPara();
      out.push(new Paragraph({ border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: RULE, space: 1 } }, spacing: { before: 120, after: 240 }, children: [] }));
      i++; continue;
    }

    const img = /^!\[([^\]]*)\]\(([^)]+)\)$/.exec(t);
    if (img) {
      flushPara();
      const p = path.resolve(srcDir, img[2]);
      const buf = fs.readFileSync(p);
      const { w, h } = pngSize(buf);
      const width = IMG_W_PX, height = Math.round((IMG_W_PX * h) / w);
      state.fig += 1;
      out.push(new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { before: 200, after: 80 }, keepNext: true,
        children: [new ImageRun({ type: "png", data: buf, transformation: { width, height } })],
      }));
      out.push(new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { after: 240 },
        children: [new TextRun({ text: `Figure ${state.fig}. ${img[1]}`, italics: true, size: 19, color: QUIET, font: FONT_BODY })],
      }));
      i++; continue;
    }

    if (t.startsWith("|")) {
      flushPara();
      const rows = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        const r = lines[i].trim();
        if (!/^\|\s*-+/.test(r)) rows.push(r.slice(1, -1).split("|").map((c) => c.trim()));
        i++;
      }
      out.push(makeTable(rows));
      out.push(new Paragraph({ spacing: { after: 120 }, children: [] }));
      continue;
    }

    const h = /^(#{1,4})\s+(.*)$/.exec(t);
    if (h) {
      flushPara();
      const lvl = h[1].length;
      if (lvl === 1) {
        out.push(new Paragraph({ heading: HeadingLevel.TITLE, children: inline(h[2]) }));
        // byline directly after the title
        if (i + 2 < lines.length && /^By\s/.test(lines[i + 2].trim())) {
          out.push(new Paragraph({ spacing: { after: 240 }, children: [new TextRun({ text: lines[i + 2].trim(), italics: true, size: 20, color: QUIET, font: FONT_HEAD })] }));
          i += 2;
        }
      } else {
        const map = { 2: HeadingLevel.HEADING_1, 3: HeadingLevel.HEADING_2, 4: HeadingLevel.HEADING_3 };
        out.push(new Paragraph({ heading: map[lvl], keepNext: true, children: inline(h[2]) }));
      }
      i++; continue;
    }

    if (t.startsWith("> ")) {
      flushPara();
      const q = [];
      while (i < lines.length && lines[i].trim().startsWith("> ")) { q.push(lines[i].trim().slice(2)); i++; }
      out.push(new Paragraph({
        border: { left: { style: BorderStyle.SINGLE, size: 18, color: LINK, space: 12 } },
        indent: { left: 360 }, spacing: { before: 120, after: 240, line: 276, lineRule: LineRuleType.AUTO },
        children: inline(q.join(" "), { italics: true, size: 23, color: INK }),
      }));
      continue;
    }

    const bul = /^(\s*)[-*]\s+(.*)$/.exec(line);
    if (bul) {
      flushPara();
      while (i < lines.length) {
        const b = /^(\s*)[-*]\s+(.*)$/.exec(lines[i]);
        if (!b) break;
        const level = b[1].length >= 2 ? 1 : 0;
        out.push(new Paragraph({ numbering: { reference: "bullets", level }, spacing: { after: 100, line: 276, lineRule: LineRuleType.AUTO }, children: inline(b[2]) }));
        i++;
      }
      continue;
    }

    const num = /^\s*\d+\.\s+(.*)$/.exec(line);
    if (num) {
      flushPara();
      state.list += 1;
      while (i < lines.length) {
        const b = /^\s*\d+\.\s+(.*)$/.exec(lines[i]);
        if (!b) break;
        out.push(new Paragraph({ numbering: { reference: "numbers", level: 0, instance: state.list }, spacing: { after: 100, line: 276, lineRule: LineRuleType.AUTO }, children: inline(b[1]) }));
        i++;
      }
      continue;
    }

    para.push(t);
    i++;
  }
  flushPara();
  return out;
}

// ------------------------------------------------------------------ document
function buildDoc(children, series) {
  return new Document({
    creator: "Yobie Benjamin",
    title: series,
    styles: {
      default: { document: { run: { font: FONT_BODY, size: 22, color: INK }, paragraph: { spacing: { line: 276, lineRule: LineRuleType.AUTO, after: 160 } } } },
      paragraphStyles: [
        { id: "Title", name: "Title", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: FONT_HEAD, size: 56, bold: true, color: HEAD }, paragraph: { spacing: { before: 0, after: 120, line: 240, lineRule: LineRuleType.AUTO } } },
        { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: FONT_HEAD, size: 34, bold: true, color: HEAD }, paragraph: { spacing: { before: 400, after: 140 }, outlineLevel: 0 } },
        { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: FONT_HEAD, size: 27, bold: true, color: HEAD }, paragraph: { spacing: { before: 300, after: 110 }, outlineLevel: 1 } },
        { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: FONT_HEAD, size: 23, bold: true, italics: true, color: HEAD }, paragraph: { spacing: { before: 220, after: 90 }, outlineLevel: 2 } },
      ],
      characterStyles: [
        { id: "Hyperlink", name: "Hyperlink", basedOn: "DefaultParagraphFont", run: { color: LINK, underline: {} } },
      ],
    },
    numbering: {
      config: [
        { reference: "bullets", levels: [
          { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
          { level: 1, format: LevelFormat.BULLET, text: "-", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1440, hanging: 360 } } } },
        ] },
        { reference: "numbers", levels: [
          { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
        ] },
      ],
    },
    sections: [{
      properties: { page: { size: { width: PAGE_W, height: PAGE_H }, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } } },
      headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: series, size: 16, color: QUIET, font: FONT_HEAD })] })] }) },
      footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
        new TextRun({ children: ["Page ", PageNumber.CURRENT, " of ", PageNumber.TOTAL_PAGES], size: 16, color: QUIET, font: FONT_HEAD }),
      ] })] }) },
      children,
    }],
  });
}

(async () => {
  for (const post of POSTS) {
    const src = path.join(ROOT, post.src);
    const md = fs.readFileSync(src, "utf8");
    const state = { fig: 0, list: 0 };
    const children = parse(md, path.dirname(src), state);
    const doc = buildDoc(children, post.series);
    const buf = await Packer.toBuffer(doc);
    const outPath = path.join(OUT, post.out);
    fs.writeFileSync(outPath, buf);
    console.log(`wrote ${outPath} (${(buf.length / 1024).toFixed(0)} KB, ${state.fig} figures)`);
  }
})().catch((e) => { console.error(e); process.exit(1); });
