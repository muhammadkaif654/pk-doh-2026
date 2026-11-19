// Builds the Phase 3 report as LaTeX from the same content as the docx (content.js + data.json).
// usage: node latex.js <out_dir>     -> <out_dir>/main.tex and <out_dir>/figures/*.png
const fs = require("fs");
const path = require("path");
const C = require("./content");

const OUT = path.resolve(process.argv[2] || path.join(__dirname, "..", "latex"));
const FIG_SRC = path.join(__dirname, "..", "figures");
fs.mkdirSync(path.join(OUT, "figures"), { recursive: true });

// ---------------------------------------------------------------- text escaping
const URL_RE = /(https?:\/\/[^\s)]+)/g;

function escPlain(t) {
  return t
    .replace(/\\/g, "\u0000BS\u0000")
    .replace(/([&%$#_{}])/g, "\\$1")
    .replace(/~/g, "\\textasciitilde{}")
    .replace(/\^/g, "\\textasciicircum{}")
    .replace(/\u0000BS\u0000/g, "\\textbackslash{}")
    .replace(/\|ΔF1\|/g, "$|\\Delta F_1|$")
    .replace(/Δ/g, "$\\Delta$")
    .replace(/±/g, "$\\pm$")
    .replace(/×/g, "$\\times$")
    .replace(/ <= /g, " $\\leq$ ")
    .replace(/ >= /g, " $\\geq$ ")
    .replace(/<=/g, "$\\leq$")
    .replace(/>=/g, "$\\geq$")
    .replace(/ -> /g, " $\\rightarrow$ ")
    .replace(/->/g, "$\\rightarrow$")
    .replace(/=>/g, "$\\Rightarrow$")
    .replace(/(^|[\s(\[])-(\d)/g, "$1$$-$$$2")
    .replace(/</g, "\\textless{}")
    .replace(/>/g, "\\textgreater{}")
    .replace(/"([^"]*)"/g, "``$1''")
    .replace(/(^|[\s(\[])'/g, "$1`")
    .replace(/\$\$/g, "");
}

// inline markup: **bold**, _italic_, URLs
function tex(t) {
  t = String(t);
  const parts = t.split(URL_RE);
  return parts.map((p, i) => {
    if (i % 2 === 1) return `\\url{${p}}`;
    return escPlain(p)
      .replace(/\*\*([^*]+)\*\*/g, "\\textbf{$1}")
      .replace(/(^|[^\w\\])\\_([^_]+?)\\_(?![\w])/g, "$1\\emph{$2}");
  }).join("");
}

// headings carry manual numbers ("1. Implementation ...") that the text refers to
function heading(cmd, text) {
  return `\\${cmd}*{${tex(text)}}\n\\addcontentsline{toc}{${cmd}}{${tex(text)}}\n`;
}

// ---------------------------------------------------------------- tables
function sizeCmd(size) { return (size || 15) <= 14 ? "\\scriptsize" : "\\footnotesize"; }

function tableTex(t) {
  const n = t.header.length;
  const widths = t.widths && t.widths.length === n ? t.widths : Array(n).fill(1);
  const total = widths.reduce((a, b) => a + b, 0);
  const cols = widths.map((w) =>
    `>{\\raggedright\\arraybackslash}p{\\dimexpr ${(w / total).toFixed(4)}\\linewidth - 2\\tabcolsep\\relax}`).join("");
  const head = t.header.map((h) => `\\textbf{${tex(h)}}`).join(" & ");
  const body = t.rows.map((r) => r.map((c, j) => (j === 0 && t.firstCol ? `\\textbf{${tex(c)}}` : tex(c))).join(" & ") + " \\\\").join("\n\\hline\n");
  return [
    "{" + sizeCmd(t.size) + "\\setlength{\\tabcolsep}{3pt}\\renewcommand{\\arraystretch}{1.18}",
    `\\begin{longtable}{${cols}}`,
    "\\hline\\rowcolor{headfill}", head + " \\\\ \\hline", "\\endfirsthead",
    "\\hline\\rowcolor{headfill}", head + " \\\\ \\hline", "\\endhead",
    "\\hline\\endfoot",
    body,
    "\\end{longtable}}",
    t.caption ? `\\vspace{-0.6em}\\captionline{${tex(t.caption)}}` : "",
    "",
  ].join("\n");
}

// ---------------------------------------------------------------- figures
function figTex(file, caption) {
  const src = path.join(FIG_SRC, file);
  if (!fs.existsSync(src)) return `\\emph{[Figure ${tex(file)} not available]}\n`;
  fs.copyFileSync(src, path.join(OUT, "figures", file));
  return [
    "\\begin{figure}[!htbp]", "\\centering",
    `\\includegraphics[width=\\linewidth,height=0.42\\textheight,keepaspectratio]{figures/${file}}`,
    `\\captionline{${tex(caption)}}`,
    "\\end{figure}", "",
  ].join("\n");
}

// ---------------------------------------------------------------- body
function render(blocks) {
  const out = [];
  let inList = false, inRefs = false;
  const closeList = () => { if (inList) { out.push("\\end{itemize}\n"); inList = false; } };
  for (const b of blocks) {
    const isBullet = typeof b === "string" && b.startsWith("- ");
    if (!isBullet) closeList();
    if (!b.ref && inRefs) { out.push("\\end{hangrefs}\n"); inRefs = false; }
    if (isBullet) {
      if (!inList) { out.push("\\begin{itemize}"); inList = true; }
      out.push(`  \\item ${tex(b.slice(2))}`);
    } else if (typeof b === "string") out.push(tex(b) + "\n");
    else if (b.h1) out.push(heading("section", b.h1));
    else if (b.h2) out.push(heading("subsection", b.h2));
    else if (b.h3) out.push(heading("subsubsection", b.h3));
    else if (b.table) out.push(tableTex(b.table));
    else if (b.fig) out.push(figTex(b.fig, b.caption));
    else if (b.ref) {
      if (!inRefs) { out.push("\\begin{hangrefs}"); inRefs = true; }
      out.push(`\\item ${tex(b.ref)}`);
    }
  }
  closeList();
  if (inRefs) out.push("\\end{hangrefs}\n");
  return out.join("\n");
}

const titleRows = C.titleBlock.map(([k, v]) => `\\rowcolor{headfill}\\textbf{${tex(k)}} & ${tex(v)} \\\\ \\hline`).join("\n");

const doc = String.raw`% Phase 3 report, generated by report/latex.js from content.js and data.json.
% Compiles with pdfLaTeX, XeLaTeX or LuaLaTeX (e.g. upload this folder to Overleaf).
\documentclass[11pt,a4paper]{article}
\usepackage[T1]{fontenc}
\usepackage{newtxtext,newtxmath}
\usepackage[a4paper,top=1.6cm,bottom=2.0cm,left=2cm,right=2cm,footskip=0.9cm]{geometry}
\usepackage[table]{xcolor}
\usepackage{graphicx,longtable,array,enumitem,caption,microtype}
\usepackage{titlesec,fancyhdr}
\usepackage[hidelinks]{hyperref}
\usepackage{xurl}

\definecolor{navy}{HTML}{102833}
\definecolor{headfill}{HTML}{DCE6EA}
\definecolor{footgrey}{HTML}{6B7B83}

\titleformat{\section}{\sffamily\Large\bfseries\color{navy}}{}{0pt}{}
\titleformat{\subsection}{\sffamily\large\bfseries\color{navy}}{}{0pt}{}
\titleformat{\subsubsection}{\sffamily\normalsize\bfseries\color{navy}}{}{0pt}{}
\titlespacing*{\section}{0pt}{1.1em}{0.5em}
\titlespacing*{\subsection}{0pt}{0.9em}{0.35em}

\pagestyle{fancy}\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
\cfoot{\color{footgrey}\footnotesize CN Research Project | Phase 3 | Page \thepage}
\fancypagestyle{plain}{\fancyhf{}\cfoot{\color{footgrey}\footnotesize CN Research Project | Phase 3 | Page \thepage}}

\setlength{\parindent}{0pt}
\setlength{\parskip}{0.55em}
\setlist[itemize]{leftmargin=1.4em,itemsep=0.15em,topsep=0.2em}
\setlength{\LTpre}{0.4em}\setlength{\LTpost}{0.6em}
\captionsetup{font=small}
% captions carry their own "Table N." / "Figure N." numbers, as cited in the text
\newcommand{\captionline}[1]{\par\begingroup\small\itshape\color{navy!80!black}#1\par\endgroup\vspace{0.4em}}
\newenvironment{hangrefs}{\begin{list}{}{\leftmargin=2.2em\itemindent=-2.2em\itemsep=0.25em\small}}{\end{list}}
\renewcommand{\arraystretch}{1.15}

\begin{document}

\begin{center}
{\large\bfseries COMPUTER NETWORKS -- RESEARCH PROJECT}\\[0.3em]
{\Large\bfseries\color{navy} Phase 3: Research Implementation and Experimental Evaluation}
\end{center}
\vspace{0.4em}
{\small\setlength{\tabcolsep}{6pt}\renewcommand{\arraystretch}{1.35}
\begin{longtable}{|>{\raggedright\arraybackslash}p{0.27\linewidth}|>{\raggedright\arraybackslash}p{\dimexpr 0.73\linewidth - 4\tabcolsep\relax}|}
\hline
${titleRows}
\end{longtable}}

${render(C.blocks)}
\end{document}
`;

fs.writeFileSync(path.join(OUT, "main.tex"), doc);
console.log("wrote", path.join(OUT, "main.tex"), "and", fs.readdirSync(path.join(OUT, "figures")).length, "figures");
