// Static (result-independent) prose for the Phase 3 document.
exports.titleBlock = [
  ["Proposed Research Topic", "Does a 2020 Attack Still Work? Reproducing Website Fingerprinting on Encrypted DNS"],
  ["Section", "AI-B"],
  ["Group Members", "[Muhammad Kaif - 24I0071]      [Samran Ahmad - 24I3013]"],
  ["Phase", "Phase 3: Research Implementation and Experimental Evaluation"],
  ["Date of Submission", "15_11_2026"],
];

exports.deliverableMap = [
  ["1. Implementation of the proposed methodology", "Section 1 (what was built, three tracks, models), Section 1.5 (changes to the Phase 2 design and why)", "Implementation of Proposed Methodology"],
  ["2. Dataset and preprocessing", "Section 2 (published data, PK-DoH-2026 capture, padding audit, preprocessing, splits, setup)", "Implementation of Proposed Methodology"],
  ["3. Baseline evaluation", "Section 3 (B1-B6 on both the 2018 data and our 2026 data, all metrics)", "Experimental Evaluation and Comparative Analysis"],
  ["4. Graphical results", "Figures 1-11 throughout Sections 1-6", "Experimental Evaluation and Comparative Analysis"],
  ["5. Comparison with existing research", "Section 4 (reproduction against Siby et al.; comparison with recent encrypted-DNS attacks)", "Experimental Evaluation and Comparative Analysis"],
  ["6. Ablation studies", "Section 5 (seven ablations A1-A7)", "Ablation Studies and Research Validation"],
  ["7. Results analysis and discussion", "Section 6 (answers to RQ1-RQ3, strengths, limitations, threats to validity)", "Ablation Studies and Research Validation"],
];

exports.intro = [
  "Phase 2 designed a three-track study of website fingerprinting on encrypted DNS. Track A reproduces the attack of Siby et al. (NDSS 2020) on their released data (RQ1). Track B collects new traces from Pakistan in 2026 and tests whether the attack, and models trained on the 2018-19 data, still work (RQ2). Track C audits the EDNS(0) padding that public resolvers actually deploy and measures what it removes (RQ3). Phase 3 implements all three tracks, end to end, on our own machine. Every number in this document was produced by the code in our repository from data we either downloaded from the authors or captured ourselves.",
  "Table 1 maps each component required by the Phase 3 brief to the section that delivers it.",
];

exports.implIntro = "The implementation is a single Python code base (about 1,700 lines) with five modules: the capture pipeline (capture/collect.py, capture/extract.py), the padding audit (padding_audit.py), shared features and statistics (common.py), the model zoo (models.py) and the experiment drivers (e1_reproduce.py, experiments.py), plus the figure scripts. Figure 1 shows the pipeline as implemented; dashed boxes mark where it differs from the Phase 2 design.";

exports.trackA = [
  "We cloned the authors' repository (spring-epfl/doh_traffic_analysis) and parsed every released dataset into one table of signed TLS-record sequences, using the authors' own encoding (positive = client to resolver, negative = resolver to client, rebuilt from their sent / received / order arrays). The authors' code is Python 2 and does not run on a current interpreter, so we ported the feature extractor and pipeline to Python 3 line by line and kept their settings: uni-grams and bi-grams of record sizes and of burst sizes, counted per trace, fed to a random forest of 100 fully grown trees with probability averaging, under stratified 10-fold cross-validation.",
  "Two practical problems had to be solved. First, with 1,500 classes a single fully grown tree stores the class distribution of every node, about 1 GB in memory, so the 100-tree forest needs about 100 GB of RAM; our machine has 16 GB. We therefore implemented a streaming forest: the same 100 bootstrap trees with the same split rule are grown one batch at a time, each tree scores the test fold, its probabilities are added to a running sum and the tree is freed. The output is the same averaged-probability forest; only the peak memory changes. Second, the full bi-gram vocabulary has 268,000 features, which makes each fold take more than an hour on a laptop CPU. The main runs therefore keep n-grams that occur in at least three training traces (89,000 features), a filter that never looks at labels; one fold with the complete vocabulary is run as a check (row LOC1, all n-grams).",
];

