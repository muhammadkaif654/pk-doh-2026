// Phase 3 document content. All numbers are read from data.json (built by code/report_data.py).
const S = require("./static");
const D = require("./data.json");

const f = (x, d = 3) => (x === undefined || x === null || Number.isNaN(x)) ? "n/a" : Number(x).toFixed(d);
const pct = (x, d = 1) => (x === undefined || x === null) ? "n/a" : (100 * x).toFixed(d) + "%";
const g = (obj, path) => path.split(".").reduce((o, k) => (o && o[k] !== undefined ? o[k] : undefined), obj);
const CF = "netA_wifi_cloudflare", Q9 = "netA_wifi_quad9";
const e2 = D.e2 || {}, e3 = D.e3 || {}, e5 = D.e5 || {}, ab = D.ablations || {}, re = D.realism || {}, e1 = D.e1 || {};
const sb = D.siby_baselines || {}, sc = D.siby_cross || {}, e4 = D.e4 || {};
const m2 = (c, m) => g(e2, `${c}.${m}`) || {};
const F1 = (c, m) => m2(c, m).f1;
const T = (k, m = "ngram_rf") => g(e3, `${m}.${k}`) || {};
const n_ps = (c) => g(D, `e2_meta.${c}.n_per_site`);
const n_sites = (c) => g(D, `e2_meta.${c}.n_sites`);
const ci = (r) => r && r.f1_ci ? `[${f(r.f1_ci[0])}, ${f(r.f1_ci[1])}]` : "";

// ------------------------------------------------------------------ helpers for tables
const modelRows = [
  ["B1", "n-grams of record and burst sizes (uni+bi) + random forest, 100 trees", "Siby et al. 2020", "Reproduction target; primary attack"],
  ["B2", "k-fingerprinting: 60 hand-crafted size, count, ordering, burst and timing statistics + RF", "Hayes & Danezis 2016", "Compared by Siby (F1 0.74 on DoH)"],
  ["B3", "CUMUL: 100-point cumulative-size curve + 4 totals, RBF-SVM (C = 1000)", "Panchenko et al. 2016", "Compared by Siby (F1 0.75)"],
  ["B4", "Deep Fingerprinting: 3 ELU conv blocks over the +1/-1 direction sequence (200 records)", "Sirinam et al. 2018", "Compared by Siby (F1 0.51)"],
  ["B5", "Burst statistics (25 ms gaps, Gini, gravity centre, counts) + RF, 200 trees, balanced", "Moure-Garrido et al. 2026 (PH1-2)", "Most recent encrypted-DNS attack"],
  ["B6", "Chance (1/K)", "-", "Floor for collapse under transfer"],
  ["M1", "Fused RF over F1 + F2 + F5 (sizes, bursts, timing)", "Ours (timing after P8)", "RQ3: do burst and timing features survive padding?"],
  ["M2", "1D-CNN with squeeze-excitation over (size, log-IAT, direction)", "Ours (Phase 2 Step 5)", "Sequence model with timing"],
];

const featRows = [
  ["F1", "Counts of uni- and bi-grams of signed record sizes and of burst sizes", "Siby et al.", "B1, M1"],
  ["F2", "24 burst statistics with a 25 ms inter-burst gap (counts, bytes, Gini, gravity, duration)", "PH1-2", "B5, M1"],
  ["F3", "First 200 records as (size/500, log1p IAT ms, direction) channels", "P1, P3", "M2"],
  ["F4", "Record sizes replaced by their 128-byte or 468-byte block index", "RFC 8467", "E5, transfer"],
  ["F5", "20 slots x 250 ms x 2 directions x 8 log-spaced IAT bins = 320 counts", "P8 (WFCAT)", "M1, E5"],
];

function datasetRows() {
  const r = [];
  const sib = (k, name, where, when, res, pad, note) => {
    const x = re["siby_" + k];
    if (x) r.push([name, where, when, res, pad, `${x.n_traces.toLocaleString()} (${(x.n_pages || 1500).toLocaleString()} pages, median ${x.per_page_median || "-"} per page${note ? "; " + note : ""})`, f(x.median_len, 0), f(x.per_site_cv_median, 2)]);
  };
  sib("LOC1", "Siby LOC1", "Lausanne", "Aug-Nov 2018", "Cloudflare (cloudflared)", "none");
  sib("LOC2", "Siby LOC2", "Leuven", "2018", "Cloudflare (cloudflared)", "none");
  sib("LOC3", "Siby LOC3", "Singapore (AWS)", "Nov 2018", "Cloudflare", "none");
  sib("EDNS0-128", "Siby EDNS0-128", "Lausanne", "Apr 2019", "Cloudflare", "128-B blocks", "paper's Table I: 700 x 60");
  sib("EDNS0-468", "Siby EDNS0-468", "Lausanne", "May 2019", "Cloudflare via mitmproxy", "468-B blocks", `only ${g(re, "siby_EDNS0-468.pages_ge60") || 700} pages have 60 or more; paper's Table I: 700 x 60`);
  for (const [c, res, pad] of [[CF, "Cloudflare (Chrome native DoH)", "468-B blocks (client pads)"], [Q9, "Quad9 (Chrome native DoH)", "none"]]) {
    const x = re[c];
    if (x) r.push([`PK-DoH-2026 / ${c.includes("cloud") ? "Cloudflare" : "Quad9"}`, "Pakistan, residential Wi-Fi", "Nov 2026",
      res, pad, `${x.n_traces.toLocaleString()} (${x.n_sites} sites, ${x.rounds} rounds)`, f(x.median_len, 0), f(x.per_site_cv_median, 2)]);
  }
  return r;
}

