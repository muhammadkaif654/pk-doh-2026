"""Figure 1: implemented pipeline (as built in Phase 3), with changes vs Phase 2 marked."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

import common

C_A, C_B, C_C, C_S = "#dbe7f5", "#fde6d2", "#dff1e4", "#eceff1"
EDGE = {"A": "#2f6db5", "B": "#e07b28", "C": "#3a9a5b", "S": "#5f6b73"}


def box(ax, x, y, w, h, title, lines, kind, changed=False):
    fc = {"A": C_A, "B": C_B, "C": C_C, "S": C_S}[kind]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.008,rounding_size=0.012",
                                fc=fc, ec=EDGE[kind], lw=1.6 if not changed else 2.2,
                                ls="-" if not changed else (0, (4, 2))))
    ax.text(x + 0.012, y + h - 0.028, title, fontsize=7.6, weight="bold", va="top", color="#102833")
    ax.text(x + 0.012, y + h - 0.075, "\n".join(lines), fontsize=6.1, va="top", color="#1d2b33", linespacing=1.25)


def arrow(ax, x1, y1, x2, y2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", color="#5f6b73", lw=1.0))


def main():
    fig = plt.figure(figsize=(7.6, 4.7))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.text(0.5, 0.975, "Implemented Phase 3 pipeline (dashed border = changed from the Phase 2 design)",
            ha="center", fontsize=9, weight="bold", color="#102833")
    # row 1: data tracks
    box(ax, 0.02, 0.73, 0.30, 0.21, "Track A - published data (RQ1)",
        ["Siby et al. release: LOC1 (415k traces),", "LOC2, LOC3, EDNS0-128/468", "2018-19, sizes + order only",
         "DOT and GOOGLE/CLOUD 60-sample sets", "not released -> dropped"], "A", True)
    box(ax, 0.35, 0.73, 0.30, 0.21, "Track B - PK-DoH-2026 capture (RQ2)",
        ["100 sites: 50 global (Siby list) + 50 .pk", "Chrome 157 native DoH, fresh profile,",
         "HTTP/2 (QUIC off), dumpcap per resolver IP", "Network A: residential Wi-Fi, Pakistan",
         "2 resolvers x 4 parallel workers"], "B", True)
    box(ax, 0.68, 0.73, 0.30, 0.21, "Track C - padding audit (RQ3)",
        ["11 public resolvers x DoH/DoT", "with / without client EDNS(0) padding",
         "ground truth from decrypted replies", "-> Cloudflare (pads 468) and",
         "   Quad9 (never pads) chosen for Track B"], "C")
    # row 2: preprocessing
    box(ax, 0.02, 0.47, 0.96, 0.20, "Preprocessing (Step 3)",
        ["tshark TLS-record extraction with TCP reassembly; TLS 1.3 handshake records removed so traces start at the first DoH exchange (comparable to TLS 1.2 data)",
         "signed record sizes (+ client->resolver, - resolver->client) and timestamps; crashed / < 5-record traces removed; balanced per site",
         "curation variant: drop sites whose loads mostly hit bot-challenge pages (Siby's 'strange page' removal); realism statistics per dataset (P10)",
         "label alignment: 50 global sites mapped to Siby class indices for cross-dataset transfer"], "S", True)
    # row 3: features and models
    box(ax, 0.02, 0.22, 0.46, 0.20, "Features (Step 4)",
        ["F1 n-grams of record & burst sizes (Siby)", "F2 burst statistics, 25 ms gaps (PH1-2)",
         "F3 (size, log-IAT, direction) sequence for CNN", "F4 128/468-byte block indices (RFC 8467)",
         "F5 per-slot log-IAT histograms, 250 ms slots (after WFCAT)"], "S", True)
    box(ax, 0.52, 0.22, 0.46, 0.20, "Models (Steps 5-6)",
        ["B1 n-grams RF  B2 k-FP  B3 CUMUL  B4 DF  B5 burst RF",
         "Proposed: fused RF (F1+F2+F5) and 1D-CNN + SE",
         "memory-light 'streaming' RF for 1,500 classes",
         "(same model, trees scored then freed)"], "S", True)
    # row 4: experiments
    box(ax, 0.02, 0.02, 0.96, 0.15, "Evaluation (Steps 7-11)",
        ["E1 reproduction vs published F1 (tolerance |dF1|<=0.03, TOST)   E2 in-domain, all models, 10 x 80/20 splits   E3 transfer matrix with site-clustered bootstrap CIs",
         "E4 recovery curve (k target traces)   E5 deployed vs simulated padding, size vs timing features   A1-A7 ablations   per-site F1 distribution"], "S", True)
    for x in (0.17, 0.50, 0.83):
        arrow(ax, x, 0.73, x, 0.675)
    arrow(ax, 0.68, 0.80, 0.655, 0.80)
    arrow(ax, 0.25, 0.47, 0.25, 0.425); arrow(ax, 0.75, 0.47, 0.75, 0.425)
    arrow(ax, 0.48, 0.32, 0.52, 0.32)
    arrow(ax, 0.50, 0.22, 0.50, 0.175)
    fig.savefig(os.path.join(common.FIGS, "fig1_pipeline.png"), dpi=300)
    print("figure fig1_pipeline.png")


if __name__ == "__main__":
    main()
