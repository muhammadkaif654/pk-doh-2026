"""Paper version of Figure 1: same diagram as fig_pipeline.py, without course-specific labels
(Phase / Step numbers). Writes ../paper/figures/fig1_pipeline.png."""
import os
import common

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "fig_pipeline.py"), encoding="utf-8").read()
for a, b in [
    ("Implemented Phase 3 pipeline (dashed border = changed from the Phase 2 design)",
     "Implemented pipeline (dashed border = changed from the planned design)"),
    ("Preprocessing (Step 3)", "Preprocessing"),
    ("Features (Step 4)", "Features"),
    ("Models (Steps 5-6)", "Models"),
    ("Evaluation (Steps 7-11)", "Evaluation"),
    ("realism statistics per dataset (P10)", "realism statistics per dataset (Jansen et al.)"),
    ("F2 burst statistics, 25 ms gaps (PH1-2)", "F2 burst statistics, 25 ms gaps (Moure-Garrido et al.)"),
]:
    assert a in src, a
    src = src.replace(a, b)
common.FIGS = os.path.join(HERE, "..", "paper", "figures")
exec(compile(src, "fig_pipeline_paper", "exec"), {"__name__": "__main__", "__file__": __file__})