function e1Text() {
  const L = e1.LOC1;
  if (!L) return ["The reproduction results are reported in Table 10."];
  const out = [];
  out.push(`On the main target, the full LOC1 closed world of 1,500 pages, our port of the attack reaches F1 = ${f(L.f1)} ± ${f(L.f1_sd)} (95% CI ${ci(L)}), against the published 0.898 ± 0.003. The difference is ${f(L.delta_f1, 3)}, so by the tolerance fixed in Phase 2 before any code was run the result is **${L.verdict}**${L.tost_p != null ? ` (TOST equivalence test with margin 0.03: p ${L.tost_p < 0.001 ? "< 0.001" : "= " + f(L.tost_p)})` : ""}. Top-1 accuracy is ${f(L.acc)} and top-5 accuracy ${f(L.top5)}.`);
  const ex = e1.LOC1_exact, uni = e1.LOC1_uni;
  if (ex) out.push(`Keeping every n-gram (268k features, the paper's exact configuration) gives F1 = ${f(ex.f1)} on the evaluated fold, ${Math.abs(ex.f1 - L.f1) < 0.02 ? "practically identical to" : (ex.f1 < L.f1 ? "slightly below" : "slightly above")} the pruned run, so the vocabulary filter does not inflate the result.`);
  if (uni) out.push(`The configuration in the released code (uni-grams only) reaches F1 = ${f(uni.f1)}, ${uni.verdict === "reproduced" ? "also within tolerance" : "outside the tolerance"}. The released code and the paper therefore disagree on the feature set, but ${Math.abs(uni.f1 - L.f1) < 0.03 ? "the disagreement is immaterial for the headline number" : "the paper's uni+bi-gram description is the one that reproduces"}.`);
  const loc = ["LOC2", "LOC3"].filter((k) => e1[k]);
  if (loc.length) out.push("The location rows of Siby's Table VI also reproduce: " + loc.map((k) => `${k} gives ${f(e1[k].f1)} against ${f(e1[k].paper_f1)} (${e1[k].verdict}${e1[k].tost_p != null && e1[k].tost_p > 0.05 ? "; the difference is inside the margin, but with three folds the equivalence test is not significant, p = " + f(e1[k].tost_p) : ""})`).join(", and ") + ". To fit the compute budget these two rows use 20 samples per page.");
  out.push(`The padding rows needed one correction. The paper's Table I gives every countermeasure dataset as 700 pages × 60 samples, but the released files differ: EDNS0-128 holds all 1,500 page labels with 84-89 samples each, and EDNS0-468 holds 1,500 labels of which only ${g(re, "siby_EDNS0-468.pages_ge60") || 700} have 60 or more samples (the other 800 have 10-19). Our first runs used all 1,500 labels with the samples available, which enlarges the closed world and shrinks the training set at the same time; ablation A4 shows that a larger closed world alone lowers F1. We therefore evaluate the Table VII rows on the ${g(re, "siby_EDNS0-468.pages_ge60") || 700} pages that have 60 samples in EDNS0-468, and use the same pages for EDNS0-128 and for perfect padding (applied to LOC1 traces). The first runs remain in Table 10 as sensitivity rows.`);
  const pad = [["EDNS0-128-700", "EDNS0-128"], ["EDNS0-468-700", "EDNS0-468"]].filter(([k]) => e1[k]);
  if (pad.length) out.push("On the 700-page configuration, " + pad.map(([k, n]) => `${n} gives ${f(e1[k].f1)} against ${f(e1[k].paper_f1)} (ΔF1 ${e1[k].delta_f1 > 0 ? "+" : ""}${f(e1[k].delta_f1)}, ${e1[k].verdict})`).join(", and ") + "." + pad.map(([k, n]) => e1[n] ? ` On all 1,500 labels with ${n === "EDNS0-128" ? 20 : 10} samples per page, ${n} gave ${f(e1[n].f1)}.` : "").join("") + (e1["EDNS0-468-700"] && e1["EDNS0-468-700"].delta_f1 > 0.03 ? " Our EDNS0-468 value is above the published one. A likely reason is that the 700 pages with 60 or more samples are not a random subset: they may be the pages the authors collected most completely, but the released files do not say which 700 pages the paper used, so we cannot test this." : ""));
  const P = e1["PERFECT-700"], Pn = e1["PERFECT-nodir-700"];
  if (P) out.push(`Perfect padding turns on one detail. Keeping each record's direction and setting its size to 825 bytes leaves F1 ${f(P.f1)} against the published ${f(P.paper_f1)}.${Pn ? ` The paper says it set "the length of all packets" to 825; read literally, that also removes direction, and this variant leaves ${f(Pn.f1)}.` : ""} ${Pn && Math.abs(Pn.f1 - P.paper_f1) < Math.abs(P.f1 - P.paper_f1) ? "The literal reading is closer to the published value, which suggests the paper dropped direction as well." : "Neither reading reaches the published value, so the gap remains unexplained."} In every variant the attack stays far above chance (1/700 = 0.0014), as the paper concludes.`);
  return out;
}

function padSummary() {
  const rows = [["EDNS0-128-700", "EDNS0-128"], ["EDNS0-468-700", "EDNS0-468"], ["PERFECT-nodir-700", "perfect padding (paper's method, all records 825 bytes and direction dropped)"]].filter(([k]) => e1[k]);
  if (!rows.length) return "The padding results are discussed in Section 4.1.";
  return "For the padding experiments of Table VII, evaluated on the paper's 700-page configuration: " + rows.map(([k, n]) => `${n} ${e1[k].verdict} (${f(e1[k].f1)} against ${f(e1[k].paper_f1)})`).join(", ") + ".";
}

const c = (k) => (k.includes("cloud") ? "Cloudflare" : "Quad9");
const sid = (x) => String(x).replace(/^P(\d\d)$/, "PK$1");  // site ids P00-P49 in the data files are shown as PK00-PK49

// ------------------------------------------------------------------ content blocks
const blocks = [];
const add = (...b) => blocks.push(...b);

add(...S.intro);
add({ table: { header: ["Phase 3 brief component", "Where it is delivered", "Rubric criterion"], rows: S.deliverableMap, widths: [2900, 4300, 2438], firstCol: true, caption: "Table 1. Map from the Phase 3 brief to this document." } });

// ============================ 1. Implementation
add({ h1: "1. Implementation of the Proposed Methodology" });
add(S.implIntro);
add({ fig: "fig1_pipeline.png", caption: "Figure 1. The pipeline as implemented. Tracks A-C feed one preprocessing, feature and evaluation pipeline. Dashed borders mark components that changed from the Phase 2 design (Section 1.5)." });
add({ h2: "1.1 Track A: reproduction of the 2020 attack (RQ1)" }, ...S.trackA);
add({ h2: "1.2 Track B: the PK-DoH-2026 capture pipeline (RQ2)" }, ...S.trackB);
add({ h2: "1.3 Track C: the resolver padding audit (RQ3)" }, S.trackC);
add({ h2: "1.4 Proposed models and baselines" }, S.proposedIntro, ...S.proposed.map((x) => "- " + x));
add({ table: { header: ["ID", "Method", "Source", "Role"], rows: modelRows, widths: [500, 4600, 2100, 2438], firstCol: true, caption: "Table 2. Baselines (B1-B6) and proposed models (M1, M2; M for 'model', to keep them apart from the paper labels P1-P10). B2-B4 are the three attacks Siby et al. compared against, so the comparison stays like for like." } });
add({ h2: "1.5 Changes to the Phase 2 methodology" }, S.changesIntro);
add({ table: { header: ["Item", "Phase 2 plan", "Reason for change", "What was implemented"], rows: S.changes, widths: [2000, 2000, 2900, 2738], firstCol: true, size: 14, caption: "Table 3. Every deviation from the Phase 2 design, with its reason." } });

