"""Delete pcaps that have no metadata row (visits interrupted by a stop)."""
import csv, glob, os
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "pcap")
for cond in [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))]:
    have = set()
    for m in glob.glob(os.path.join(root, f"{cond}_ip*_meta.csv")):
        have |= {r["file"] for r in csv.DictReader(open(m, encoding="utf-8"))}
    for f in os.listdir(os.path.join(root, cond)):
        if f not in have:
            try:
                os.remove(os.path.join(root, cond, f)); print("removed", cond, f)
            except OSError as e:
                print("locked", cond, f, e)
