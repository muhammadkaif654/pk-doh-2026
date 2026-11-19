"""Classifiers used in Phase 3. Every model exposes fit_predict(train_df, test_df) -> (classes, proba).

Data frames carry columns: label, lengths (np.int array, signed), times (np.float array or None).

  ngram_rf      B1 / primary  - Siby et al. n-grams (uni+bi, sizes+bursts) + RF(100)
  kfp           B2            - k-fingerprinting features + RF(100)          (Hayes & Danezis 2016)
  cumul         B3            - CUMUL features + RBF-SVM                      (Panchenko et al. 2016)
  df            B4            - Deep Fingerprinting CNN on direction sequence (Sirinam et al. 2018)
  burst_rf      B5            - burst statistics + RF(200, balanced)          (Moure-Garrido et al. 2026)
  timing_rf     F5 only       - timing histograms (no sizes) + RF(100)
  block_rf      F4            - n-grams over 128/468-byte block indices + RF(100)
  fused_rf      PROPOSED      - F1 n-grams + F2 burst stats + F5 timing histograms + RF(100)
  cnn_se        PROPOSED      - 1D-CNN with squeeze-excitation on (size, log-IAT) sequence
  cnn_nose      ablation      - same CNN without the SE block
"""
import numpy as np
import scipy.sparse as sp
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

import common

N_JOBS = 6


def _labels(df):
    return df["label"].values


def _times(df):
    return list(df["times"]) if "times" in df and df["times"].iloc[0] is not None else [None] * len(df)


def _rf(Xtr, ytr, Xte, n=100, balanced=False, seed=0):
    rf = RandomForestClassifier(n_estimators=n, n_jobs=N_JOBS, random_state=seed,
                                class_weight="balanced" if balanced else None)
    rf.fit(Xtr, ytr)
    return rf.classes_, rf.predict_proba(Xte), rf


# --------------------------------------------------------------------------- feature builders
def ngram_rf(tr, te, n=2, use_sizes=True, use_bursts=True, seed=0, transform=None, return_model=False):
    f = transform or (lambda s: s)
    fx = common.NgramFeatures(n, use_sizes, use_bursts)
    Xtr = fx.fit_transform([f(s) for s in tr["lengths"]])
    Xte = fx.transform([f(s) for s in te["lengths"]])
    c, p, rf = _rf(Xtr, _labels(tr), Xte, seed=seed)
    if return_model:
        vocab = (list(fx.v_size.get_feature_names_out()) if use_sizes else []) + \
                (["B:" + x for x in fx.v_burst.get_feature_names_out()] if use_bursts else [])
        return c, p, rf, vocab
    return c, p


def block_rf(tr, te, block=468, seed=0):
    return ngram_rf(tr, te, seed=seed, transform=lambda s: common.block_index(s, block))


def kfp(tr, te, seed=0):
    Xtr = np.array([common.kfp_features(s, t) for s, t in zip(tr["lengths"], _times(tr))])
    Xte = np.array([common.kfp_features(s, t) for s, t in zip(te["lengths"], _times(te))])
    c, p, _ = _rf(Xtr, _labels(tr), Xte, seed=seed)
    return c, p


def cumul(tr, te, seed=0):
    Xtr = np.array([common.cumul_features(s) for s in tr["lengths"]])
    Xte = np.array([common.cumul_features(s) for s in te["lengths"]])
    sc = StandardScaler().fit(Xtr)
    svm = SVC(C=1000, gamma="scale", probability=True, random_state=seed)
    svm.fit(sc.transform(Xtr), _labels(tr))
    return svm.classes_, svm.predict_proba(sc.transform(Xte))


def burst_rf(tr, te, seed=0):
    Xtr = np.array([common.burst_stats(s, t) for s, t in zip(tr["lengths"], _times(tr))])
    Xte = np.array([common.burst_stats(s, t) for s, t in zip(te["lengths"], _times(te))])
    c, p, _ = _rf(Xtr, _labels(tr), Xte, n=200, balanced=True, seed=seed)
    return c, p


def timing_rf(tr, te, seed=0):
    Xtr = np.array([common.timing_hist(s, t) for s, t in zip(tr["lengths"], _times(tr))])
    Xte = np.array([common.timing_hist(s, t) for s, t in zip(te["lengths"], _times(te))])
    c, p, _ = _rf(Xtr, _labels(tr), Xte, seed=seed)
    return c, p


def fused_rf(tr, te, seed=0, use_ngrams=True, use_bursts=True, use_timing=True, return_model=False):
    parts_tr, parts_te = [], []
    if use_ngrams:
        fx = common.NgramFeatures(2)
        parts_tr.append(fx.fit_transform(list(tr["lengths"])))
        parts_te.append(fx.transform(list(te["lengths"])))
    if use_bursts:
        parts_tr.append(sp.csr_matrix(np.array([common.burst_stats(s, t) for s, t in zip(tr["lengths"], _times(tr))])))
        parts_te.append(sp.csr_matrix(np.array([common.burst_stats(s, t) for s, t in zip(te["lengths"], _times(te))])))
    if use_timing:
        parts_tr.append(sp.csr_matrix(np.array([common.timing_hist(s, t) for s, t in zip(tr["lengths"], _times(tr))])))
        parts_te.append(sp.csr_matrix(np.array([common.timing_hist(s, t) for s, t in zip(te["lengths"], _times(te))])))
    Xtr = sp.hstack(parts_tr).tocsr(); Xte = sp.hstack(parts_te).tocsr()
    c, p, rf = _rf(Xtr, _labels(tr), Xte, seed=seed)
    return (c, p, rf) if return_model else (c, p)