exports.trackB = [
  "We built an unattended crawler that reproduces Siby et al.'s collection loop with a 2026 browser. For every visit it creates a fresh Chrome profile whose Local State forces Secure DNS into strict mode with exactly one DoH server given by IP address, starts dumpcap filtered to that address on port 443, loads http://<site> in headless Chrome 157 through Selenium with a 30 s page-load timeout, waits 5 s, closes the browser and stops the capture. QUIC is disabled so that the DoH channel is HTTP/2 over TLS 1.3, the transport of the 2020 attack. Sites are visited round-robin in a freshly shuffled order every round, so that each site's samples are spread over the whole collection period.",
  "Eight workers run in parallel. Each resolver is reached through four of its own anycast addresses (Cloudflare 1.1.1.1, 1.0.0.1, 162.159.36.1, 162.159.46.1; Quad9 9.9.9.9, 149.112.112.112, 9.9.9.10, 149.112.112.10), each capture is filtered to one address, so traces from different workers can never mix. We verified that all four addresses of a resolver return byte-identical, identically padded replies (Section 2.2). A side capture of plaintext port 53 during test visits showed no query for any visited site, confirming that every name was resolved over DoH.",
];

exports.trackC = "The audit sends a fixed set of 16 queries (short and long answers, A, AAAA, MX and TXT records, global and Pakistani names, and one non-existent name) to 11 public resolvers, over DoH (HTTP/2, RFC 8484) and DoT (RFC 7858), once without and once with a client EDNS(0) Padding option (RFC 7830; queries padded to 128 bytes as RFC 8467 recommends for clients). Because our script is the endpoint, it decrypts the reply and reads the ground truth directly: whether the reply carries a Padding option, how long it is, and whether the DNS message length is a multiple of 128 or 468 bytes. Only our own 704 queries are involved and no third-party traffic is observed.";

exports.proposedIntro = "Phase 2 framed the project as a measurement study: the proposed method is the reproduce-then-transfer protocol, evaluated with a fixed classifier so that 2018 and 2026 numbers stay comparable. To answer RQ3 ('does timing recover what padding removes?', and more broadly what survives padding) we also implemented the two models Phase 2 proposed as secondary classifiers:";
exports.proposed = [
  "**Fused RF (proposed).** One random forest over three feature families: the size n-grams of Siby et al. (F1), 24 burst statistics computed with the 25 ms inter-burst gap of PH1-2 (F2), and a timing representation after WFCAT (P8): for 20 time slots of 250 ms and each direction, a histogram of log-spaced inter-arrival times (F5, 320 values). Sizes, bursts and timing enter the same trees, so the forest can fall back on burst structure and timing when sizes are padded. Ablation A1 (Section 5.1) shows which of the two carries the gain: the burst statistics, which are themselves cut at 25 ms time gaps.",
  "**1D-CNN with squeeze-and-excitation (proposed).** Three convolutional blocks (32, 64, 128 channels, kernel 5, batch normalisation) each followed by a squeeze-and-excitation channel-attention layer, global average pooling and a two-layer head, over the first 200 records encoded in three channels: signed size, log inter-arrival time, and direction (F3). Training uses AdamW, cosine learning-rate decay, label smoothing 0.05, a random shift of up to three positions as augmentation, and early stopping on a validation split carved out of the training data only.",
  "**Recovery procedure (E4).** A model trained on dataset X is retrained after adding k = 1, 2 or 5 traces per site from dataset Y, and tested on held-out traces of Y. The F1-versus-k curve prices the cost of adapting a stale model to a new resolver, place or year.",
];

