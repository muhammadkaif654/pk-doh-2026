"""All Phase 3 figures, regenerated from results/*.json (python figures.py)."""
import glob, json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

import common

R, F = common.RESULTS, common.FIGS
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.dpi": 300, "savefig.bbox": "tight"})
BLUE, ORANGE, GREEN, RED, GREY, PURPLE = "#2f6db5", "#e07b28", "#3a9a5b", "#c8443a", "#8a8a8a", "#7a4fb0"
NICE = {"ngram_rf": "n-grams RF (Siby; B1)", "kfp": "k-FP (B2)", "cumul": "CUMUL (B3)", "df": "DF CNN (B4)",
        "burst_rf": "Burst-stats RF (B5)", "timing_rf": "Timing only (F5)", "fused_rf": "Fused RF (proposed)",
        "cnn_se": "1D-CNN + SE (proposed)", "block_rf_468": "Block-468 n-grams (F4)",
        "block_rf_128": "Block-128 n-grams (F4)"}


def J(name):
    p = os.path.join(R, name)
    return json.load(open(p)) if os.path.exists(p) else None


def save(fig, name):
    fig.savefig(os.path.join(F, name)); plt.close(fig); print("figure", name)


def fig_reproduction():
    rows = []
    for f in sorted(glob.glob(os.path.join(R, "e1", "*_summary.json"))):
        s = json.load(open(f))
        if s.get("paper_f1") is None:
            continue
        rows.append(s)
    if not rows:
        return
    order = ["LOC1", "LOC1_exact", "LOC1_uni", "LOC2", "LOC3", "EDNS0-128-700", "EDNS0-468-700", "PERFECT-700", "PERFECT-nodir-700"]
    rows = sorted([r for r in rows if r["exp"] in order], key=lambda s: order.index(s["exp"]))
    lab = {"LOC1": "LOC1\n(uni+bi)", "LOC1_exact": "LOC1\nall n-grams", "LOC1_uni": "LOC1\nuni only\n(released code)",
           "LOC2": "LOC2", "LOC3": "LOC3", "EDNS0-128-700": "EDNS0\n128", "EDNS0-468-700": "EDNS0\n468", "PERFECT-700": "Perfect\n(direction\nkept)",
           "PERFECT-nodir-700": "Perfect\n(direction\ndropped)"}
    x = np.arange(len(rows)); w = 0.38
    fig, ax = plt.subplots(figsize=(7.6, 3.1))
    ax.bar(x - w / 2, [r["paper_f1"] for r in rows], w, color=GREY, label="Siby et al. 2020 (published)")
    ours = [r["f1"] for r in rows]
    err = np.array([[r["f1"] - r["f1_ci"][0], r["f1_ci"][1] - r["f1"]] for r in rows]).T
    ax.bar(x + w / 2, ours, w, color=BLUE, label="Our reproduction (95% CI)", yerr=err, capsize=2)
    for xi, r in zip(x, rows):
        ax.text(xi + w / 2, r["f1_ci"][1] + 0.02, f"{r['delta_f1']:+.3f}", ha="center", fontsize=6.5)
    ax.set_xticks(x); ax.set_xticklabels([lab.get(r["exp"], r["exp"]) for r in rows], fontsize=7.5)
    ax.set_ylabel("Macro F1"); ax.set_ylim(0, 1.08); ax.legend(frameon=False, fontsize=7, loc="upper right")
    ax.set_title("E1 / RQ1: reproduction of the 2020 attack on the released data (labels: ΔF1)", fontsize=9)
    save(fig, "fig2_reproduction.png")


def fig_padding_audit():
    p = os.path.join(R, "padding_audit", "padding_audit_raw.csv")
    if not os.path.exists(p):
        return
    d = pd.read_csv(p)
    d = d[d.error.isna() & (d.proto == "DoH")]
    res = [r for r in ["Cloudflare", "Google", "Quad9", "AdGuard", "OpenDNS", "NextDNS", "CleanBrowsing",
                       "DNS.SB", "ControlD", "AliDNS"] if r in set(d.resolver)]
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.2), sharey=True)
    for ax, cp, title in zip(axes, (0, 1), ("Client sends no padding", "Client pads query to 128 B")):
        for i, r in enumerate(res):
            v = d[(d.resolver == r) & (d.client_pad == cp)].resp_len.values
            jitter = np.random.RandomState(i).uniform(-0.18, 0.18, len(v))
            ax.scatter(v, i + jitter, s=9, color=BLUE if (v % 468 == 0).all() else ORANGE if (d[(d.resolver == r) & (d.client_pad == cp)].resp_has_pad == 1).any() else GREY, alpha=0.8)
        for b in range(468, 3000, 468):
            ax.axvline(b, color=RED, lw=0.6, ls="--", alpha=0.6)
        ax.set_title(title, fontsize=9); ax.set_xlabel("DNS response size (bytes, decrypted)")
        ax.set_yticks(range(len(res))); ax.set_yticklabels(res)
    fig.suptitle("Track C: active EDNS(0) padding audit over DoH (blue = all on 468-B blocks, "
                 "orange = padded, non-standard, grey = unpadded;\nred dashed lines = multiples of 468 bytes, RFC 8467)", fontsize=8.5, y=1.07)
    save(fig, "fig3_padding_audit.png")


