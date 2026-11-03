"""Per-container miss rates and bound-vs-candidate in misses, using live_report's own log parser."""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, sys.argv[1])  # operator repo: deploy/experiments
from live_report import bound, gate_log  # noqa: E402

base = Path(sys.argv[2])  # gke-ab-v3/out
rows = gate_log(base / "controller-full.json", "ab-gate")
cal = [(r, bound(r[4])) for r in rows.values() if bound(r[4]) is not None]
miss = [(r, b) for r, b in cal if float(r[2]) > b]
print("scored", len(rows), "calibrated", len(cal), "misses", len(miss))
print("misses with bound < candidate:", sum(b < float(r[3]) for r, b in miss))
print("misses with bound >= candidate:", sum(b >= float(r[3]) for r, b in miss))
print("misses with peak > candidate:", sum(float(r[2]) > float(r[3]) for r, b in miss))
n = Counter(r[0] for r, _ in cal)
m = Counter(r[0] for r, _ in miss)
rates = sorted(((m[k] / n[k], m[k], n[k], k) for k in n), reverse=True)
print("containers", len(n), "over eps 0.05:", sum(x[0] > 0.05 for x in rates), "over 2eps:", sum(x[0] > 0.10 for x in rates))
print("with zero misses:", sum(x[1] == 0 for x in rates))
for x in rates[:8]:
    print(f"{x[3]} {x[1]}/{x[2]} = {x[0]:.3f}")
print("calibration scores per container (calibrated decisions) min/max:", min(n.values()), max(n.values()))
