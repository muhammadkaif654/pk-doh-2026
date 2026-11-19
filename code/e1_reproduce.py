"""E1 / RQ1 - Reproduce Siby et al. (NDSS 2020) on their released data.

Targets (paper values, B0):
  Table II  LOC1 full dataset, 1,500 pages            F1 0.898 +- 0.003 (10-fold CV)
  Table VI  LOC2 / LOC3 in-domain                      F1 0.908 / 0.917
  Table VI  GOOGLE / CLOUD in-domain                   F1 0.880 / 0.885
  Table VII EDNS0-128 (Cloudflare pads 128)            F1 0.691
            EDNS0-468 (mitmproxy pads 468)             F1 0.430
            Perfect padding (all sizes -> 825)         F1 0.066
Pre-registered tolerance (Phase 2, Step 7): reproduced if |dF1| <= 0.03,
partly if <= 0.10, else not reproduced; TOST equivalence test, margin 0.03.

Classifier = B1: n-grams (uni+bi) of TLS record sizes and burst sizes, random
forest of 100 trees, majority vote; stratified 10-fold CV.  We additionally run
the uni-gram-only configuration found in the *released* code (classify()
uses NgramsExtractor(max_ngram_len=1)), which differs from the paper text.

Usage: python e1_reproduce.py <experiment> [n_samples] [n_classes|all] [n_folds_to_run]
Each fold's result is written to results/e1/<exp>_fold<k>.json (resumable).
"""
import json, os, sys, time
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold

import common

OUT = os.path.join(common.RESULTS, "e1")
os.makedirs(OUT, exist_ok=True)

PAPER = {"LOC1": 0.898, "LOC1_uni": 0.898, "LOC1_exact": 0.898, "LOC2": 0.908, "LOC3": 0.917, "GOOGLE": 0.880,
         "CLOUD": 0.885, "EDNS0-128": 0.691, "EDNS0-468": 0.430, "PERFECT": 0.066,
         "EDNS0-128-adblock": 0.325}
# Table I: the countermeasure experiments use 700 pages x 60 samples. "-700" runs use the 700 pages
# that have >= 60 samples in the released EDNS0-468 data (the other 800 have only 10-19).
for _k in ("EDNS0-128", "EDNS0-468", "PERFECT", "PERFECT-nodir"):
    PAPER[_k + "-700"] = PAPER.get(_k, 0.066)


def pages700():
    c = common.load_siby("EDNS0-468").groupby("class_label").size()
    return sorted(c[c >= 60].index)


def run(exp, n_samples=60, n_classes=None, n_run=3, n_jobs=int(os.environ.get("NJOBS", 3)), ngram=2, min_df=3):
    """10-fold stratified CV split as in the paper; the first `n_run` folds are evaluated
    (compute budget). min_df=3 drops n-grams seen in < 3 training traces (label-agnostic);
    'LOC1_exact' keeps every n-gram (min_df=1) as in the paper."""
    folds = 10
    base = exp[:-4] if exp.endswith("-700") else exp
    ds = {"LOC1_uni": "LOC1", "PERFECT": "LOC1", "PERFECT-nodir": "LOC1", "LOC1_exact": "LOC1"}.get(base, base)
    if exp == "LOC1_exact":
        min_df = 1
    df = common.load_siby(ds)
    classes = None
    if n_classes:
        rng = np.random.RandomState(1)
        counts = df.groupby("class_label").size()
        elig = sorted(counts[counts >= n_samples].index)
        classes = sorted(rng.choice(elig, size=min(n_classes, len(elig)), replace=False))
    if exp.endswith("-700"):
        classes = pages700()
    d = common.trim_per_class(df, n_samples, classes=classes, seed=0)
    seqs = list(d.lengths)
    if base == "PERFECT":  # every record set to 825 bytes, direction kept
        seqs = [np.sign(s) * 825 for s in seqs]
    if base == "PERFECT-nodir":  # literal reading of the paper: all packets 825, direction dropped too
        seqs = [np.full(len(s), 825) for s in seqs]
    y = d.class_label.values
    if exp == "LOC1_uni":
        ngram = 1
    print(f"{exp}: {len(y)} traces, {len(set(y))} classes, {n_samples}/class, ngram<= {ngram}", flush=True)
    skf = StratifiedKFold(folds, shuffle=True, random_state=0)
    for k, (tr, te) in enumerate(skf.split(seqs, y)):
        if k >= n_run:
            break
        path = os.path.join(OUT, f"{exp}_fold{k}.json")
        if os.path.exists(path):
            continue
        t0 = time.time()
        fx = common.NgramFeatures(ngram, min_df=min_df)
        Xtr = fx.fit_transform([seqs[i] for i in tr])
        Xte = fx.transform([seqs[i] for i in te])
        classes, proba = common.streaming_forest(Xtr, y[tr], Xte, n_trees=100, n_jobs=n_jobs, seed=k)
        pred = classes[proba.argmax(1)]
        m = common.metrics(y[te], pred, proba, classes)
        m.update(fold=k, n_features=Xtr.shape[1], seconds=round(time.time() - t0, 1))
        # per-class F1 for the CDF figure (fold 0 only to save space)
        if k == 0:
            from sklearn.metrics import f1_score
            labs = np.unique(y)
            m["per_class_f1"] = dict(zip(map(int, labs), map(float, f1_score(y[te], pred, labels=labs, average=None, zero_division=0))))
            m["y_true"] = list(map(int, y[te])); m["y_pred"] = list(map(int, pred))
        with open(path, "w") as f:
            json.dump(m, f)
        print(f"  fold {k}: F1={m['f1']:.4f} acc={m['acc']:.4f} top5={m['top5']:.4f} "
              f"feats={Xtr.shape[1]} {m['seconds']}s", flush=True)


def summarise(exp):
    import glob
    fs = sorted(glob.glob(os.path.join(OUT, f"{exp}_fold*.json")))
    rs = [json.load(open(f)) for f in fs]
    out = {"exp": exp, "folds": len(rs)}
    for key in ("acc", "top5", "precision", "recall", "f1"):
        m, s, ci = common.mean_ci([r[key] for r in rs])
        out[key] = m; out[key + "_sd"] = s; out[key + "_ci"] = ci
    tgt = PAPER.get(exp)
    if tgt is not None:
        d = out["f1"] - tgt
        out["paper_f1"] = tgt; out["delta_f1"] = d
        out["verdict"] = ("reproduced" if abs(d) <= 0.03 else "partly reproduced" if abs(d) <= 0.10
                          else "not reproduced")
        out["tost_p"] = common.tost([r["f1"] for r in rs], tgt, 0.03) if len(rs) > 1 else None
    return out


if __name__ == "__main__":
    common.low_priority()
    exp = sys.argv[1]
    ns = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    nc = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] != "all" else None
    n_run = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    run(exp, ns, nc, n_run)
    s = summarise(exp)
    print(json.dumps(s, indent=1, default=float))
    common.save_json(s, f"e1/{exp}_summary.json")
