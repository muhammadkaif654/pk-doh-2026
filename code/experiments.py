"""E2-E5 and ablations on PK-DoH-2026 (and Siby data where shared labels allow).

python experiments.py realism | e2 | e3 | e4 | e5 | ablate | siby_baselines | siby_cross
Results -> results/<name>.json ; figures are produced by figures.py
"""
import json, os, sys, time
import numpy as np
import pandas as pd

import common, models, ours

NET = os.environ.get("NETA", "netA_wifi")
CF, Q9 = f"{NET}_cloudflare", f"{NET}_quad9"
N_REP = int(os.environ.get("N_REP", "10"))


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def save(obj, name):
    common.save_json(obj, name)
    log("saved", name)


# ------------------------------------------------------------------ realism statistics (P10)
def realism():
    out = {}
    for c in (CF, Q9):
        d = ours.load(c)
        L = d.lengths.apply(len); dur = d.times.apply(lambda t: t[-1] if len(t) else 0)
        per = d.assign(L=L).groupby("label").L.agg(["median", "mean", "std"])
        out[c] = dict(n_traces=len(d), n_sites=d.label.nunique(),
                      rounds=int(d["round"].max()) + 1,
                      median_len=float(L.median()), p90_len=float(L.quantile(.9)),
                      median_dur_s=float(dur.median()),
                      per_site_cv_median=float((per["std"] / per["mean"]).median()),
                      share_timeout=float((d.status == "timeout").mean()),
                      challenge_sites=ours.challenge_sites(c),
                      bytes_in_median=float(d.lengths.apply(lambda s: -s[s < 0].sum()).median()),
                      bytes_out_median=float(d.lengths.apply(lambda s: s[s > 0].sum()).median()))
    for name in ("LOC1", "LOC2", "LOC3", "EDNS0-128", "EDNS0-468"):
        df = common.load_siby(name)
        L = df.lengths.apply(len)
        per = df.assign(L=L).groupby("class_label").L.agg(["mean", "std"])
        out["siby_" + name] = dict(n_traces=len(df), median_len=float(L.median()),
                                   p90_len=float(L.quantile(.9)),
                                   per_site_cv_median=float((per["std"] / per["mean"]).median()),
                                   n_pages=int(df.class_label.nunique()),
                                   pages_ge60=int((df.groupby("class_label").size() >= 60).sum()),
                                   per_page_median=int(df.groupby("class_label").size().median()))
    save(out, "realism.json")


# ------------------------------------------------------------------ E2 in-domain, all models
E2_MODELS = ["ngram_rf", "kfp", "cumul", "df", "burst_rf", "timing_rf", "fused_rf", "cnn_se"]


def e2():
    res = {}
    for c in (CF, Q9):
        for curated in (False, True):
            d, n = ours.balanced(ours.load(c, curated=curated))
            key = f"{c}{'_curated' if curated else ''}"
            log(key, len(d), "traces", d.label.nunique(), "sites", n, "per site")
            splits = ours.repeated_splits(d, N_REP)
            res[key] = {"n_per_site": n, "n_sites": int(d.label.nunique())}
            mlist = E2_MODELS if not curated else ["ngram_rf", "fused_rf"]
            for mname in mlist:
                runs = []
                reps = splits if mname not in ("df", "cnn_se", "cumul") else splits[:5]
                for k, (tr, te) in enumerate(reps):
                    m, y, p = ours.evaluate(models.MODELS[mname], d.iloc[tr], d.iloc[te], seed=k)
                    runs.append(m)
                    if k == 0 and mname in ("ngram_rf", "fused_rf") and not curated:
                        f1, ci, per, labs = ours.cluster_bootstrap_ci(y, p)
                        res[key][mname + "_per_site_f1"] = dict(zip(labs.tolist(), per.tolist()))
                        res[key][mname + "_confusion"] = {"y": y.tolist(), "p": p.tolist()}
                res[key][mname] = ours.summarise(runs)
                res[key][mname]["f1_runs"] = [r["f1"] for r in runs]
                log(f"  {mname:10s} F1={res[key][mname]['f1']:.3f}±{res[key][mname]['f1_sd']:.3f} "
                    f"acc={res[key][mname]['acc']:.3f} top5={res[key][mname].get('top5', 0):.3f}")
            save(res, "e2_indomain.json")
    # paired significance: fused vs ngram (Wilcoxon on paired split F1s)
    from scipy.stats import wilcoxon
    for key in list(res):
        r = res[key]
        if "fused_rf" in r and "ngram_rf" in r:
            a, b = r["fused_rf"]["f1_runs"], r["ngram_rf"]["f1_runs"]
            try:
                r["fused_vs_ngram_wilcoxon_p"] = float(wilcoxon(a, b).pvalue)
            except ValueError:
                r["fused_vs_ngram_wilcoxon_p"] = None
    save(res, "e2_indomain.json")