# --------------------------------------------------------------------------- neural models (torch, CPU)
def _torch():
    import torch
    torch.set_num_threads(4)
    return torch


def _build_cnn(in_ch, n_cls, se=True, df_style=False):
    torch = _torch()
    nn = torch.nn

    class SE(nn.Module):
        def __init__(self, c, r=8):
            super().__init__()
            self.fc = nn.Sequential(nn.Linear(c, c // r), nn.ReLU(), nn.Linear(c // r, c), nn.Sigmoid())

        def forward(self, x):
            w = self.fc(x.mean(-1))
            return x * w.unsqueeze(-1)

    def block(ci, co, k, act):
        layers = [nn.Conv1d(ci, co, k, padding=k // 2), nn.BatchNorm1d(co), act(),
                  nn.Conv1d(co, co, k, padding=k // 2), nn.BatchNorm1d(co), act()]
        if se and not df_style:
            layers.append(SE(co))
        layers += [nn.MaxPool1d(2), nn.Dropout(0.1)]
        return nn.Sequential(*layers)

    act = nn.ELU if df_style else nn.ReLU
    chans = [32, 64, 128] if df_style else [32, 64, 128]
    ks = 8 if df_style else 5
    blocks, ci = [], in_ch
    for co in chans:
        blocks.append(block(ci, co, ks, act)); ci = co

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.f = nn.Sequential(*blocks)
            self.h = nn.Sequential(nn.AdaptiveAvgPool1d(1), nn.Flatten(), nn.Linear(ci, 256), nn.ReLU(),
                                   nn.Dropout(0.3), nn.Linear(256, n_cls))

        def forward(self, x):
            return self.h(self.f(x))

    return Net()


def _train_net(Xtr, ytr, Xte, n_cls, se=True, df_style=False, epochs=40, seed=0, lr=2e-3):
    torch = _torch()
    torch.manual_seed(seed); np.random.seed(seed)
    net = _build_cnn(Xtr.shape[1], n_cls, se=se, df_style=df_style)
    # validation split from TRAINING data only, for early stopping
    rng = np.random.RandomState(seed)
    idx = rng.permutation(len(ytr)); nv = max(1, int(0.1 * len(ytr)))
    vi, ti = idx[:nv], idx[nv:]
    Xt, yt = torch.tensor(Xtr[ti]), torch.tensor(ytr[ti])
    Xv, yv = torch.tensor(Xtr[vi]), torch.tensor(ytr[vi])
    opt = torch.optim.AdamW(net.parameters(), lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs)
    lossf = torch.nn.CrossEntropyLoss(label_smoothing=0.05)
    best, best_state, patience = -1, None, 0
    for ep in range(epochs):
        net.train()
        perm = torch.randperm(len(yt))
        for b in range(0, len(yt), 128):
            j = perm[b:b + 128]
            xb = Xt[j]
            # light augmentation: random shift of up to 3 positions
            if not df_style:
                xb = torch.roll(xb, int(rng.randint(-3, 4)), dims=-1)
            opt.zero_grad(); loss = lossf(net(xb), yt[j]); loss.backward(); opt.step()
        sched.step()
        net.eval()
        with torch.no_grad():
            acc = (net(Xv).argmax(1) == yv).float().mean().item()
        if acc > best:
            best, patience = acc, 0
            best_state = {k: v.clone() for k, v in net.state_dict().items()}
        else:
            patience += 1
            if patience >= 10 and ep >= 20:
                break
    net.load_state_dict(best_state)
    net.eval()
    with torch.no_grad():
        p = torch.softmax(net(torch.tensor(Xte)), 1).numpy()
    return p


def _encode(tr, te):
    classes = np.unique(tr["label"].values)
    m = {c: i for i, c in enumerate(classes)}
    return classes, np.array([m[c] for c in tr["label"].values], dtype=np.int64)


def cnn(tr, te, se=True, L=200, use_timing=True, seed=0):
    classes, ytr = _encode(tr, te)
    tt = _times(tr) if use_timing else None
    te_t = _times(te) if use_timing else None
    Xtr = common.seq_tensor(list(tr["lengths"]), tt if (tt and tt[0] is not None) else None, L=L)
    Xte = common.seq_tensor(list(te["lengths"]), te_t if (te_t and te_t[0] is not None) else None, L=L)
    p = _train_net(Xtr, ytr, Xte, len(classes), se=se, seed=seed)
    return classes, p


def df_model(tr, te, L=200, seed=0):
    """Deep Fingerprinting: direction-only (+1/-1) sequence, ELU conv blocks."""
    classes, ytr = _encode(tr, te)
    def enc(seqs):
        X = np.zeros((len(seqs), 1, L), dtype=np.float32)
        for i, s in enumerate(seqs):
            s = np.sign(np.asarray(s)[:L]); X[i, 0, :len(s)] = s
        return X
    p = _train_net(enc(list(tr["lengths"])), ytr, enc(list(te["lengths"])), len(classes),
                   se=False, df_style=True, seed=seed, lr=1e-3)
    return classes, p


MODELS = {
    "ngram_rf": ngram_rf, "kfp": kfp, "cumul": cumul, "df": df_model, "burst_rf": burst_rf,
    "timing_rf": timing_rf, "block_rf_468": lambda tr, te, seed=0: block_rf(tr, te, 468, seed),
    "block_rf_128": lambda tr, te, seed=0: block_rf(tr, te, 128, seed),
    "fused_rf": fused_rf, "cnn_se": cnn,
    "cnn_nose": lambda tr, te, seed=0: cnn(tr, te, se=False, seed=seed),
}