def fig_wire_hist():
    e5 = J("e5_padding.json")
    if not e5:
        return
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 2.8), sharey=False)
    for ax, (c, col) in zip(axes, [(k, BLUE if "cloudflare" in k else ORANGE) for k in e5["deployed"]]):
        h = e5["deployed"][c]["hist_in"]
        xs = np.array(list(map(int, h.keys()))); ys = np.array(list(h.values()))
        m = xs <= 1200
        ax.bar(xs[m], ys[m] / ys.sum(), width=4, color=col)
        ax.set_yscale("log"); ax.set_xlabel("Incoming TLS record size on the wire (bytes)")
        ax.set_title(c.replace("netA_wifi_", "PK-2026 ").replace("cloudflare", "Cloudflare (pads)").replace("quad9", "Quad9 (no padding)"), fontsize=9)
        top = xs[np.argsort(-ys)][:3]
        ax.text(0.98, 0.95, "most common: " + ", ".join(map(str, top)), transform=ax.transAxes, ha="right", va="top", fontsize=7)
    axes[0].set_ylabel("Share of records (log)")
    fig.suptitle("Passive view: resolver-to-client record sizes in our captures", fontsize=9)
    save(fig, "fig4_wire_histograms.png")


def fig_e2():
    e2 = J("e2_indomain.json")
    if not e2:
        return
    keys = [k for k in e2 if not k.endswith("_curated")]
    mlist = ["ngram_rf", "kfp", "cumul", "df", "burst_rf", "timing_rf", "cnn_se", "fused_rf"]
    fig, ax = plt.subplots(figsize=(7.4, 3.1))
    w = 0.38; x = np.arange(len(mlist))
    for i, (k, col) in enumerate(zip(keys, (BLUE, ORANGE))):
        vals = [e2[k][m]["f1"] if m in e2[k] else np.nan for m in mlist]
        err = np.array([[e2[k][m]["f1"] - e2[k][m]["f1_ci"][0], e2[k][m]["f1_ci"][1] - e2[k][m]["f1"]]
                        if m in e2[k] else [0, 0] for m in mlist]).T
        lab = "Cloudflare (padded responses)" if "cloudflare" in k else "Quad9 (unpadded)"
        ax.bar(x + (i - 0.5) * w, vals, w, color=col, yerr=err, capsize=2, label=lab)
        for xi, v, hi in zip(x, vals, err[1]):
            ax.text(xi + (i - 0.5) * w, v + hi + 0.015, f"{v:.2f}", ha="center", fontsize=6)
    ax.axhline(0.01, color=GREY, ls=":", lw=0.8); ax.text(7.55, 0.03, "chance = 0.01", fontsize=6.5, ha="right", color=GREY)
    ax.set_xticks(x); ax.set_xticklabels([NICE[m].replace(" (", "\n(") for m in mlist], fontsize=7)
    ax.set_ylabel("Macro F1 (mean, 95% CI)"); ax.set_ylim(0, 1.1); ax.legend(frameon=False, fontsize=7.5, ncol=2, loc="upper left")
    ax.set_title("E2: baselines vs proposed on PK-DoH-2026 (100 sites, closed world)", fontsize=9)
    save(fig, "fig5_baselines.png")


