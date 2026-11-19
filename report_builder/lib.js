// Shared helpers that reproduce the Phase 1 document styling.
const d = require("docx");
const {
  Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  AlignmentType, HeadingLevel, VerticalAlign,
} = d;

const NAVY = "102833";
const HEAD_FILL = "DCE6EA";
const ALT_FILL = "F0F3F5";
const BORDER = { style: BorderStyle.SINGLE, size: 4, color: "9AAAB2" };
const BORDERS = { top: BORDER, bottom: BORDER, left: BORDER, right: BORDER };

// Inline markup: **bold**, _italic_ (underscore pairs delimited by non-word chars)
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|(?<![\w])_[^_]+_(?![\w]))/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const tok = m[0];
    if (tok.startsWith("**")) out.push(new TextRun({ text: tok.slice(2, -2), ...base, bold: true }));
    else out.push(new TextRun({ text: tok.slice(1, -1), ...base, italics: true }));
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
  return out;
}

const P = (text, opts = {}) => new Paragraph({
  children: runs(text, opts.run || {}),
  alignment: opts.align || AlignmentType.JUSTIFIED,
  spacing: { after: opts.after ?? 120, before: opts.before ?? 0, line: 264 },
  keepNext: opts.keepNext,
});
const H1 = (t, pageBreakBefore = false) => new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore, children: [new TextRun(t)] });
const H2 = (t, pageBreakBefore = false) => new Paragraph({ heading: HeadingLevel.HEADING_2, pageBreakBefore, children: [new TextRun(t)] });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(t)] });
const B = (t, level = 0) => new Paragraph({
  numbering: { reference: "bullets", level }, children: runs(t),
  spacing: { after: 40, line: 264 }, alignment: AlignmentType.JUSTIFIED,
});
const N = (t, ref = "numbers") => new Paragraph({
  numbering: { reference: ref, level: 0 }, children: runs(t),
  spacing: { after: 40, line: 264 }, alignment: AlignmentType.JUSTIFIED,
});
const Caption = (t) => new Paragraph({
  children: runs(t, { size: 18, italics: true, color: "44545C" }),
  alignment: AlignmentType.LEFT, spacing: { before: 60, after: 160 },
});

// cellText may be a string (lines split by "\n" become separate paragraphs) or array of strings
function cell(content, width, { fill, bold, size = 16, align = AlignmentType.LEFT } = {}) {
  const lines = Array.isArray(content) ? content : String(content).split("\n");
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    borders: BORDERS,
    shading: fill ? { fill, type: ShadingType.CLEAR, color: "auto" } : undefined,
    margins: { top: 50, bottom: 50, left: 80, right: 80 },
    verticalAlign: VerticalAlign.TOP,
    children: lines.map((ln) => new Paragraph({
      children: runs(ln, { size, bold }), alignment: align, spacing: { after: 30, line: 240 },
    })),
  });
}

// header: array of strings; rows: array of arrays; widths: DXA per column
function table(header, rows, widths, { size = 16, headSize, firstColFill = false, zebra = true } = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  const head = new TableRow({
    tableHeader: true,
    cantSplit: true,
    children: header.map((h, i) => cell(h, widths[i], { fill: HEAD_FILL, bold: true, size: headSize || size })),
  });
  const body = rows.map((r, ri) => new TableRow({
    cantSplit: true,
    children: r.map((c, i) => cell(c, widths[i], {
      size,
      fill: (firstColFill && i === 0) ? HEAD_FILL : (zebra && ri % 2 === 1 ? ALT_FILL : undefined),
      bold: firstColFill && i === 0,
    })),
  }));
  return new Table({ width: { size: total, type: WidthType.DXA }, columnWidths: widths, rows: [head, ...body] });
}

// two-column key/value info table (title block), same look as Phase 1
function infoTable(pairs, widths) {
  return new Table({
    width: { size: widths[0] + widths[1], type: WidthType.DXA },
    columnWidths: widths,
    rows: pairs.map(([k, v]) => new TableRow({
      children: [cell(k, widths[0], { fill: HEAD_FILL, bold: true, size: 20 }), cell(v, widths[1], { size: 20 })],
    })),
  });
}

const spacer = (after = 120) => new Paragraph({ children: [], spacing: { after } });

module.exports = { d, runs, P, H1, H2, H3, B, N, Caption, cell, table, infoTable, spacer, NAVY, HEAD_FILL, ALT_FILL };
