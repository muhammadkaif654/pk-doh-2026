// Builds the Phase 3 deliverable: i240071_i243013_Phase3.docx
// usage: node build.js <out.docx>
const fs = require("fs");
const path = require("path");
const { d, P, H1, H2, H3, B, N, Caption, table, infoTable, spacer, NAVY } = require("./lib");
const { Document, Packer, Paragraph, TextRun, ImageRun, AlignmentType, LevelFormat, Footer, PageNumber } = d;

const OUT = process.argv[2];
const FIG = path.join(__dirname, "..", "figures");
const C = require("./content");

const PORTRAIT_W = 11906 - 2 * 1134; // 9638 dxa
const pageP = { size: { width: 11906, height: 16838 }, margin: { top: 907, right: 1134, bottom: 907, left: 1134 } };

const footer = new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
  new TextRun({ text: "CN Research Project | Phase 3 | Page ", size: 16, color: "6B7B83" }),
  new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "6B7B83" })] })] });

function pngSize(buf) { return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) }; }
function Fig(file, caption, widthPt = 480) {
  const p = path.join(FIG, file);
  if (!fs.existsSync(p)) return [P(`[Figure ${file} not available]`)];
  const buf = fs.readFileSync(p);
  const s = pngSize(buf);
  const h = Math.round(widthPt * s.h / s.w);
  return [new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 80, after: 0 },
    children: [new ImageRun({ type: "png", data: buf, transformation: { width: widthPt, height: h },
      altText: { title: file, description: caption, name: file } })] }), Caption(caption)];
}

// Render a block list: strings (paragraph, "- " bullet), {h2}, {h3}, {table}, {fig}
function render(blocks) {
  const out = [];
  for (const b of blocks) {
    if (typeof b === "string") out.push(b.startsWith("- ") ? B(b.slice(2)) : P(b));
    else if (b.h1) out.push(H1(b.h1, !!b.pageBreak));
    else if (b.h2) out.push(H2(b.h2, !!b.pageBreak));
    else if (b.h3) out.push(H3(b.h3));
    else if (b.table) {
      out.push(table(b.table.header, b.table.rows, b.table.widths, { size: b.table.size || 15, firstColFill: !!b.table.firstCol }));
      if (b.table.caption) out.push(Caption(b.table.caption)); else out.push(spacer(60));
    } else if (b.fig) out.push(...Fig(b.fig, b.caption, b.width || 480));
    else if (b.ref) out.push(new Paragraph({ children: require("./lib").runs(b.ref, { size: 20 }),
      indent: { left: 567, hanging: 567 }, spacing: { after: 80, line: 252 }, alignment: AlignmentType.LEFT }));
  }
  return out;
}

const head = [];
head.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 },
  children: [new TextRun({ text: "COMPUTER NETWORKS - RESEARCH PROJECT", bold: true, size: 24 })] }));
head.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
  children: [new TextRun({ text: "Phase 3: Research Implementation and Experimental Evaluation", bold: true, size: 26, color: NAVY })] }));
head.push(infoTable(C.titleBlock, [2600, PORTRAIT_W - 2600]));
head.push(spacer(160));

const doc = new Document({
  creator: "Muhammad Kaif, Samran Ahmad",
  title: "Phase 3 - Research Implementation and Experimental Evaluation",
  styles: {
    default: { document: { run: { font: "Times New Roman", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, font: "Calibri Light", color: NAVY },
        paragraph: { spacing: { before: 240, after: 100 }, outlineLevel: 0, keepNext: true, keepLines: true } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Calibri Light", color: NAVY },
        paragraph: { spacing: { before: 180, after: 60 }, outlineLevel: 1, keepNext: true, keepLines: true } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 21, bold: true, font: "Calibri Light", color: NAVY },
        paragraph: { spacing: { before: 100, after: 30 }, outlineLevel: 2, keepNext: true, keepLines: true } },
    ],
  },
  numbering: { config: [
    { reference: "bullets", levels: [
      { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 400, hanging: 260 } } } },
      { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 800, hanging: 260 } } } } ] },
    { reference: "numbers", levels: [
      { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 400, hanging: 300 } } } } ] },
  ] },
  sections: [{ properties: { page: pageP }, footers: { default: footer }, children: [...head, ...render(C.blocks)] }],
});

Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log("wrote", OUT); });