def fig_e3():
    e3 = J("e3_transfer.json")
    if not e3:
        return
    for model, fname in (("ngram_rf", "fig6_transfer_matrix.png"),):
        mat = e3[model]
        names = []
        for k in mat:
            a, b = k.split("->")
            for n in (a, b):
                if n not in names:
                    names.append(n)
        M = np.full((len(names), len(names)), np.nan)
        for k, v in mat.items():
            a, b = k.split("->"); M[names.index(a), names.index(b)] = v["f1"]
        fig, ax = plt.subplots(figsize=(5.6, 4.4))
        im = ax.imshow(M, cmap="Blues", vmin=0, vmax=1)
        for i in range(len(names)):
            for j in range(len(names)):
                v = mat.get(f"{names[i]}->{names[j]}")
                if v:
                    ci = v.get("f1_cluster_ci")
                    txt = f"{v['f1']:.2f}" + (f"\n[{ci[0]:.2f},{ci[1]:.2f}]" if ci else "")
                    ax.text(j, i, txt, ha="center", va="center", fontsize=6.5, color="white" if v["f1"] > 0.55 else "black")
        lab = [n.replace("-", "\n", 1) for n in names]
        ax.set_xticks(range(len(names))); ax.set_xticklabels(lab, fontsize=7, rotation=30, ha="right")
        ax.set_yticks(range(len(names))); ax.set_yticklabels(lab, fontsize=7)
        ax.set_xlabel("Test on"); ax.set_ylabel("Train on")
        fig.colorbar(im, ax=ax, fraction=0.04, label="Macro F1")
        ax.set_title("E3 / RQ2: transfer matrix (n-grams RF, shared labels,\nsite-clustered bootstrap 95% CI)", fontsize=9)
        save(fig, fname)


def fig_e4():
    e4 = J("e4_recovery.json")
    if not e4:
        return
    fig, ax = plt.subplots(figsize=(7.4, 3.0))
    cols = [BLUE, ORANGE, GREEN, PURPLE, RED]
    i = 0
    for pair, d in e4.items():
        for model, r in d.items():
            ks = [c["k"] for c in r["with_source"]]; f = [c["f1"] for c in r["with_source"]]
            ax.plot(ks, f, "-o", ms=3, color=cols[i % 5], label=f"{pair} [{NICE[model].split(' (')[0]}]")
            if r["target_only"]:
                ax.plot([c["k"] for c in r["target_only"]], [c["f1"] for c in r["target_only"]], ":", color=cols[i % 5], lw=1)
            i += 1
    ax.set_xlabel("Target-domain traces per site added to training (k)"); ax.set_ylabel("Macro F1 on held-out target")
    ax.set_ylim(0, 1); ax.legend(frameon=False, fontsize=6.5, loc="center left", bbox_to_anchor=(1.01, 0.5))
    ax.set_title("E4: recovery curves (solid: source + k target traces; dotted: k target traces only)", fontsize=8.5)
    save(fig, "fig7_recovery.png")


def fig_e5():
    e5 = J("e5_padding.json")
    if not e5:
        return
    fig, axes = plt.subplots(1, 2, figsize=(8.0, 3.1))
    ax = axes[0]
    ms = ["ngram_rf", "block_rf_128", "block_rf_468", "burst_rf", "timing_rf", "fused_rf"]
    x = np.arange(len(ms)); w = 0.38
    for i, (c, col) in enumerate(zip(e5["deployed"], (BLUE, ORANGE))):
        v = [e5["deployed"][c][m]["f1"] for m in ms]
        ax.bar(x + (i - .5) * w, v, w, color=col, label="Cloudflare (pads)" if "cloud" in c else "Quad9 (no pad)")
    ax.set_xticks(x); ax.set_xticklabels(["n-grams", "Block\n128", "Block\n468", "Burst\nstats", "Timing\nonly", "Fused"], fontsize=6.5)
    ax.set_ylim(0, 1.05); ax.set_ylabel("Macro F1"); ax.legend(frameon=False, fontsize=7); ax.set_title("Deployed padding x feature family", fontsize=8.5)
    ax = axes[1]
    modes = ["none", "128", "468", "perfect"]
    ov = [e5["simulated"][m]["overhead"] * 100 for m in modes]
    for m_, col, lab in (("ngram_rf", BLUE, "size n-grams"), ("fused_rf", GREEN, "fused (sizes+bursts+timing)")):
        ax.plot(ov, [e5["simulated"][m][m_]["f1"] for m in modes], "-o", color=col, ms=4, label=lab)
    t = e5["simulated"]["none"]["timing_rf"]["f1"]
    ax.axhline(t, color=PURPLE, ls="--", lw=1, label=f"timing only = {t:.2f}")
    for o, m in zip(ov, modes):
        ax.annotate(m if m != "none" else "no pad", (o, e5["simulated"][m]["ngram_rf"]["f1"]), fontsize=7,
                    xytext=(3, 4), textcoords="offset points")
    ax.set_xlabel("Byte overhead vs unpadded (%)"); ax.set_ylabel("Macro F1"); ax.set_ylim(0, 1.05)
    ax.legend(frameon=False, fontsize=7); ax.set_title("Simulated padding on Quad9 traces", fontsize=8.5)
    fig.suptitle("E5 / RQ3: what padding removes, and what survives it", fontsize=9)
    save(fig, "fig8_padding_effect.png")


