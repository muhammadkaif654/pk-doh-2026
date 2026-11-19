"""Collect every result JSON into report/data.json (numbers and pre-formatted table rows)."""
import glob, json, os
import numpy as np
import common

R = common.RESULTS
OUT = os.path.join(common.ROOT, "report", "data.json")


def J(name):
    p = os.path.join(R, name)
    return json.load(open(p)) if os.path.exists(p) else None


def f3(x):
    return "-" if x is None else f"{x:.3f}"


def ci(r, key="f1"):
    if not r or key + "_ci" not in r:
        return "-"
    lo, hi = r[key + "_ci"]
    return f"[{lo:.3f}, {hi:.3f}]"


NAME = {"ngram_rf": "B1 n-grams + RF (Siby et al. 2020)", "kfp": "B2 k-FP (Hayes & Danezis 2016)",
        "cumul": "B3 CUMUL (Panchenko et al. 2016)", "df": "B4 Deep Fingerprinting (Sirinam et al. 2018)",
        "burst_rf": "B5 Burst statistics + RF (Moure-Garrido et al. 2026)", "timing_rf": "Timing only (F5) + RF",
        "fused_rf": "Proposed: fused RF (F1+F2+F5)", "cnn_se": "Proposed: 1D-CNN + SE",
        "cnn_nose": "1D-CNN without SE", "block_rf_128": "Block-128 n-grams (F4)", "block_rf_468": "Block-468 n-grams (F4)"}


def main():
    D = {}
    # ---------------- E1 reproduction
    rows = []
    e1 = {}
    LAB = {"LOC1": "LOC1, 1,500 pages × 60, pruned n-grams (Table II)",
           "LOC1_exact": "LOC1, 1,500 × 60, all n-grams (check)",
           "LOC1_uni": "LOC1, 1,500 × 60, uni-grams only (released code; check)",
           "LOC2": "LOC2 Leuven, 1,500 × 20 (Table VI)", "LOC3": "LOC3 Singapore, 1,500 × 20 (Table VI)",
           "EDNS0-128-700": "EDNS0-128, 700 × 60 (Table VII)", "EDNS0-468-700": "EDNS0-468, 700 × 60 (Table VII)",
           "PERFECT-700": "Perfect padding, 700 × 60, direction kept (Table VII)",
           "PERFECT-nodir-700": "Perfect padding, 700 × 60, direction dropped",
           "EDNS0-128": "Sensitivity: EDNS0-128, 1,500 × 20", "EDNS0-468": "Sensitivity: EDNS0-468, 1,500 × 10",
           "PERFECT": "Sensitivity: perfect padding, 1,500 × 60"}
    for f in sorted(glob.glob(os.path.join(R, "e1", "*_summary.json"))):
        s = json.load(open(f)); e1[s["exp"]] = s
    order = list(LAB)

    def delta(d):  # show a 4th decimal where 3 decimals would hide which side of a threshold it is on
        r3 = round(abs(d), 3)
        return f"{d:+.4f}" if r3 in (0.03, 0.1) else f"{d:+.3f}"
    for k in order:
        s = e1.get(k)
        if not s:
            continue
        one = s["folds"] < 2
        tp = s.get("tost_p")
        rows.append([LAB[k], f3(s["paper_f1"]), f"{s['f1']:.3f}" if one else f"{s['f1']:.3f} ± {s['f1_sd']:.3f}",
                     "- (1 fold)" if one else ci(s), delta(s["delta_f1"]),
                     "- (1 fold)" if tp is None or one else ("< 0.001" if tp < 0.001 else f3(tp)),
                     f"{s['acc']:.3f} / {s['top5']:.3f}", str(s["folds"]), s["verdict"]])
    D["e1"] = e1; D["e1_rows"] = rows

    # ---------------- Siby-side baselines
    sb = J("siby_baselines.json")
    if sb:
        D["siby_baselines"] = sb
        D["siby_baseline_rows"] = [[NAME[m], f"{sb[m]['f1']:.3f} ± {sb[m]['f1_sd']:.3f}", f3(sb[m]["acc"]),
                                    f3(sb[m].get("top5")), f3(sb[m]["precision"]), f3(sb[m]["recall"]), str(sb[m]["n_runs"])]
                                   for m in ("ngram_rf", "kfp", "cumul", "burst_rf", "df", "fused_rf", "cnn_se", "cnn_nose") if m in sb]
    sc = J("siby_cross.json")
    if sc:
        D["siby_cross"] = sc

    # ---------------- E2
    e2 = J("e2_indomain.json")
    if e2:
        D["e2"] = {k: {m: {kk: vv for kk, vv in v.items() if kk not in ("y", "p")} for m, v in r.items()
                       if isinstance(v, dict) and not m.endswith(("_confusion", "_per_site_f1"))} for k, r in e2.items()}
        rows = []
        for m in ("ngram_rf", "kfp", "cumul", "df", "burst_rf", "timing_rf", "cnn_se", "fused_rf"):
            row = [NAME[m]]
            for k in [k for k in e2 if not k.endswith("_curated")]:
                r = e2[k].get(m)
                row += ([f"{r['f1']:.3f} ± {r['f1_sd']:.3f}", f3(r["acc"]), f3(r.get("top5")), f3(r["precision"]), f3(r["recall"])]
                        if r else ["-"] * 5)
            rows.append(row)
        D["e2_rows"] = rows
        D["e2_meta"] = {k: {"n_per_site": e2[k]["n_per_site"], "n_sites": e2[k]["n_sites"],
                            "wilcoxon": e2[k].get("fused_vs_ngram_wilcoxon_p")} for k in e2}
    # ---------------- E3
    e3 = J("e3_transfer.json")
    if e3:
        D["e3"] = {m: {k: {kk: vv for kk, vv in v.items() if kk != "per_site_f1"} for k, v in mat.items()} for m, mat in e3.items()}
    # ---------------- E4, E5, ablations, realism
    for name, key in (("e4_recovery.json", "e4"), ("realism.json", "realism"), ("ablations.json", "ablations")):
        x = J(name)
        if x:
            D[key] = x
    e5 = J("e5_padding.json")
    if e5:
        for c in e5["deployed"]:
            e5["deployed"][c].pop("hist_in", None); e5["deployed"][c].pop("hist_out", None)
        D["e5"] = e5
    # ---------------- padding audit
    import pandas as pd
    p = os.path.join(R, "padding_audit", "padding_audit_summary.csv")
    if os.path.exists(p):
        s = pd.read_csv(p)
        rows = []
        for res in s.resolver.unique():
            row = [res]
            for proto in ("DoH", "DoT"):
                for cp in (0, 1):
                    r = s[(s.resolver == res) & (s.proto == proto) & (s.client_pad == cp)]
                    if not len(r) or r.verdict.iloc[0] == "unreachable":
                        row.append("unreachable")
                    else:
                        v = r.verdict.iloc[0].replace("pads to 468 (RFC 8467)", "468-B blocks").replace(
                            "pads, non-standard block", "non-standard").replace("no padding", "none")
                        row.append(v)
            rows.append(row)
        D["audit_rows"] = rows
    with open(OUT, "w") as f:
        json.dump(D, f, indent=1, default=float)
    print("wrote", OUT, list(D))


if __name__ == "__main__":
    main()