// ============================ 2. Dataset and preprocessing
add({ h1: "2. Dataset, Preprocessing and Experimental Setup" });
add({ h2: "2.1 Datasets" });
add(`We use two kinds of data. The published 2018-19 datasets of Siby et al. give the reproduction target and the 'old' side of the transfer experiments; our own PK-DoH-2026 capture gives the 'new' side. The site list has 100 labels: 50 global sites taken from Siby's list (mapped to their class indices so that the two eras share labels) that are still online and reachable from Pakistan, and 50 Pakistani sites across news (16), e-commerce (11), banking and payments (6), education (6), government (8) and telecom (3), none of which appears in any prior encrypted-DNS study. Ten global candidates were rejected before collection because they did not load from our network (for example x.com, telegram.org, live.com), and nine Pakistani candidates for the same reason.`);
add({ table: { header: ["Dataset", "Vantage point", "Collected", "Resolver / client", "Padding", "Traces", "Median records / trace", "Median per-site CV"], rows: datasetRows(), widths: [1500, 1300, 950, 1550, 1200, 1300, 900, 938], size: 14, caption: "Table 4. Datasets used. Page and sample counts are those of the released files, which do not always match the paper's Table I (Section 4.1). CV is the coefficient of variation of trace length within a site (a realism statistic after P10): higher means less regular traffic." } });
const rq = re[Q9] || {}, rc = re[CF] || {};
add(`Two realism statistics stand out. Traces in 2026 are much longer than in 2018 (median ${f(rc.median_len, 0)} and ${f(rq.median_len, 0)} TLS records for Cloudflare and Quad9, against ${f(g(re, "siby_LOC1.median_len"), 0)} in LOC1), because a 2026 page load resolves more names and Chrome keeps several DoH connections. ${f(100 * (rc.share_timeout || 0), 1)}% of Cloudflare and ${f(100 * (rq.share_timeout || 0), 1)}% of Quad9 visits hit the 30 s load timeout; their partial traces are kept, as Siby did. ${(rc.challenge_sites || []).length} sites returned a bot-challenge page to headless Chrome in more than half of their visits (${(rc.challenge_sites || []).map(sid).join(", ")}; G = global, PK = Pakistani); they stay in the full dataset and are removed in the curated variant.`);

add({ h2: "2.2 Padding audit and resolver selection" });
add("Table 5 is the result of Track C. It decided which two resolvers Track B uses, and it is itself a finding for RQ3.");
add({ table: { header: ["Resolver", "DoH, client no pad", "DoH, client pads", "DoT, client no pad", "DoT, client pads"], rows: D.audit_rows || [], widths: [1900, 1934, 1934, 1934, 1936], firstCol: true, size: 14, caption: "Table 5. Padding of DNS responses as deployed (November 2026), from decrypted replies to our own probes. '468-B blocks': every reply is a multiple of 468 bytes (RFC 8467). 'non-standard': a Padding option is present but replies do not fall on a block boundary." } });
add({ fig: "fig3_padding_audit.png", caption: "Figure 2. Decrypted DoH response sizes per resolver, without (left) and with (right) a padded client query. Padded replies sit exactly on 468-byte multiples (dashed lines)." });
add("Three behaviours are visible. Cloudflare and Google follow RFC 8467 exactly, but only when the client pads its query; OpenDNS (and Cloudflare over DoT) pads every reply regardless. AdGuard and ControlD add a Padding option of non-standard length, so replies do not land on a block boundary. Quad9, NextDNS, DNS.SB, AliDNS and CleanBrowsing (DoH) never pad. Two observations matter for the rest of the study. First, Cloudflare has changed since 2019: Siby et al. found it padding replies to 128 bytes, while it now pads to 468. Second, padding depends on the client: Chrome pads its DoH queries (all Chrome queries in our captures are 154-byte records), so a Chrome user of Cloudflare gets padded replies while the same user of Quad9 gets none. We therefore chose **Cloudflare (padded)** and **Quad9 (unpadded)** for Track B: the same client, network and sites, differing only in the resolver's padding. Mullvad was unreachable over both transports and Quad9 over DoT from our network; consistent with the proposal's ethics statement we did not investigate why. To our knowledge no earlier measurement reports which public resolvers pad: the large resolver survey of P5 measures protocol support, latency and page-load time, not padding.");
add({ fig: "fig4_wire_histograms.png", caption: "Figure 3. Passive view of the same contrast in our captures: resolver-to-client TLS record sizes. Cloudflare's responses collapse onto a few sizes (494 bytes = one 468-byte padded message plus HTTP/2 and TLS framing); Quad9's spread over hundreds of values." });

add({ h2: "2.3 Preprocessing and feature engineering" });
add("- **Record extraction.** tshark with TCP reassembly reads every TLS record on the resolver flow; its length and direction become one signed integer, its capture time one timestamp.");
add("- **TLS 1.3 alignment.** The encrypted handshake (server certificate chain, client Finished) and session tickets sent before the first request are removed per connection, so a 2026 trace starts at the first DoH exchange, as a 2018 TLS 1.2 trace did. Without this step every 2026 trace would begin with a 2 kB certificate record that carries no site information.");
add("- **Cleaning.** Crashed visits and traces with fewer than five records are discarded. Each condition is balanced to the same number of traces per site; sites with fewer valid traces than the 10th-percentile count are dropped rather than shrinking every site.");
add("- **Label alignment.** The 50 global sites are mapped to Siby's class indices, so a model trained on 2018 traces can be tested on 2026 traces with identical labels.");
add("- **Leakage control.** All splits are stratified by site; every trace and any variant derived from it (simulated padding, truncation) stays on one side of a split.");
add({ table: { header: ["Set", "Representation", "Source", "Used by"], rows: featRows, widths: [600, 5200, 1600, 2238], firstCol: true, caption: "Table 6. Feature sets. Siby's released data has no timestamps, so F2 falls back to direction runs and F3/F5 timing channels are zero on 2018-19 data." } });

add({ h2: "2.4 Experimental setup" });
add({ table: { header: ["Item", "Setting"], rows: [
  ["Hardware", "Laptop, Intel Core i7-13620H (10 cores, 16 threads), 16 GB RAM, no GPU; Windows 11"],
  ["Software", "Python 3.14.2, scikit-learn 1.8.0, PyTorch 2.11 (CPU), NumPy 2.4, pandas 3.0, SciPy 1.17; tshark/dumpcap 4.6.8 (Npcap); Chrome 157 + ChromeDriver 157; Selenium 4.52; dnspython 2.8; httpx 0.28 (HTTP/2)"],
  ["E1 protocol", "Stratified 10-fold CV with the paper's split sizes; first 3 folds evaluated (1 fold for the two check rows); seed fixed per fold. LOC1: 1,500 pages x 60; LOC2, LOC3: 1,500 x 20; padding rows: 700 x 60 (Section 4.1)"],
  ["E2 / ablations protocol", "10 (E2) or 5 (E5, ablations) repeated stratified 80/20 splits, at least one test trace per site; neural models on 5 (E2) or 3 (ablations) splits"],
  ["E3 / E4 protocol", "Train on all of X, test on all of Y over the shared labels; in-domain cells by 5 repeated splits. Recovery: half of Y held out for test, k traces per site drawn from the other half, 3 repetitions"],
  ["Metrics", "Macro-F1 (headline), top-1 and top-5 accuracy, macro precision and recall; per-site F1 distribution"],
  ["Statistics", "Mean, SD and t-based 95% CI over splits; site-clustered bootstrap CI (1,000 resamples of sites) for transfer cells; TOST equivalence test (margin 0.03) for reproduction; Wilcoxon signed-rank for paired model comparisons"],
  ["Random forest", "100 fully grown trees, sqrt(features) per split, bootstrap, probability averaging (B5: 200 trees, balanced class weights)"],
  ["Neural training", "AdamW (lr 2e-3, DF 1e-3), cosine schedule, batch 128, label smoothing 0.05, up to 40 epochs, early stopping on a 10% validation split of the training data"],
], widths: [2100, 7538], firstCol: true, caption: "Table 7. Experimental setup. All code, configurations and seeds are in the project repository." } });