# ------------------------------------------------------------------ E3 transfer matrix
def _transfer(tr, te, model="ngram_rf", seed=0):
    m, y, p = ours.evaluate(models.MODELS[model], tr, te, seed=seed)
    f1, ci, per, labs = ours.cluster_bootstrap_ci(y, p)
    m["f1_cluster_ci"] = ci
    m["per_site_f1"] = dict(zip(labs.tolist(), per.tolist()))
    return m


def e3():
    """Train on X, test on Y over the shared label set. In-domain reference: train/test split of Y."""
    res = {}
    cf = ours.load(CF); q9 = ours.load(Q9)
    glob_ids = sorted(ours.SITES[ours.SITES.group == "global"].site_id)
    shared = sorted(set(cf.label) & set(q9.label))
    cfb, n1 = ours.balanced(cf[cf.label.isin(shared)]); q9b, n2 = ours.balanced(q9[q9.label.isin(shared)])
    n = min(n1, n2)
    shared = sorted(set(cfb.label) & set(q9b.label))
    cfb = common.trim_per_class(cfb[cfb.label.isin(shared)], n, label="label")
    q9b = common.trim_per_class(q9b[q9b.label.isin(shared)], n, label="label")
    datasets = {"PK26-Cloudflare": cfb, "PK26-Quad9": q9b}
    # Siby (2018 Lausanne, 2018 Singapore, 2019 padded-128) on the 50 shared global sites
    gs = [g for g in glob_ids if g in shared]
    for name, key in (("LOC1", "S18-LOC1-Lausanne"), ("LOC3", "S18-LOC3-Singapore"),
                      ("EDNS0-128", "S19-EDNS128-Lausanne")):
        datasets[key] = ours.siby_as_ours(name, gs, n=n)
    for model in ("ngram_rf", "block_rf_468", "burst_rf"):
        mat = {}
        for a, da in datasets.items():
            for b, db in datasets.items():
                common_ids = sorted(set(da.label) & set(db.label))
                da_, db_ = da[da.label.isin(common_ids)], db[db.label.isin(common_ids)]
                if a == b:  # in-domain: 5 repeated 80/20 splits
                    runs = []
                    for k, (tr, te) in enumerate(ours.repeated_splits(da_, 5)):
                        runs.append(_transfer(da_.iloc[tr], da_.iloc[te], model, seed=k))
                    r = ours.summarise(runs); r["f1_cluster_ci"] = runs[0]["f1_cluster_ci"]
                    r["per_site_f1"] = runs[0]["per_site_f1"]
                else:
                    r = _transfer(da_, db_, model)
                r["n_labels"] = len(common_ids)
                mat[f"{a}->{b}"] = r
                log(model, f"{a:22s} -> {b:22s} F1={r['f1']:.3f} ({len(common_ids)} sites)")
        res[model] = mat
        save(res, "e3_transfer.json")