exports.changesIntro = "The instructor gave no written or verbal feedback on our Phase 2 submission, so there was no external feedback to incorporate. We instead list every change we made to the Phase 2 design during implementation, with the reason, so that the evaluation can be judged against what was actually run (Table 3). Items marked 'not done' are also listed as limitations in Section 6.4.";
exports.changes = [
  ["Siby DOT dataset and the 60-sample GOOGLE / CLOUD sets", "Planned for E1 and the DoT comparison", "Not released by the authors (the repository has no DOT folder; GOOGLE and CLOUD have as few as one sample for some pages)", "DoT is evaluated through our active audit only; DoT traffic analysis is left to future work"],
  ["List of 'strange' pages used for curation", "Reproduce Table II 'curated' row", "File referenced by the authors' code is not in the repository", "We reproduce the 'full dataset' row (0.898); our own curation (bot-challenge pages) is an ablation"],
  ["Released code vs paper", "Run released code unchanged", "Released classify() uses uni-grams only, the paper states uni+bi-grams; code is Python 2", "Ported to Python 3; both configurations reported (rows LOC1 and LOC1 uni)"],
  ["Random forest memory", "sklearn RandomForest", "1,500-class trees need ~100 GB RAM", "Streaming forest (identical model, trees freed after scoring)"],
  ["n-gram vocabulary", "All n-grams", "268k features: > 1 h per fold", "Keep n-grams seen in >= 3 training traces (label-agnostic); one full-vocabulary fold as a check"],
  ["Folds for E1", "10-fold CV, all folds", "Compute budget on one laptop", "Paper's 10-fold split; first three folds evaluated (paper SD <= 0.003)"],
  ["Resolvers for Track B", "'Two resolvers that differ in padding'", "Audit result (Section 2.2)", "Cloudflare (pads replies to 468 B when the client pads, which Chrome does) and Quad9 (never pads)"],
  ["Traces per site", "30 per site per condition", "About 25-40 s per page load; deadline", "10 rounds per site per resolver (Siby: 10 samples reach F1 0.887 vs 0.913 at 100)"],
  ["Second network (mobile hotspot)", "Campus Wi-Fi vs mobile 4G", "Each condition costs ~3 GB of mobile data; both members could not be co-located before the deadline", "One network (residential Wi-Fi); network transfer replaced by resolver transfer; listed as a limitation"],
  ["TLS 1.3 record view", "Not anticipated", "2018 data is TLS 1.2 (handshake in clear); 2026 traffic is TLS 1.3 (handshake encrypted in application-data records)", "Encrypted handshake and pre-request session tickets removed so both eras start at the first DoH exchange"],
  ["Recovery budget k (E4)", "k = 0, 1, 5, 10, 20 target traces per site", "Only 10 traces per site were collected and half are held out for testing, leaving at most 5", "k = 0, 1, 2, 5"],
  ["Timing slot width (F5)", "Slots of about 10-20 ms", "Our 2026 traces last about 10 s (median); 10-20 ms slots give 500-1,000 mostly empty slots", "20 slots of 250 ms (first 5 s), 8 log-spaced IAT bins per slot and direction"],
  ["Paired tests and effect sizes (Step 9)", "McNemar's test, Holm-Bonferroni across the transfer matrix, Cliff's delta", "Time budget", "Not done. Wilcoxon signed-rank over paired splits, site-clustered bootstrap CIs and TOST are used instead"],
  ["Constant-offset calibration ablation", "Calibrated variant evaluated as an ablation", "Time budget", "Not done. Block-index features (F4), which absorb small size offsets, are used as a partial substitute"],
  ["Derived metrics (Step 8)", "Transfer ratio and asymmetry, recovery AUC, F1 reduction per 100 bytes of overhead", "Time budget", "Not done. The underlying values are reported: transfer F1 (Figure 7), F1 at each k (Figure 8), F1 against % byte overhead (Figure 11)"],
  ["Error analysis (Step 11)", "Confusion clustering and feature-importance shift", "Time budget", "Not done. Only the per-site F1 distribution (Figure 5) is reported"],
  ["Countermeasure datasets (E1)", "Use as released", "Released EDNS0-128 has 1,500 pages (84-89 samples each) and EDNS0-468 has 1,500 pages, of which only 700 have >= 60 samples; the paper uses 700 x 60", "Table VII rows evaluated on those 700 pages x 60 samples; 1,500-page runs kept as sensitivity rows"],
  ["Bot-challenge pages", "Not anticipated", "Twelve sites serve a bot-check page to headless Chrome", "Kept in the full dataset (they are what an adversary's crawler would also see); removed in the curated variant"],
];

exports.limitationsFixed = [];
