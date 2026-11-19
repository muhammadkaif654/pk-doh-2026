"""Shared data loading, feature extraction and evaluation utilities (Python 3).

Feature sets (Phase 2, Table 3):
  F1  n-grams of signed TLS record sizes and of burst sizes (Siby et al., NDSS'20)
  F2  burst statistics (Moure-Garrido et al., 2026, 'PH1-2')
  F3  first-L sequence (size, log-IAT) for the 1D-CNN
  F4  padding-aware sizes (block index for 128/468 blocks, RFC 8467)
  F5  timing-only slot histograms of log-spaced IATs (after WFCAT, P8)
Baselines: k-FP (Hayes & Danezis 2016), CUMUL (Panchenko et al. 2016), DF (Sirinam et al. 2018).
"""
import glob, json, os, pickle, re
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.feature_extraction.text import CountVectorizer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
SIBY_DATA = os.path.join(ROOT, "baseline_siby", "dataset")
SIBY_URLS = os.path.join(ROOT, "baseline_siby", "code", "collection", "short_list_1500")
CACHE = os.path.join(ROOT, "data", "cache")
RESULTS = os.path.join(ROOT, "results")
FIGS = os.path.join(ROOT, "figures")
for d in (CACHE, RESULTS, FIGS):
    os.makedirs(d, exist_ok=True)


def low_priority():
    """Run experiments below normal priority so the trace collector keeps its timing."""
    try:
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if os.name == "nt" else 10)
    except Exception:
        pass

DATE_RE = re.compile(r"(\d\d-\d\d-\d\d)")


# ----------------------------------------------------------------------------- loading
def _recover_order(sent, received, order):
    order = np.asarray(order)
    seq = np.zeros(len(order), dtype=np.int32)
    pos = np.flatnonzero(order > 0)
    neg = np.flatnonzero(order < 0)
    if len(pos) != len(sent) or len(neg) != len(received):
        return None
    seq[pos] = sent
    seq[neg] = -np.asarray(received, dtype=np.int32)
    return seq


def _parse_file(fpath):
    rows = []
    fname = os.path.basename(fpath)
    m = DATE_RE.search(fname)
    date = m.group(1) if m else ""
    try:
        with open(fpath) as f:
            data = json.load(f)
    except Exception:
        return rows
    for key, v in data.items():
        try:
            seq = _recover_order(v["sent"], v["received"], v["order"])
        except (KeyError, TypeError):
            continue
        if seq is None or len(seq) == 0:
            continue
        rows.append((int(key.split(".")[0]), seq, date, fname))
    return rows


def load_siby(name):
    """Return DataFrame(class_label:int, lengths:np.ndarray, date, fname) for a Siby dataset."""
    cache = os.path.join(CACHE, f"siby_{name}.pkl")
    if os.path.exists(cache):
        return pd.read_pickle(cache)
    files = sorted(glob.glob(os.path.join(SIBY_DATA, name, "**", "*.json"), recursive=True))
    rows = []
    with ProcessPoolExecutor(max_workers=8) as ex:
        for r in ex.map(_parse_file, files, chunksize=4):
            rows.extend(r)
    df = pd.DataFrame(rows, columns=["class_label", "lengths", "date", "fname"])
    df["date"] = pd.to_datetime(df["date"], format="%d-%m-%y", errors="coerce")
    df.to_pickle(cache)
    return df


def siby_urls():
    return [l.strip() for l in open(SIBY_URLS)]


def load_ours(cond):
    """Our 2026 captures: DataFrame with site_id, domain, group, lengths, times, status, title..."""
    path = os.path.join(ROOT, "data", "traces", f"{cond}.jsonl")
    rows = [json.loads(l) for l in open(path)]
    df = pd.DataFrame(rows)
    df["lengths"] = df["lengths"].apply(lambda x: np.asarray(x, dtype=np.int32))
    df["times"] = df["times"].apply(lambda x: np.asarray(x, dtype=np.float64))
    df["round"] = df["round"].astype(int)
    return df


def trim_per_class(df, n, classes=None, seed=0, label="class_label"):
    """Keep classes with >= n samples, then n samples per class (Siby's trim_df), optionally a class subset."""
    counts = df.groupby(label).size()
    ok = counts[counts >= n].index
    if classes is not None:
        ok = [c for c in ok if c in set(classes)]
    d = df[df[label].isin(ok)]
    rng = np.random.RandomState(seed)
    keep = []
    for _, idx in d.groupby(label).indices.items():
        keep.extend(d.index[rng.choice(idx, size=n, replace=False)])
    return d.loc[sorted(keep)].reset_index(drop=True)