def fig_ablations():
    ab = J("ablations.json")
    if not ab:
        return
    conds = list(ab)
    # A1 features
    fig, ax = plt.subplots(figsize=(8.0, 3.1))
    feats = list(ab[conds[0]]["features"])
    x = np.arange(len(feats)); w = 0.38
    for i, (c, col) in enumerate(zip(conds, (BLUE, ORANGE))):
        ax.bar(x + (i - .5) * w, [ab[c]["features"][f]["f1"] for f in feats], w, color=col,
               label="Cloudflare (pads)" if "cloud" in c else "Quad9 (no pad)")
    FL = {"sizes_uni": "sizes\nuni", "sizes_uni_bi": "sizes\nuni+bi", "bursts_uni_bi": "bursts\nuni+bi",
          "ngrams_full(F1)": "F1\n(all n-grams)", "ngrams_tri": "F1 +\ntri-grams", "F1+F2": "F1+F2", "F1+F5": "F1+F5",
          "F1+F2+F5(fused)": "F1+F2+F5\n(fused)", "F2+F5(no sizes n-grams)": "F2+F5\n(no size\nn-grams)"}
    ax.set_xticks(x); ax.set_xticklabels([FL.get(f, f) for f in feats], fontsize=6.5)
    ax.set_ylim(0, 1.18); ax.set_yticks(np.arange(0, 1.01, 0.2)); ax.set_ylabel("Macro F1")
    ax.legend(frameon=False, fontsize=7, ncol=2, loc="upper center", bbox_to_anchor=(0.5, 1.0))
    ax.set_title("Ablation A1: feature groups (remove / add components)", fontsize=9)
    save(fig, "fig9_ablation_features.png")
    # A2-A4 curves
    fig, axes = plt.subplots(1, 3, figsize=(7.6, 2.6))
    for c, col in zip(conds, (BLUE, ORANGE)):
        lab = "Cloudflare" if "cloud" in c else "Quad9"
        pr = ab[c]["prefix"]; ks = [k for k in pr if k != "full"]
        axes[0].plot([int(k) for k in ks], [pr[k]["ngram_rf"]["f1"] for k in ks], "-o", ms=3, color=col, label=lab + " n-grams")
        axes[0].plot([int(k) for k in ks], [pr[k]["fused_rf"]["f1"] for k in ks], "--s", ms=3, color=col, label=lab + " fused")
        bt = ab[c]["budget_traces"]
        axes[1].plot([int(k) for k in bt], [bt[k]["f1"] for k in bt], "-o", ms=3, color=col, label=lab)
        bs = ab[c]["budget_sites"]
        axes[2].plot([int(k) for k in bs], [bs[k]["f1"] for k in bs], "-o", ms=3, color=col, label=lab)
    axes[0].set_xscale("log"); axes[0].set_xlabel("First N TLS records"); axes[0].set_ylabel("Macro F1")
    axes[1].set_xlabel("Training traces per site"); axes[2].set_xlabel("Number of sites (closed world)")
    for a, t in zip(axes, ("A2: trace prefix", "A3: training budget", "A4: world size")):
        a.set_ylim(0, 1.02); a.set_title(t, fontsize=8.5)
    axes[0].legend(frameon=False, fontsize=5.8); axes[1].legend(frameon=False, fontsize=6.5)
    save(fig, "fig10_ablation_curves.png")


def fig_cdf():
    e2 = J("e2_indomain.json")
    if not e2:
        return
    fig, ax = plt.subplots(figsize=(4.6, 2.8))
    for k, col in zip([k for k in e2 if not k.endswith("_curated")], (BLUE, ORANGE)):
        v = np.sort(list(e2[k]["ngram_rf_per_site_f1"].values()))
        ax.step(v, np.arange(1, len(v) + 1) / len(v), color=col, label=("Cloudflare" if "cloud" in k else "Quad9"))
    s = sorted(glob.glob(os.path.join(R, "e1", "LOC1_fold0.json")))
    if s:
        v = np.sort(list(json.load(open(s[0]))["per_class_f1"].values()))
        ax.step(v, np.arange(1, len(v) + 1) / len(v), color=GREY, label="Siby LOC1 (2018, 1,500 sites)")
    ax.set_xlabel("Per-site F1"); ax.set_ylabel("CDF of sites"); ax.legend(frameon=False, fontsize=7)
    ax.set_title("Per-site F1 distribution (n-grams RF)", fontsize=9)
    save(fig, "fig11_per_site_cdf.png")


if __name__ == "__main__":
    for f in (fig_reproduction, fig_padding_audit, fig_wire_hist, fig_e2, fig_e3, fig_e4, fig_e5, fig_ablations, fig_cdf):
        try:
            f()
        except Exception as e:
            print("FAILED", f.__name__, type(e).__name__, e)