// ============================ 3. Baseline evaluation
add({ h1: "3. Baseline Evaluation" });
add({ h2: "3.1 Baselines on the published 2018 data" });
add(`Table 8 runs all five baselines and both proposed models on a random 100-page subset of LOC1 (60 traces per page, 3 repeated 80/20 splits). This mirrors Siby et al.'s Table III comparison on DoH-only traffic.`);
add({ table: { header: ["Method", "Macro F1 (mean ± SD)", "Accuracy", "Top-5", "Precision", "Recall", "Splits"], rows: D.siby_baseline_rows || [], widths: [3300, 1500, 950, 950, 950, 950, 1038], firstCol: true, caption: "Table 8. Baselines on Siby LOC1 (2018, Lausanne), 100 pages. No timestamps exist in this data, so timing features are absent." } });
add(`The ranking largely matches the paper's: n-grams first (${f(g(sb, "ngram_rf.f1"))}) and Deep Fingerprinting last (${f(g(sb, "df.f1"))}). The two middle methods swap places: Siby reported CUMUL (0.75) marginally above k-FP (0.74), while we find k-FP (${f(g(sb, "kfp.f1"))}) clearly above CUMUL (${f(g(sb, "cumul.f1"))}). Siby's values for n-grams, k-FP, CUMUL and DF are 0.87, 0.74, 0.75 and 0.51 at 1,500 pages. Absolute values are higher here because 100 pages are easier than 1,500. The fused RF (${f(g(sb, "fused_rf.f1"))}) matches the n-gram forest, as it should when no timing is available. Neither neural model reaches the forests with 48 training traces per page; the CNN without the attention block (${f(g(sb, "cnn_nose.f1"))}) does better than with it (${f(g(sb, "cnn_se.f1"))}), a first indication that channel attention does not help on short DNS traces (Section 5).`);

add({ h2: "3.2 Baselines and proposed models on PK-DoH-2026" });
add(`Table 9 is the in-domain evaluation on our own data: the same 100 sites, network and client, for each resolver, with ${n_ps(CF) || "n"} traces per site, 10 repeated splits for the forests and 5 for the neural models.`);
add({ table: { header: ["Method", "Cloudflare F1", "Acc", "Top-5", "Prec", "Rec", "Quad9 F1", "Acc", "Top-5", "Prec", "Rec"], rows: D.e2_rows || [], widths: [2300, 1050, 650, 650, 650, 650, 1050, 650, 650, 650, 688], firstCol: true, size: 13, caption: "Table 9. In-domain results on PK-DoH-2026 (mean ± SD over splits). Chance is 0.01." } });
add({ fig: "fig5_baselines.png", caption: "Figure 4. In-domain macro-F1 with 95% CIs for every method on both resolvers." });
const cfN = F1(CF, "ngram_rf"), q9N = F1(Q9, "ngram_rf");
add(`The resolver changes everything. Against **Quad9**, which does not pad, the 2020 attack still works in 2026 from Pakistan: the n-gram forest identifies the site with macro-F1 ${f(q9N)} (top-5 accuracy ${f(m2(Q9, "ngram_rf").top5)}). Against **Cloudflare**, which pads Chrome's replies to 468 bytes, the same attack falls to ${f(cfN)}. The two conditions differ only in the resolver, so the drop of ${f(q9N - cfN)} F1 is the effect of padding as deployed. Methods that lean less on exact sizes degrade less: k-FP (${f(F1(CF, "kfp"))}) and the burst statistics of PH1-2 (${f(F1(CF, "burst_rf"))}) are the strongest single baselines on Cloudflare, because the number of queries, bursts and their timing survive block padding. The proposed fused forest reaches ${f(F1(CF, "fused_rf"))} on Cloudflare, ${f(F1(CF, "fused_rf") - cfN)} above the n-gram attack${D.e2_meta && D.e2_meta[CF] && D.e2_meta[CF].wilcoxon != null ? ` (Wilcoxon signed-rank over the paired splits, p = ${f(D.e2_meta[CF].wilcoxon)})` : ""}, and ${f(F1(Q9, "fused_rf"))} on Quad9, slightly below it (${f(F1(Q9, "fused_rf") - q9N)}): when sizes are intact the extra features only dilute them, and when sizes are padded the extra features carry the attack. Timing alone (F5) is weak on both (${f(F1(CF, "timing_rf"))} and ${f(F1(Q9, "timing_rf"))}), and the neural models remain far below the forests at this sample size.`);
add({ fig: "fig11_per_site_cdf.png", caption: "Figure 5. Distribution of per-site F1 (n-gram forest). Under Cloudflare's padding most sites are rarely identified, but a minority remain easy prey." });

// ============================ 4. Comparison with existing research
add({ h1: "4. Comparison with Existing Research" });
add({ h2: "4.1 Reproduction of Siby et al. (RQ1)" });
add({ table: { header: ["Experiment", "Published F1", "Our F1 (mean ± SD)", "95% CI", "ΔF1", "TOST p", "Acc / Top-5", "Folds", "Verdict"], rows: D.e1_rows || [], widths: [2150, 800, 1250, 1150, 700, 800, 1100, 550, 1138], firstCol: true, size: 13, caption: "Table 10. Reproduction table (B0 vs B1). Each row gives pages x samples per page. Verdicts use the tolerance fixed in Phase 2: reproduced if |ΔF1| <= 0.03, partly reproduced if <= 0.10, otherwise not reproduced; ΔF1 shows a fourth decimal where three would hide which side of a threshold it falls. Sensitivity rows rerun the padding experiments on all 1,500 released page labels and are not part of the verdict." } });
add({ fig: "fig2_reproduction.png", caption: "Figure 6. Published F1 (grey) and our reproduction (blue, 95% CI) for every row of Table 10 except the sensitivity rows; labels give ΔF1. Perfect padding is shown with record direction kept and dropped." });
add(...e1Text());

