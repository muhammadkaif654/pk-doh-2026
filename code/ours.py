"""Dataset assembly for our 2026 captures (PK-DoH-2026) and shared evaluation loops."""
import json, os, re
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedShuffleSplit

import common

CHALLENGE = re.compile(r"just a moment|attention required|access denied|captcha|are you a robot|"
                       r"verify you are human|request rejected|forbidden", re.I)
SITES = pd.read_csv(os.path.join(common.HERE, "capture", "sites.csv"))


def load(cond, curated=False, min_records=5, n_per_site=None, seed=0):
    """Load one condition. Removes crashed visits and degenerate traces (< min_records).
    curated=True also removes sites whose visits mostly land on bot-challenge pages
    (the analogue of Siby et al.'s removal of 'strange' pages)."""
    d = common.load_ours(cond)
    d = d[~d["status"].str.startswith(("crash", "error"))]
    d = d[d["lengths"].apply(len) >= min_records].copy()
    d["challenge"] = d["title"].fillna("").str.contains(CHALLENGE)
    if curated:
        bad = d.groupby("site_id")["challenge"].mean()
        d = d[~d["site_id"].isin(bad[bad > 0.5].index)]
    d["label"] = d["site_id"]
    d["cond"] = cond
    if n_per_site:
        d = common.trim_per_class(d, n_per_site, seed=seed, label="label")
    return d.reset_index(drop=True)


def challenge_sites(cond):
    d = common.load_ours(cond)
    d["challenge"] = d["title"].fillna("").str.contains(CHALLENGE)
    s = d.groupby("site_id")["challenge"].mean()
    return sorted(s[s > 0.5].index)


def balanced(d, label="label", n=None):
    """Equal traces per site. n defaults to the 10th percentile of per-site counts (min 3);
    sites with fewer traces than n are dropped rather than shrinking every site."""
    counts = d.groupby(label).size()
    if n is None:
        n = max(3, int(np.percentile(counts, 10)))
    return common.trim_per_class(d, int(n), label=label), int(n)


def siby_as_ours(name, site_ids=None, n=None, seed=0):
    """Siby dataset restricted to our shared global sites, relabelled with our site ids."""
    df = common.load_siby(name)
    g = SITES[SITES.group == "global"]
    m = dict(zip(g.siby_index.astype(int), g.site_id))
    df = df[df.class_label.isin(m.keys())].copy()
    df["label"] = df.class_label.map(m)
    if site_ids is not None:
        df = df[df.label.isin(site_ids)]
    df["times"] = None
    if n:
        df = common.trim_per_class(df, n, seed=seed, label="label")
    return df.reset_index(drop=True)


def repeated_splits(d, n_rep=10, test_size=0.2, seed=0):
    n_cls = d["label"].nunique()
    test_size = max(test_size, n_cls / len(d))  # at least one test trace per site
    sss = StratifiedShuffleSplit(n_splits=n_rep, test_size=test_size, random_state=seed)
    return list(sss.split(np.zeros(len(d)), d["label"].values))


def evaluate(model_fn, tr, te, seed=0):
    classes, proba = model_fn(tr, te, seed=seed)
    pred = classes[np.argmax(proba, 1)]
    y = te["label"].values
    m = common.metrics(y, pred, proba, classes)
    return m, y, pred


def cluster_bootstrap_ci(y_true, y_pred, n_boot=1000, seed=0):
    """Site-clustered bootstrap CI of macro-F1: resample SITES (classes) with replacement."""
    from sklearn.metrics import f1_score
    y_true = np.asarray(y_true); y_pred = np.asarray(y_pred)
    labs = np.unique(y_true)
    per = f1_score(y_true, y_pred, labels=labs, average=None, zero_division=0)
    rng = np.random.RandomState(seed)
    boots = [per[rng.randint(0, len(labs), len(labs))].mean() for _ in range(n_boot)]
    return float(per.mean()), (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))), per, labs


def summarise(runs):
    out = {}
    for key in ("acc", "top5", "precision", "recall", "f1"):
        vals = [r[key] for r in runs if key in r]
        if vals:
            m, s, ci = common.mean_ci(vals)
            out[key] = m; out[key + "_sd"] = s; out[key + "_ci"] = list(ci)
    out["n_runs"] = len(runs)
    return out