# ------------------------------------------------------------------ E4 recovery curve
def e4(ks=(0, 1, 2, 5, 10)):
    cf = ours.load(CF); q9 = ours.load(Q9)
    shared = sorted(set(cf.label) & set(q9.label))
    cf, n1 = ours.balanced(cf[cf.label.isin(shared)]); q9, n2 = ours.balanced(q9[q9.label.isin(shared)])
    n = min(n1, n2)
    shared = sorted(set(cf.label) & set(q9.label))
    cf = common.trim_per_class(cf[cf.label.isin(shared)], n, label="label")
    q9 = common.trim_per_class(q9[q9.label.isin(shared)], n, label="label")
    gs = sorted(ours.SITES[ours.SITES.group == "global"].site_id)
    gs = [g for g in gs if g in shared]
    s18 = ours.siby_as_ours("LOC1", gs, n=n)
    pairs = {"Quad9->Cloudflare": (q9, cf), "Cloudflare->Quad9": (cf, q9),
             "S18-LOC1->PK26-Cloudflare": (s18, cf[cf.label.isin(gs)])}
    res = {}
    rng = np.random.RandomState(0)
    for pname, (src, tgt) in pairs.items():
        res[pname] = {}
        tgt_test_parts, tgt_pool_parts = [], []
        for lab, g in tgt.groupby("label"):
            idx = rng.permutation(len(g))
            ntest = max(1, len(g) // 2)
            tgt_test_parts.append(g.iloc[idx[:ntest]]); tgt_pool_parts.append(g.iloc[idx[ntest:]])
        tgt_test = pd.concat(tgt_test_parts); pool = pd.concat(tgt_pool_parts)
        kmax = pool.groupby("label").size().min()
        for model in ("ngram_rf", "fused_rf") if "S18" not in pname else ("ngram_rf",):
            curve = []
            for k in ks:
                if k > kmax:
                    continue
                runs = []
                for rep in range(3):
                    add = common.trim_per_class(pool, k, seed=rep, label="label") if k > 0 else pool.iloc[:0]
                    src_ = src[src.label.isin(set(tgt.label))]
                    tr = pd.concat([src_, add]).reset_index(drop=True)
                    m, _, _ = ours.evaluate(models.MODELS[model], tr, tgt_test.reset_index(drop=True), seed=rep)
                    runs.append(m)
                s = ours.summarise(runs); s["k"] = k
                curve.append(s)
                log(pname, model, "k=", k, f"F1={s['f1']:.3f}")
            # target-only reference with the same k (no source data)
            tonly = []
            for k in ks:
                if k == 0 or k > kmax:
                    continue
                add = common.trim_per_class(pool, k, seed=0, label="label")
                m, _, _ = ours.evaluate(models.MODELS[model], add.reset_index(drop=True), tgt_test.reset_index(drop=True))
                tonly.append({"k": k, "f1": m["f1"]})
            res[pname][model] = {"with_source": curve, "target_only": tonly}
        save(res, "e4_recovery.json")


# ------------------------------------------------------------------ E5 padding: features x resolver, simulation
def sim_pad(seq, mode):
    """Simulated padding on observed TLS record sizes. block: round |size| up to multiple of b
    (upper bound on what EDNS(0) block padding at the record level can hide); perfect: all = 825
    as in Siby et al."""
    s = np.asarray(seq)
    if mode == "none":
        return s
    if mode == "perfect":
        return np.sign(s) * 825
    b = int(mode)
    return np.sign(s) * (np.ceil(np.abs(s) / b) * b).astype(np.int32)


def e5():
    res = {"deployed": {}, "simulated": {}}
    for c in (CF, Q9):
        d, n = ours.balanced(ours.load(c))
        splits = ours.repeated_splits(d, 5)
        res["deployed"][c] = {}
        for mname in ("ngram_rf", "block_rf_128", "block_rf_468", "timing_rf", "burst_rf", "fused_rf"):
            runs = [ours.evaluate(models.MODELS[mname], d.iloc[tr], d.iloc[te], seed=k)[0]
                    for k, (tr, te) in enumerate(splits)]
            res["deployed"][c][mname] = ours.summarise(runs)
            log("E5 deployed", c, mname, f"F1={res['deployed'][c][mname]['f1']:.3f}")
        # size histogram of incoming / outgoing records (for the padding figure)
        neg = np.concatenate([-s[s < 0] for s in d.lengths]); pos = np.concatenate([s[s > 0] for s in d.lengths])
        res["deployed"][c]["hist_in"] = dict(zip(*[x.tolist() for x in np.unique(neg, return_counts=True)]))
        res["deployed"][c]["hist_out"] = dict(zip(*[x.tolist() for x in np.unique(pos, return_counts=True)]))
        res["deployed"][c]["bytes_per_trace"] = float(d.lengths.apply(lambda s: np.abs(s).sum()).mean())
    # simulation on the UNPADDED resolver (Quad9): what would padding remove?
    d, n = ours.balanced(ours.load(Q9))
    splits = ours.repeated_splits(d, 5)
    base_bytes = d.lengths.apply(lambda s: np.abs(s).sum()).mean()
    for mode in ("none", "128", "468", "perfect"):
        dd = d.copy(); dd["lengths"] = dd.lengths.apply(lambda s: sim_pad(s, mode))
        overhead = dd.lengths.apply(lambda s: np.abs(s).sum()).mean() / base_bytes - 1
        res["simulated"][mode] = {"overhead": float(overhead)}
        for mname in ("ngram_rf", "fused_rf", "timing_rf"):
            if mname == "timing_rf" and mode != "none":
                continue  # timing is unaffected by size padding (identical by construction)
            runs = [ours.evaluate(models.MODELS[mname], dd.iloc[tr], dd.iloc[te], seed=k)[0]
                    for k, (tr, te) in enumerate(splits)]
            res["simulated"][mode][mname] = ours.summarise(runs)
            log("E5 simulated", mode, mname, f"F1={res['simulated'][mode][mname]['f1']:.3f}",
                f"overhead={overhead:.2%}")
    save(res, "e5_padding.json")


# ------------------------------------------------------------------ Ablations (Step 10)
def ablate():
    res = {}
    conds = [x for x in (CF, Q9) if os.environ.get("ONLY", "") in x]
    for c in conds:
        d, n = ours.balanced(ours.load(c))
        splits = ours.repeated_splits(d, 5)
        R = res[c] = {}

        def run(fn, data=d, sp_=splits):
            runs = [ours.evaluate(fn, data.iloc[tr], data.iloc[te], seed=k)[0] for k, (tr, te) in enumerate(sp_)]
            return ours.summarise(runs)

        # A1 feature groups
        R["features"] = {} if os.environ.get("SKIP_A12") else {
            "sizes_uni": run(lambda tr, te, seed=0: models.ngram_rf(tr, te, 1, True, False, seed)),
            "sizes_uni_bi": run(lambda tr, te, seed=0: models.ngram_rf(tr, te, 2, True, False, seed)),
            "bursts_uni_bi": run(lambda tr, te, seed=0: models.ngram_rf(tr, te, 2, False, True, seed)),
            "ngrams_full(F1)": run(models.ngram_rf),
            "ngrams_tri": run(lambda tr, te, seed=0: models.ngram_rf(tr, te, 3, True, True, seed)),
            "F1+F2": run(lambda tr, te, seed=0: models.fused_rf(tr, te, seed, True, True, False)),
            "F1+F5": run(lambda tr, te, seed=0: models.fused_rf(tr, te, seed, True, False, True)),
            "F1+F2+F5(fused)": run(models.fused_rf),
            "F2+F5(no sizes n-grams)": run(lambda tr, te, seed=0: models.fused_rf(tr, te, seed, False, True, True)),
        }
        log(c, "A1", {k: round(float(v["f1"]), 3) for k, v in R["features"].items()})
        # A2 trace prefix (records needed)
        R["prefix"] = {}
        for L in (() if os.environ.get("SKIP_A12") else (5, 10, 20, 50, 100, 200, 300, 0)):
            dd = d.copy()
            if L:
                dd["lengths"] = dd.lengths.apply(lambda s: s[:L]); dd["times"] = dd.times.apply(lambda t: t[:L])
            R["prefix"][str(L or "full")] = {"ngram_rf": run(models.ngram_rf, dd), "fused_rf": run(models.fused_rf, dd)}
        log(c, "A2", {k: round(float(v["ngram_rf"]["f1"]), 3) for k, v in R["prefix"].items()})
        # A3 training budget (traces per site), fixed test set of 4 traces per site
        R["budget_traces"] = {}
        rng = np.random.RandomState(0)
        test_idx, pool_idx = [], []
        n_test = max(1, min(4, n // 3))
        for lab, g in d.groupby("label"):
            p = rng.permutation(g.index.values); test_idx += list(p[:n_test]); pool_idx += list(p[n_test:])
        te_d = d.loc[test_idx]; pool = d.loc[pool_idx]
        for k in (1, 2, 5, 10, 15, 20, 25):
            if pool.empty or pool.label.nunique() < d.label.nunique() or k > pool.groupby("label").size().min():
                continue
            runs = []
            for rep in range(3):
                tr_d = common.trim_per_class(pool, k, seed=rep, label="label")
                runs.append(ours.evaluate(models.ngram_rf, tr_d, te_d, seed=rep)[0])
            R["budget_traces"][str(k)] = ours.summarise(runs)
        log(c, "A3", {k: round(v["f1"], 3) for k, v in R["budget_traces"].items()})
        # A4 number of sites (closed-world size)
        R["budget_sites"] = {}
        labs = np.array(sorted(d.label.unique()))
        for ns in (10, 25, 50, 75, len(labs)):
            runs = []
            for rep in range(3):
                pick = np.random.RandomState(rep).choice(labs, ns, replace=False)
                dd = d[d.label.isin(pick)].reset_index(drop=True)
                tr, te = ours.repeated_splits(dd, 1, seed=rep)[0]
                runs.append(ours.evaluate(models.ngram_rf, dd.iloc[tr], dd.iloc[te], seed=rep)[0])
            R["budget_sites"][str(ns)] = ours.summarise(runs)
        log(c, "A4", {k: round(v["f1"], 3) for k, v in R["budget_sites"].items()})
        # A5 label composition: global-only vs Pakistani-only
        R["composition"] = {}
        for grp in ("global", "pk"):
            ids = set(ours.SITES[ours.SITES.group == grp].site_id)
            dd = d[d.label.isin(ids)].reset_index(drop=True)
            R["composition"][grp] = run(models.ngram_rf, dd, ours.repeated_splits(dd, 5))
        log(c, "A5", {k: round(v["f1"], 3) for k, v in R["composition"].items()})
        # A6 curation
        dc, _ = ours.balanced(ours.load(c, curated=True))
        R["curation"] = {"full": run(models.ngram_rf), "curated": run(models.ngram_rf, dc, ours.repeated_splits(dc, 5))}
        # A7 CNN attention block
        R["cnn"] = {"cnn_se": run(models.MODELS["cnn_se"], d, splits[:3]),
                    "cnn_nose": run(models.MODELS["cnn_nose"], d, splits[:3]),
                    "cnn_se_no_timing": run(lambda tr, te, seed=0: models.cnn(tr, te, use_timing=False, seed=seed), d, splits[:3])}
        log(c, "A7", {k: round(v["f1"], 3) for k, v in R["cnn"].items()})
        save(res, "ablations.json")


# ------------------------------------------------------------------ Siby-side baselines (Table III analogue)
def siby_baselines(n_classes=100, n=60):
    df = common.load_siby("LOC1")
    rng = np.random.RandomState(1)
    cl = sorted(rng.choice(sorted(df.class_label.unique()), n_classes, replace=False))
    d = common.trim_per_class(df, n, classes=cl, label="class_label")
    d["label"] = d.class_label; d["times"] = None
    splits = ours.repeated_splits(d, 3)
    res = {"n_classes": n_classes, "n_per_class": n}
    for mname in ("ngram_rf", "kfp", "cumul", "burst_rf", "fused_rf", "df", "cnn_se", "cnn_nose"):
        sp_ = splits if mname not in ("df", "cnn_se", "cnn_nose") else splits[:2]
        runs = [ours.evaluate(models.MODELS[mname], d.iloc[tr], d.iloc[te], seed=k)[0]
                for k, (tr, te) in enumerate(sp_)]
        res[mname] = ours.summarise(runs)
        log("Siby baselines", mname, f"F1={res[mname]['f1']:.3f}")
        save(res, "siby_baselines.json")


# ------------------------------------------------------------------ Siby cross-location (Table VI row)
def siby_cross(n_classes=300, n=60):
    rng = np.random.RandomState(1)
    loc = {k: common.load_siby(k) for k in ("LOC1", "LOC2", "LOC3")}
    cl = sorted(rng.choice(sorted(loc["LOC1"].class_label.unique()), n_classes, replace=False))
    ds = {}
    for k, df in loc.items():
        d = common.trim_per_class(df, n, classes=cl, label="class_label")
        d["label"] = d.class_label; d["times"] = None
        ds[k] = d
    res = {"n_classes": n_classes}
    for a in ds:
        for b in ds:
            if a == b:
                runs = [ours.evaluate(models.ngram_rf, ds[a].iloc[tr], ds[a].iloc[te], seed=k)[0]
                        for k, (tr, te) in enumerate(ours.repeated_splits(ds[a], 3))]
                r = ours.summarise(runs)
            else:
                r = ours.evaluate(models.ngram_rf, ds[a], ds[b])[0]
            res[f"{a}->{b}"] = r
            log("Siby cross", a, b, f"F1={r['f1']:.3f}")
            save(res, "siby_cross.json")
    save(res, "siby_cross.json")


if __name__ == "__main__":
    common.low_priority()
    for name in sys.argv[1:]:
        globals()[name]()