add({ h2: "4.2 Transfer across time, place and resolver (RQ2)" });
const t = (a, b) => T(`${a}->${b}`).f1;
add(`Figure 7 is the transfer matrix over the ${g(e3, "ngram_rf.S18-LOC1-Lausanne->PK26-Cloudflare.n_labels") || 45} global sites that both eras share (rows train, columns test). It has 49 rather than 50 sites because vimeo.com (G40) had fewer than ten valid Cloudflare traces and was dropped by the balancing step (Section 2.3), which also removed one Pakistani site (PK35) from the Cloudflare set. Within the 2018 data the attack transfers between places, as Siby reported: a model trained in Lausanne still scores ${f(t("S18-LOC1-Lausanne", "S18-LOC3-Singapore"))} in Singapore and the reverse gives ${f(t("S18-LOC3-Singapore", "S18-LOC1-Lausanne"))}${sc["LOC1->LOC3"] ? ` (at 300 pages: ${f(sc["LOC1->LOC3"].f1)} and ${f(g(sc, "LOC3->LOC1.f1"))}; paper at 1,500 pages: 0.663 and 0.680)` : ""}. Across eras it does not transfer at all: every 2018 -> 2026 and 2026 -> 2018 cell is at chance (F1 <= ${f(Math.max(t("S18-LOC1-Lausanne", "PK26-Quad9") || 0, t("S18-LOC1-Lausanne", "PK26-Cloudflare") || 0, t("PK26-Quad9", "S18-LOC1-Lausanne") || 0, 0.001))}), including the unpadded 2018 Lausanne data against our unpadded Quad9 data. Transfer also fails between our two resolvers in the same week, network and browser (Quad9 -> Cloudflare ${f(t("PK26-Quad9", "PK26-Cloudflare"))}, Cloudflare -> Quad9 ${f(t("PK26-Cloudflare", "PK26-Quad9"))}).`);
add({ fig: "fig6_transfer_matrix.png", caption: "Figure 7. Transfer matrix (n-gram forest; site-clustered bootstrap 95% CIs). PK26 = our 2026 Pakistan data; S18/S19 = Siby et al. 2018-19 data." });
add(`The cause is visible in the features rather than in the sites. A 2026 trace and a 2018 trace of the same page share almost no n-grams: the 2018 records come from cloudflared over TLS 1.2 with unpadded HTTP/2 frames, the 2026 records from Chrome over TLS 1.3 with padded queries (154-byte records instead of 2018's 100-200-byte spread). Siby already showed that a constant 7.8-byte offset between platforms destroys transfer (F1 0.0003 desktop -> Raspberry Pi); our setting changes far more than a constant. Even block-index features (F4), which are invariant to small offsets, stay at chance across eras (F1 <= 0.041 over 49 sites, chance 0.020). For an adversary this means a 2018-19 model is useless today, and the question becomes how cheaply a fresh one is built.`);
add({ h2: "4.3 Recovery: how much local data restores the attack" });
add({ fig: "fig7_recovery.png", caption: "Figure 8. Recovery curves: F1 on held-out target traces after adding k target traces per site to the source training data (solid), and with the k target traces alone (dotted)." });
const rec = (pair, model = "ngram_rf") => (g(e4, `${pair}.${model}.with_source`) || []);
const recK = (pair, k, model = "ngram_rf") => (rec(pair, model).find((x) => x.k === k) || {}).f1;
const tok = (pair, k, model = "ngram_rf") => ((g(e4, `${pair}.${model}.target_only`) || []).find((x) => x.k === k) || {}).f1;
add(`Adding a handful of local traces per site restores most of the attack, and older data adds little on top of them. From the 2018 Lausanne model, adding k = 1, 2 and 5 Cloudflare 2026 traces per site gives F1 ${f(recK("S18-LOC1->PK26-Cloudflare", 1))}, ${f(recK("S18-LOC1->PK26-Cloudflare", 2))} and ${f(recK("S18-LOC1->PK26-Cloudflare", 5))}. Between resolvers, a Quad9-trained model supplemented with k = 5 Cloudflare traces reaches ${f(recK("Quad9->Cloudflare", 5))}, and the Cloudflare -> Quad9 direction reaches ${f(recK("Cloudflare->Quad9", 5))}. The source data helps only at the smallest budget, and only between our two 2026 resolvers: at k = 1, Cloudflare -> Quad9 reaches ${f(recK("Cloudflare->Quad9", 1))} with the Cloudflare data against ${f(tok("Cloudflare->Quad9", 1))} with the single Quad9 trace alone, and Quad9 -> Cloudflare ${f(recK("Quad9->Cloudflare", 1))} against ${f(tok("Quad9->Cloudflare", 1))}. From k = 2 on, the target-only curves match or exceed the solid ones (for example ${f(tok("Cloudflare->Quad9", 2))} with two Quad9 traces alone against ${f(recK("Cloudflare->Quad9", 2))} with the Cloudflare data added). The 2018 data helps at no budget (k = 1: ${f(recK("S18-LOC1->PK26-Cloudflare", 1))} against ${f(tok("S18-LOC1->PK26-Cloudflare", 1))}). So the cost of the attack is the cost of a few fresh crawls per site, which Siby's own Table IV and PH1-1's N-shot results also suggest.`);

add({ h2: "4.4 Comparison with recent encrypted-DNS attacks" });
add("Table 11 sets our results beside the published attacks reviewed in Phases 1 and 2. Only the first two rows are measured on identical data and protocol; for the others the comparison is indicative, and the right-hand column states what prevents a strict comparison.");
add({ table: { header: ["Study", "Channel / data", "Sites", "Reported result", "Our comparable result", "Limits on fair comparison"], rows: [
  ["Siby et al. 2020 (NDSS)", "DoH/2, Cloudflare, Lausanne 2018", "1,500", "F1 0.898 (LOC1)", e1.LOC1 ? `F1 ${f(e1.LOC1.f1)} on the same data` : "Table 10", "None: same data, same features and classifier"],
  ["Siby et al. 2020, padding", "EDNS0-468 via mitmproxy, 2019", "700", "F1 0.430", e1["EDNS0-468-700"] ? `F1 ${f(e1["EDNS0-468-700"].f1)} (reproduction, same data); 2026 deployed 468 padding: ${f(cfN)} at 100 sites` : `deployed 468 padding, 2026: ${f(cfN)} at 100 sites`, "Reproduction: none. 2026 value: different client (Chrome vs cloudflared), year and site count"],
  ["DoHFuse (P1), 2026", "DoH/3, Google, California VPS", "100 / 449", "Acc 95.48% (100); sizes-only RF 67.39% (449)", `Acc ${f(m2(CF, "fused_rf").acc)} fused, ${f(m2(CF, "ngram_rf").acc)} n-grams (Cloudflare, padded)`, "HTTP/3 and Google; 100 visits per site vs ours ~10; timing-only DMAG-LSTM not reimplemented"],
  ["ODoH (P2), DSN 2025", "Oblivious DoH, 10 US states", "100", "Acc 0.9434; ~9% drop for unseen location", `Acc ${f(m2(Q9, "ngram_rf").acc)} (Quad9); cross-era transfer at chance`, "Different protocol (ODoH), wget page loads, single split"],
  ["PH1-2 Moure-Garrido 2026", "DoQ, CloudLab, 4 US sites", "986", "Acc 0.873 pooled; cross-node 53.2-81.0%", `Burst-stats RF acc ${f(m2(Q9, "burst_rf").acc)} (Quad9), ${f(m2(CF, "burst_rf").acc)} (Cloudflare)`, "DoQ on a dedicated port; first-burst truncation; 10x more traces per site"],
  ["Csikor et al. (P3) 2025", "DoQ + HTTP/3, transformer", "500", "> 80% CW accuracy", "Neural models below forests at our sample size", "640k traces vs ours ~2k per resolver"],
], widths: [1700, 1650, 650, 1700, 2050, 1888], firstCol: true, size: 13, caption: "Table 11. Comparison with published results. Rows 1-2 are exact comparisons; the rest are indicative only." } });
add("Two points follow. On identical data our implementation matches the original, so differences in the 2026 results are not implementation artefacts. Against the recent literature, our Quad9 numbers are of the same order as DoHFuse's size-only control and PH1-2's per-node accuracies despite ten times fewer traces per site, while our Cloudflare numbers show that the recent papers' high accuracies depend on a resolver or transport where padding is absent or ineffective. None of those papers measures this, because none audits the resolver's padding.");