# ----------------------------------------------------------------------------- F1: n-grams
def bursts(seq):
    seq = np.asarray(seq)
    if len(seq) == 0:
        return seq
    s = np.sign(seq)
    idx = np.flatnonzero(np.diff(s) != 0) + 1
    return np.array([c.sum() for c in np.split(seq, idx)])


def _tok(x):
    return x.split()


class NgramFeatures:
    """Siby et al. features: counts of 1..n-grams of record sizes and of burst sizes (sparse)."""

    def __init__(self, n=2, use_sizes=True, use_bursts=True, min_df=1):
        self.n, self.use_sizes, self.use_bursts = n, use_sizes, use_bursts
        mk = lambda: CountVectorizer(analyzer="word", tokenizer=_tok, token_pattern=None,
                                     lowercase=False, ngram_range=(1, n), min_df=min_df,
                                     dtype=np.float32)
        self.v_size, self.v_burst = mk(), mk()

    @staticmethod
    def _docs(seqs, burst):
        return [" ".join(map(str, bursts(s) if burst else s)) for s in seqs]

    def fit_transform(self, seqs):
        mats = []
        if self.use_sizes:
            mats.append(self.v_size.fit_transform(self._docs(seqs, False)))
        if self.use_bursts:
            mats.append(self.v_burst.fit_transform(self._docs(seqs, True)))
        return sp.hstack(mats).tocsr()

    def transform(self, seqs):
        mats = []
        if self.use_sizes:
            mats.append(self.v_size.transform(self._docs(seqs, False)))
        if self.use_bursts:
            mats.append(self.v_burst.transform(self._docs(seqs, True)))
        return sp.hstack(mats).tocsr()


# ----------------------------------------------------------------------------- F2: burst statistics (PH1-2)
def burst_stats(seq, times=None, thr=0.025):
    """Per-trace statistics of bursts. With times, bursts are split by a 25 ms gap (PH1-2);
    without times (Siby data) a burst is a run of same-direction records."""
    seq = np.asarray(seq, dtype=np.float64)
    if len(seq) == 0:
        return np.zeros(24)
    if times is not None and len(times) == len(seq):
        gaps = np.diff(times)
        idx = np.flatnonzero(gaps > thr) + 1
    else:
        idx = np.flatnonzero(np.diff(np.sign(seq)) != 0) + 1
    chunks = np.split(seq, idx)
    nb = len(chunks)
    out_b = np.array([c[c > 0].sum() for c in chunks])
    in_b = np.array([-c[c < 0].sum() for c in chunks])
    tot = out_b + in_b
    npk = np.array([len(c) for c in chunks])
    srt = np.sort(tot)
    cum = np.cumsum(srt)
    gini = (nb + 1 - 2 * (cum / cum[-1]).sum()) / nb if cum[-1] > 0 else 0.0
    gravity = (np.arange(nb) * tot).sum() / tot.sum() / max(nb - 1, 1) if tot.sum() > 0 else 0
    pos, neg = seq[seq > 0], -seq[seq < 0]
    f = [nb, len(seq), len(pos), len(neg), pos.sum(), neg.sum(),
         tot.mean(), tot.std(), tot.max(), np.median(tot), npk.mean(), npk.std(), npk.max(),
         out_b.mean(), in_b.mean(), gini, gravity,
         pos.mean() if len(pos) else 0, neg.mean() if len(neg) else 0,
         neg.std() if len(neg) else 0, len(np.unique(neg)), len(np.unique(pos)),
         (times[-1] if times is not None and len(times) else 0),
         (np.median(np.diff(times)) if times is not None and len(times) > 1 else 0)]
    return np.nan_to_num(np.array(f, dtype=np.float64))


