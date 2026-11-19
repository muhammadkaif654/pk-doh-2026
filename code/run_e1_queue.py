"""Sequential E1 queue (resumable: finished folds are skipped)."""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
# Rows of Table 10: [experiment, samples per page, pages ("all" or a number), folds].
# "-700" experiments use the 700 pages that have >= 60 samples in EDNS0-468 (paper's Table I).
JOBS = [["LOC1", "60", "all", "3"], ["LOC1_uni", "60", "all", "1"], ["LOC1_exact", "60", "all", "1"],
        ["LOC2", "20", "all", "3"], ["LOC3", "20", "all", "3"],
        ["EDNS0-128-700", "60", "all", "3"], ["EDNS0-468-700", "60", "all", "3"],
        ["PERFECT-700", "60", "all", "3"], ["PERFECT-nodir-700", "60", "all", "3"],
        # sensitivity rows: all 1,500 released page labels with the samples available
        ["EDNS0-128", "20", "all", "3"], ["EDNS0-468", "10", "all", "3"], ["PERFECT", "60", "all", "3"]]
for j in JOBS:
    print("=== job", j, flush=True)
    subprocess.run([sys.executable, "-u", "e1_reproduce.py", *j])