// ============================ 5. Ablations
add({ h1: "5. Ablation Studies" });
add("Seven ablations remove, replace or modify one component at a time. Each uses 5 repeated splits (3 for the neural models) on both resolvers.");
add({ h2: "5.1 A1: feature groups" });
add({ fig: "fig9_ablation_features.png", caption: "Figure 9. Ablation A1: removing and adding feature families (macro-F1)." });
const A = (cnd, k) => g(ab, `${cnd}.features.${k}.f1`);
add(`On unpadded Quad9 the size n-grams carry the attack: sizes alone (uni-grams ${f(A(Q9, "sizes_uni"))}, uni+bi ${f(A(Q9, "sizes_uni_bi"))}) are close to the full F1 set (${f(A(Q9, "ngrams_full(F1)"))}), bursts alone are weaker (${f(A(Q9, "bursts_uni_bi"))}), and tri-grams add nothing (${f(A(Q9, "ngrams_tri"))}), the paper's own observation. On padded Cloudflare, burst n-grams (${f(A(CF, "bursts_uni_bi"))}) are worth ${A(CF, "bursts_uni_bi") > A(CF, "sizes_uni_bi") ? "more" : "less"} than size n-grams (${f(A(CF, "sizes_uni_bi"))}), and removing the size n-grams altogether (F2+F5, ${f(A(CF, "F2+F5(no sizes n-grams)"))}) ${A(CF, "F2+F5(no sizes n-grams)") >= A(CF, "F1+F2+F5(fused)") ? "does not hurt and even raises F1 slightly above the fused set (" + f(A(CF, "F1+F2+F5(fused)")) + ")" : "costs " + f(A(CF, "F1+F2+F5(fused)") - A(CF, "F2+F5(no sizes n-grams)")) + " F1"}: once replies are padded, what remains is how many exchanges a page makes and how they are grouped, not their sizes. Adding timing to the n-grams moves F1 from ${f(A(CF, "ngrams_full(F1)"))} to ${f(A(CF, "F1+F5"))} on Cloudflare and from ${f(A(Q9, "ngrams_full(F1)"))} to ${f(A(Q9, "F1+F5"))} on Quad9. A1 also shows where the fused model's gain on padded traffic comes from. Adding the burst statistics to the n-grams (F1+F2) gives ${f(A(CF, "F1+F2"))} on Cloudflare, and adding the timing histogram on top (F1+F2+F5) gives ${f(A(CF, "F1+F2+F5(fused)"))}. The gain therefore comes from the burst statistics (F2); the explicit timing histogram (F5) adds nothing once they are present. F2 is not free of timing, since its bursts are cut at 25 ms gaps, but its value lies in counting and grouping exchanges rather than in fine-grained inter-arrival times.`);
add({ h2: "5.2 A2-A4: trace prefix, training budget and world size" });
add({ fig: "fig10_ablation_curves.png", caption: "Figure 10. A2: F1 using only the first N TLS records. A3: F1 against training traces per site (fixed test set). A4: F1 against the number of sites in the closed world." });
const P = (cnd, k) => g(ab, `${cnd}.prefix.${k}.ngram_rf.f1`);
add(`A2 shows how early a page gives itself away. On Quad9 the first 20 records give F1 ${f(P(Q9, "20"))} and the first 50 ${f(P(Q9, "50"))} against ${f(P(Q9, "full"))} for the full trace, yet the first 100 records already give ${f(P(Q9, "100"))}. On Cloudflare the values are ${f(P(CF, "20"))}, ${f(P(CF, "50"))}, ${f(P(CF, "100"))} and ${f(P(CF, "full"))}. The first records are the browser's own start-up lookups, which are the same for every site, so the page reveals itself between roughly the 50th and the 100th record, once its own resolutions begin. A passive observer therefore needs only the first hundred or so DoH records after navigation; we did not measure how much time that corresponds to. A3 shows the attack is still data-limited at our budget (F1 keeps rising with traces per site), which is why our absolute numbers sit below papers with 100 visits per site. A4 confirms that accuracy falls as the closed world grows, as in Siby's entropy analysis.`);
add({ h2: "5.3 A5-A7: label composition, curation and model components" });
const comp = (cnd, k) => g(ab, `${cnd}.composition.${k}.f1`);
add(`A5 splits the label set. On Quad9, global sites score ${f(comp(Q9, "global"))} and Pakistani sites ${f(comp(Q9, "pk"))}; on Cloudflare ${f(comp(CF, "global"))} and ${f(comp(CF, "pk"))}. The two halves differ by at most ${f(Math.max(Math.abs(comp(Q9, "pk") - comp(Q9, "global")), Math.abs(comp(CF, "pk") - comp(CF, "global"))))} F1: Pakistani sites are fingerprinted as easily as global ones, so the attack is not limited to the well-studied global sites and the headline numbers are not driven by either half of the label set. A6 removes the ${(rc.challenge_sites || []).length} bot-challenge sites: F1 moves from ${f(g(ab, `${Q9}.curation.full.f1`))} to ${f(g(ab, `${Q9}.curation.curated.f1`))} on Quad9 (no change) and from ${f(g(ab, `${CF}.curation.full.f1`))} to ${f(g(ab, `${CF}.curation.curated.f1`))} on Cloudflare. Challenge pages look alike under padding and are hard to tell apart, so on Cloudflare they slightly understate the attack. Our full-dataset numbers are therefore conservative. A7 tests the CNN's components: with the squeeze-excitation block F1 is ${f(g(ab, `${Q9}.cnn.cnn_se.f1`))}, without it ${f(g(ab, `${Q9}.cnn.cnn_nose.f1`))}, and without the timing channel ${f(g(ab, `${Q9}.cnn.cnn_se_no_timing.f1`))} (Quad9; on Cloudflare ${f(g(ab, `${CF}.cnn.cnn_se.f1`))}, ${f(g(ab, `${CF}.cnn.cnn_nose.f1`))} and ${f(g(ab, `${CF}.cnn.cnn_se_no_timing.f1`))}). The timing channel helps the CNN on both resolvers, and the attention block does not. Together with Table 8 this indicates that channel attention, which helps on long Tor traces (P8), does not help on short DNS traces at our sample size.`);
add({ h2: "5.4 E5: padding, simulated and deployed (RQ3)" });
add({ fig: "fig8_padding_effect.png", caption: "Figure 11. Left: F1 by feature family on the padded (Cloudflare) and unpadded (Quad9) resolver. Right: padding simulated on Quad9 traces (record sizes rounded up to 128 or 468 bytes, or all set to 825 bytes), against the resulting byte overhead." });
const sim = (mode, m = "ngram_rf") => g(e5, `simulated.${mode}.${m}.f1`);
const ov = (mode) => g(e5, `simulated.${mode}.overhead`);
add(`The deployed comparison (left) and the simulation (right) agree. Rounding every record of the unpadded Quad9 traces up to 128-byte blocks cuts the n-gram attack from ${f(sim("none"))} to ${f(sim("128"))} for ${pct(ov("128"), 0)} more bytes; 468-byte blocks cut it to ${f(sim("468"))} for ${pct(ov("468"), 0)}; perfect padding leaves ${f(sim("perfect"))} at ${pct(ov("perfect"), 0)}. The real 468-byte padding on Cloudflare leaves ${f(g(e5, `deployed.${CF}.ngram_rf.f1`))}, below the simulated ${f(sim("468"))}. The two numbers come from different resolvers, so the gap may also reflect other differences between Cloudflare and Quad9 traffic, but it suggests that block rounding alone, if anything, understates what deployed padding removes. Padding removes size information but leaves two other signals. The first is timing: the timing-only model scores ${f(sim("none", "timing_rf"))} on Quad9 and ${f(g(e5, `deployed.${CF}.timing_rf.f1`))} on Cloudflare, about 25 times chance, and padding does not change it. The second is the count and grouping of queries, captured by burst statistics (${f(g(e5, `deployed.${CF}.burst_rf.f1`))} on Cloudflare) and by k-FP. The proposed fused forest combines these signals (its gain comes mainly from the burst statistics, Section 5.1) and degrades much less than the n-gram attack: ${f(sim("468", "fused_rf"))} against ${f(sim("468"))} with 468-byte blocks, and ${f(sim("perfect", "fused_rf"))} against ${f(sim("perfect"))} with perfect padding. Even perfect size padding at more than five times the bytes leaves a combined attack at over half of its unpadded F1. In Siby's padding experiment, 468-byte padding left 0.430 (${f(g(e1, "EDNS0-468-700.f1"))} in our reproduction on their data). Against Chrome and Cloudflare in 2026 we find ${f(g(e5, `deployed.${CF}.ngram_rf.f1`))} with n-grams over 100 sites; in neither setting does padding bring the attack to chance.`);