# ----------------------------------------------------------------------------- k-FP (subset of Hayes & Danezis features)
def kfp_features(seq, times=None):
    seq = np.asarray(seq, dtype=np.float64)
    if len(seq) == 0:
        return np.zeros(60)
    if times is None or len(times) != len(seq):
        times = np.arange(len(seq), dtype=np.float64) * 0.01  # Siby data: no timestamps
    out, inc = seq > 0, seq < 0
    f = [len(seq), out.sum(), inc.sum(), out.mean(), inc.mean(),
         np.abs(seq[out]).sum(), np.abs(seq[inc]).sum()]
    # ordering statistics
    oi = np.flatnonzero(out); ii = np.flatnonzero(inc)
    for idx in (oi, ii):
        f += [idx.mean() if len(idx) else 0, idx.std() if len(idx) else 0]
    # first / last 30 packets counts
    f += [out[:30].sum(), inc[:30].sum(), out[-30:].sum(), inc[-30:].sum()]
    # concentration of outgoing packets in chunks of 20
    ch = [out[i:i + 20].sum() for i in range(0, len(seq), 20)]
    f += [np.mean(ch), np.std(ch), np.max(ch), np.min(ch), np.median(ch)]
    # bursts (incoming runs)
    b = bursts(np.sign(seq))
    ib = -b[b < 0] if (b < 0).any() else np.array([0.0])
    f += [ib.mean(), ib.std(), ib.max(), len(ib), (ib > 5).sum(), (ib > 10).sum()]
    # timing statistics
    for m in (None, out, inc):
        t = times if m is None else times[m]
        iat = np.diff(t) if len(t) > 1 else np.array([0.0])
        f += [iat.mean(), iat.std(), iat.max(), np.percentile(iat, 75)]
        f += [np.percentile(t, q) if len(t) else 0 for q in (25, 50, 75, 100)]
    # size statistics
    for m in (out, inc):
        s = np.abs(seq[m]) if m.any() else np.array([0.0])
        f += [s.mean(), s.std(), s.max(), s.min(), len(np.unique(s))]
    f = np.array(f, dtype=np.float64)
    return np.nan_to_num(np.pad(f, (0, max(0, 60 - len(f))))[:60])


# ----------------------------------------------------------------------------- CUMUL
def cumul_features(seq, n=100):
    seq = np.asarray(seq, dtype=np.float64)
    if len(seq) == 0:
        return np.zeros(n + 4)
    c = np.cumsum(seq)
    a = np.cumsum(np.abs(seq))
    interp = np.interp(np.linspace(0, a[-1], n), a, c)
    out, inc = seq[seq > 0], -seq[seq < 0]
    return np.concatenate([[len(inc), len(out), inc.sum(), out.sum()], interp])


# ----------------------------------------------------------------------------- F4: padding-aware sizes
def block_index(seq, block):
    seq = np.asarray(seq)
    return np.sign(seq) * np.ceil(np.abs(seq) / block).astype(np.int32)


# ----------------------------------------------------------------------------- F3 / F5: sequences for neural models
def seq_tensor(seqs, times_list=None, L=150, size_scale=500.0):
    """(N, C, L) array: ch0 signed size/size_scale, ch1 log1p(IAT ms) (zeros if no times),
    ch2 direction (+1/-1, 0 = padding)."""
    N = len(seqs)
    C = 3
    X = np.zeros((N, C, L), dtype=np.float32)
    for i, s in enumerate(seqs):
        s = np.asarray(s)[:L]
        X[i, 0, :len(s)] = s / size_scale
        X[i, 2, :len(s)] = np.sign(s)
        if times_list is not None:
            t = np.asarray(times_list[i])[:L]
            if len(t) > 1:
                iat = np.diff(t, prepend=t[0]) * 1000.0
                X[i, 1, :len(t)] = np.log1p(np.clip(iat, 0, None))
    return X


def timing_hist(seq, times, n_slots=20, slot=0.25, n_bins=8):
    """F5: per slot (slot seconds) and direction, histogram of log10 IAT (ms) in n_bins bins."""
    H = np.zeros((2, n_slots, n_bins), dtype=np.float32)
    if times is None:
        return H.ravel()  # size-only data (Siby et al.): no timing available
    seq = np.asarray(seq); times = np.asarray(times)
    if len(times) < 2:
        return H.ravel()
    edges = np.linspace(-2, 4, n_bins + 1)  # 0.01 ms .. 10 s
    for d_i, m in enumerate((seq > 0, seq < 0)):
        t = times[m]
        if len(t) < 2:
            continue
        iat = np.diff(t) * 1000.0
        lg = np.log10(np.clip(iat, 1e-2, 1e4))
        sl = np.minimum((t[1:] / slot).astype(int), n_slots - 1)
        b = np.clip(np.digitize(lg, edges) - 1, 0, n_bins - 1)
        np.add.at(H[d_i], (sl, b), 1)
    return H.ravel()


