# Live GKE run v4 (second confirmatory run: cold-start raises applied)

Pre-registration: operator repo `deploy/experiments/gke-ab-v4/PREREGISTRATION.md` (6f38386; one change after launch,
logged there: the outcome (h) analysis code, 0e597e6). Controller image `controller:gate-0e597e6` (controller code
as 6f38386; 0e597e6 only touches `live_report.py`).
Cluster ico-gate-ab4, 4x e2-highmem-4, us-central1-a. Start 2026-11-03T14:03:11Z; collected and cluster deleted
2026-11-06 (72 h). Design otherwise identical to v3 (see `../revision5/README.md`). Not pooled with v3.

    cd deploy/experiments/gke-ab-v4
    python3 ../live_report.py out ab-gate ab-nogate ab-margin ab-vpa --gate-log out/controller-full.json --until 2026-11-06T14:03:11Z
    python3 ../../../experiments/conformal_gate/results/revision6/uncert_ctrl_v4.py out 2026-11-06T14:03:11

Outputs: `live_v4_report.txt` (primary, (a)-(e), (h)), `live_v4_f_g.txt` ((f), (g)).

Notes:
- (f) counted directly as pre-registered: 11,980 gate-arm capping lines, each following a same-container
  "Risk budget ... raised" line with the same value within 60 s; 0 capping lines without such a raise. All on
  spike-s1..s3. The controller logs one pair per reconcile, so the line count is per reconcile, not per decision;
  the per-decision count from the scored log (report, "uncertified") is 108 of 1491 scored decisions.
- (g) controller: 0 restarts, one pod; non-evictable memory hourly max median 270 MiB, max 352 MiB.
- Pods created (report, operations): gate 1158 vs nogate 769, margin 757, vpa 49.
- `live_v4_miss_detail.txt`: `../revision5/miss_detail.py` on v4. 20/1092 misses; bound below candidate in 19;
  peak above candidate in 2 (spike-s3, 2026-11-05T10-11: admitted request 245 MiB, the only large gate overruns);
  3 of 21 containers above eps (0.058 each), none above 2 eps; 52 calibrated decisions per container.
- `live_v4_overrun.txt` (`overrun_v4.py`, descriptive, NOT pre-registered): size of each calibrated-window
  exceedance. Gate: 11 of 13 are +116..+156 KiB over a 606 MiB request, 2 are +361 MiB over 245 MiB. No gate:
  all 13 +361 MiB over 245 MiB; margin: all 13 +269 MiB over 337 MiB; VPA: none.