// ============================ 6. Discussion
add({ h1: "6. Results Analysis and Discussion" });
add({ h2: "6.1 Answers to the research questions" });
add(`**RQ1, does the attack reproduce?** ${e1.LOC1 ? `Yes. On the authors' released data our Python 3 port reaches F1 ${f(e1.LOC1.f1)} on the 1,500-page closed world, ${e1.LOC1.verdict} against the published 0.898 under a tolerance fixed in advance.` : "See Section 4.1."} The Leuven (LOC2) and Singapore (LOC3) results also fall within tolerance${e1.LOC2 && e1.LOC2.tost_p > 0.05 ? " (for LOC2 the difference is inside the margin but the equivalence test is not significant with three folds, so we call it reproduced with lower confidence)" : ""}, and the ranking of the baselines largely reproduces (n-grams first, DF last; k-FP and CUMUL swap places, Section 3.1). ${padSummary()} Two things in the released artefact do not match the paper (the uni-gram-only feature set and the missing curation and DoT data), and we document both.`);
add(`**RQ2, does it transfer?** Within one era, across places, partly yes, as Siby found. Across eras, no: a model trained on 2018-19 European or Singapore traces identifies nothing in 2026 Pakistani traces, and the reverse also fails, including between unpadded resolvers. Transfer even fails between two resolvers on the same network in the same week. The attack itself, however, is alive: retrained on a few local traces per site it reaches F1 ${f(q9N)} against an unpadded resolver from Pakistan. Phase 2's expected mechanism, regional CDN steering, could not be tested: the client stack, TLS version and padding change the representation so much that any location effect is hidden beneath them. Ruling it in or out needs 2026 captures with the same client from a second country. The practical conclusion is that DNS fingerprinting models are as perishable as the client software, and that every published model must be re-trained, not re-used, in line with the drift that P7 and PH1-1 report for Tor traffic.`);
add(`**RQ3, does padding help?** Yes, substantially, but only where it is deployed and only for size features. With Chrome and Cloudflare, padding as deployed removes ${f(q9N - cfN)} of the ${f(q9N)} F1 that the attack achieves without it. Whether a user gets this protection depends on an invisible combination of client and resolver: the same browser on Quad9, NextDNS, DNS.SB or AliDNS gets none. Padding is also not a complete defence: timing and burst structure survive it, and the proposed fused model keeps F1 ${f(F1(CF, "fused_rf"))} on Cloudflare (against ${f(cfN)} for n-grams) and ${f(sim("perfect", "fused_rf"))} under simulated perfect padding. A complete defence would need to shape timing and query counts as well as sizes.`);
add({ h2: "6.2 Does the work close the research gap?" });
add("Phase 2 identified four gaps. Gap 1 (the 2020 attack never re-measured): we re-ran it on its own data and re-measured it on 2026 DoH from a new browser. Gap 2 (transfer never tested outside one country, never from South Asia): we provide, to our knowledge, the first encrypted-DNS fingerprinting measurement from Pakistan and the first cross-era transfer matrix, and find that the question 'does a model transfer across regions?' is dominated by 'does it survive a client upgrade?'. Gap 3 (padding simulated, never tied to attack accuracy as deployed): we audited 11 resolvers, found that Cloudflare's padding has changed since 2019 and that most resolvers do not pad, and measured the attack against a padding and a non-padding resolver under identical conditions. Gap 4 (thin statistics): every number carries repeated-split variance or a site-clustered bootstrap interval, and the reproduction uses a pre-registered tolerance with an equivalence test.");
add({ h2: "6.3 Strengths" });
add("- Every comparison changes one factor: the two PK-DoH-2026 conditions share sites, network, browser, time and collection script and differ only in the resolver.");
add("- Padding is measured, not assumed: decrypted ground truth from our own probes, confirmed passively on the wire (Figure 3).");
add("- The reproduction is anchored to the authors' own data and judged against a tolerance fixed before running code.");
add("- The pipeline is unattended, resumable and released, so the same matrix can be re-run from another network.");
add({ h2: "6.4 Limitations and threats to validity" });
add(`- **One network.** Campus Wi-Fi vs mobile 4G (RQ2b) was not collected (Table 3), so network transfer within Pakistan remains untested. The resolver split partly substitutes.`);
add(`- **Sample size.** About ${n_ps(Q9) || 10} traces per site per resolver, against 60-200 in the 2018 data. A3 shows F1 still rising with more traces, so our absolute values are lower bounds; the neural models in particular are under-trained.`);
add("- **Crawled traffic.** Headless Chrome with a fresh profile, as in all reviewed attack papers; PH1-3 and P10 show that real users are less regular, which would lower all our numbers. Twelve sites served bot-challenge pages; removing them (A6) leaves Quad9 unchanged and raises Cloudflare slightly, so they make our Cloudflare numbers conservative rather than inflated.");
add("- **Partial reproduction scope.** Every E1 row uses 3 of the 10 folds (1 fold for the two check rows); LOC2 and LOC3 use 20 of their roughly 200 and 100 samples per page; all rows except the full-vocabulary check keep only n-grams seen in at least three training traces. Table 10 gives pages, samples and folds for each row.");
add("- **Closed world.** As planned, no open-world evaluation; an adversary facing unmonitored sites would do worse.");
add("- **Analyses planned but not done.** McNemar's test, Holm-Bonferroni correction, Cliff's delta, the offset-calibration ablation, the derived transfer and padding metrics, and the confusion-clustering and feature-importance analysis (Table 3).");
add("- **Concurrency.** Eight workers ran in parallel on one laptop; this can add timing noise, which may understate timing features, but cannot leak traces between conditions (one resolver address per capture filter).");
add({ h2: "6.5 Ethics and reproducibility" });
add("All traffic analysed was generated by our own crawler on our own machine to resolvers we chose; no third-party, campus or user traffic was captured, and no attempt was made to measure filtering by any operator. The code (capture, extraction, audit, features, models, experiments, figures), the per-trace metadata and the extracted traces of PK-DoH-2026 are kept in the project repository. Every table and figure can be regenerated with six scripts, run in the order given in the code archive's README: capture/extract.py (traces), padding_audit.py (Table 5), run_e1_queue.py with e1_reproduce.py (Table 10), experiments.py (all other experiments), report_data.py and figures.py.");

// ============================ 7. References
add({ h1: "7. References" });
add("Labels in brackets are the paper numbers used throughout Phases 1-3: P1-P10 for the Phase 2 set and PH1-1 to PH1-3 for the Phase 1 set.");
[
  "Siby, S., Juarez, M., Diaz, C., Vallina-Rodriguez, N., & Troncoso, C. (2020). Encrypted DNS => privacy? A traffic analysis perspective. NDSS 2020. https://doi.org/10.14722/ndss.2020.24301",
  "Hayes, J., & Danezis, G. (2016). k-fingerprinting: A robust scalable website fingerprinting technique. USENIX Security 2016, 1187-1203.",
  "Panchenko, A., Lanze, F., Zinnen, A., Henze, M., Pennekamp, J., Wehrle, K., & Engel, T. (2016). Website fingerprinting at Internet scale. NDSS 2016.",
  "Sirinam, P., Imani, M., Juarez, M., & Wright, M. (2018). Deep fingerprinting: Undermining website fingerprinting defenses with deep learning. ACM CCS 2018, 1928-1943. https://doi.org/10.1145/3243734.3243768",
  "[PH1-2] Moure-Garrido, M., Garcia-Rubio, C., & Campo, C. (2026). The persistent vulnerability: Characterizing metadata leakage in DNS over QUIC. Computer Networks, 286, 112464. https://doi.org/10.1016/j.comnet.2026.112464",
  "[PH1-1] Shusterman, A., David, R., & Oren, Y. (2026). Understanding and addressing concept drift in website fingerprinting. Computer Networks, 275, 111811. https://doi.org/10.1016/j.comnet.2025.111811",
  "[PH1-3] Deng, X., Chen, J., Yu, L., Zhang, Y., Gu, Z., Qiu, C., Zhao, X., Xu, K., & Li, Q. (2026). Beyond a single perspective: Towards a realistic evaluation of website fingerprinting attacks. Tsinghua Science and Technology, 31(3), 1381-1392. https://doi.org/10.26599/TST.2025.9010167",
  "[P1] Zhang, Z., Cheng, Y., Zhang, Z., Huo, X., & Wu, C. (2026). DoHFuse: A dual-branch architecture with DMAG-LSTM for website fingerprinting over DNS over HTTPS/3. IEEE Internet of Things Journal. https://doi.org/10.1109/JIOT.2026.3734028",
  "[P2] Salari, M. A., Kumar, A., Rinaudi, F., Tourani, R., Sacco, A., & Esposito, F. (2025). Privacy analysis of Oblivious DNS over HTTPS: A website fingerprinting study. IEEE/IFIP DSN 2025, 415-428. https://doi.org/10.1109/DSN64029.2025.00048",
  "[P3] Csikor, L., Lian, Z., Zhang, H., Lakshmanan, N., & Divakaran, D. M. (2025). DNS-over-QUIC and HTTP/3 in the era of transformers: The new Internet privacy battle. IEEE Communications Magazine, 63(11), 114-120. https://doi.org/10.1109/MCOM.004.2400680",
  "[P8] Gong, J., Cai, W., Liang, S., Guan, Z., Wang, T., & Chang, E.-C. (2026). WFCAT: Augmenting website fingerprinting with channel-wise attention on timing features. IEEE TDSC, 23(1), 149-163. https://doi.org/10.1109/TDSC.2025.3605197",
  "[P10] Jansen, R., Wails, R., & Johnson, A. (2026). A measurement of genuine Tor traces for realistic website fingerprinting. PAM 2026, LNCS 16477, 277-293. https://doi.org/10.1007/978-3-032-18268-5_13",
  "[P7] Zhao, X., Deng, X., Cui, T., Zhang, Y., Xu, K., & Li, Q. (2026). Robust LLM-based website fingerprinting under dynamic real-world conditions. WWW '26, 2800-2811. https://doi.org/10.1145/3774904.3792288",
  "[P5] Bielefeld, P., Hoffmann, F., Sasalla, S., Ververis, V., & Bajpai, V. (2026). The future of DNS privacy: A comparison of DNS over QUIC and DNS over HTTP/3. PAM 2026, LNCS 16477, 202-228. https://doi.org/10.1007/978-3-032-18268-5_10",
  "Hoffman, P., & McManus, P. (2018). DNS queries over HTTPS (DoH). RFC 8484. https://doi.org/10.17487/RFC8484",
  "Hu, Z., Zhu, L., Heidemann, J., Mankin, A., Wessels, D., & Hoffman, P. (2016). Specification for DNS over Transport Layer Security (TLS). RFC 7858. https://doi.org/10.17487/RFC7858",
  "Mayrhofer, A. (2016). The EDNS(0) padding option. RFC 7830. https://doi.org/10.17487/RFC7830",
  "Mayrhofer, A. (2018). Padding policies for extension mechanisms for DNS (EDNS(0)). RFC 8467. https://doi.org/10.17487/RFC8467",
].forEach((r) => add({ ref: r }));

exports.titleBlock = S.titleBlock;
exports.blocks = blocks;