# ----------------------------------------------------------------------------- memory-light random forest
def _one_tree(X, y, Xte, seed, max_features, sample_weight_base):
    from sklearn.tree import DecisionTreeClassifier
    rng = np.random.RandomState(seed)
    n = X.shape[0]
    w = np.bincount(rng.randint(0, n, n), minlength=n).astype(np.float64)  # bootstrap
    if sample_weight_base is not None:
        w = w * sample_weight_base
    t = DecisionTreeClassifier(max_features=max_features, random_state=seed)
    t.fit(X, y, sample_weight=w)
    p = t.predict_proba(Xte).astype(np.float32)
    imp = t.feature_importances_.astype(np.float32)
    return p, imp


def streaming_forest(Xtr, ytr, Xte, n_trees=100, n_jobs=6, seed=0, max_features="sqrt",
                     return_importance=False):
    """Random forest identical in construction to sklearn's RandomForestClassifier (bootstrap,
    sqrt(features) per split, fully grown trees, probability averaging) but each tree is
    scored on the test set and discarded immediately. Needed because with 1,500 classes a single
    fully grown tree stores ~1 GB of class distributions, i.e. ~100 GB for a 100-tree forest."""
    from joblib import Parallel, delayed
    classes = np.unique(ytr)
    if sp.issparse(Xtr):
        Xtr = Xtr.tocsc().astype(np.float32); Xte = Xte.tocsr().astype(np.float32)
    acc = np.zeros((Xte.shape[0], len(classes)), dtype=np.float32)
    imp = np.zeros(Xtr.shape[1], dtype=np.float64)
    rs = np.random.RandomState(seed).randint(0, 2**31 - 1, n_trees)
    for start in range(0, n_trees, n_jobs):
        outs = Parallel(n_jobs=n_jobs, prefer="threads")(
            delayed(_one_tree)(Xtr, ytr, Xte, int(s), max_features, None) for s in rs[start:start + n_jobs])
        for p, im in outs:
            acc += p; imp += im
        del outs
    acc /= n_trees
    if return_importance:
        return classes, acc, imp / n_trees
    return classes, acc


# ----------------------------------------------------------------------------- metrics & stats
def metrics(y_true, y_pred, proba=None, classes=None):
    from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
    r = dict(acc=accuracy_score(y_true, y_pred),
             precision=precision_score(y_true, y_pred, average="macro", zero_division=0),
             recall=recall_score(y_true, y_pred, average="macro", zero_division=0),
             f1=f1_score(y_true, y_pred, average="macro", zero_division=0))
    if proba is not None and classes is not None:
        top5 = np.argsort(-proba, axis=1)[:, :5]
        cls = np.asarray(classes)
        r["top5"] = float(np.mean([yt in cls[t] for yt, t in zip(y_true, top5)]))
    return r


def mean_ci(vals, conf=0.95):
    from scipy import stats
    v = np.asarray(vals, dtype=float)
    m = v.mean()
    if len(v) < 2:
        return m, 0.0, (m, m)
    se = v.std(ddof=1) / np.sqrt(len(v))
    h = se * stats.t.ppf((1 + conf) / 2, len(v) - 1)
    return m, v.std(ddof=1), (m - h, m + h)


def tost(vals, target, margin=0.03):
    """Two one-sided t-tests: H0 |mean - target| >= margin. Returns p (max of the two)."""
    from scipy import stats
    v = np.asarray(vals, dtype=float)
    n = len(v); se = v.std(ddof=1) / np.sqrt(n)
    if se == 0:
        return 0.0 if abs(v.mean() - target) < margin else 1.0
    t1 = (v.mean() - (target - margin)) / se
    t2 = (v.mean() - (target + margin)) / se
    p1 = 1 - stats.t.cdf(t1, n - 1)
    p2 = stats.t.cdf(t2, n - 1)
    return float(max(p1, p2))


def save_json(obj, name):
    with open(os.path.join(RESULTS, name), "w") as f:
        json.dump(obj, f, indent=2, default=float)
