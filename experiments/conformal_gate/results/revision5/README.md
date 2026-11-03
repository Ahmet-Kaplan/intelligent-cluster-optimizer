# Live GKE runs v2 (segment 1, exploratory) and v3 (confirmatory)

Pre-registrations: operator repo `deploy/experiments/gke-ab-v2/PREREGISTRATION.md` (3956468, with its
changes-after-launch log) and `deploy/experiments/gke-ab-v3/PREREGISTRATION.md` (10699df, no changes after launch).
Analysis code: `deploy/experiments/live_report.py` at operator commit 6abaf8c.

## v3 (confirmatory)
Cluster ico-gate-ab3, 4x e2-highmem-4, us-central1-a. Controller image `controller:gate-10699df`.
Start 2026-10-25T13:33:24Z; data collected and cluster deleted 2026-10-28 (72 h).
Arms ab-gate (memoryRiskBudget 0.05), ab-nogate, ab-margin (safetyMargin 1.65), ab-vpa (GKE VPA, Recreate);
21 workloads per arm (7 wall-clock-anchored patterns x 3 seeds), request 512Mi, limit 1Gi; leak and anomaly vetoes off.

    cd deploy/experiments/gke-ab-v3
    python3 ../live_report.py out ab-gate ab-nogate ab-margin ab-vpa --gate-log out/controller-full.json

Output: `live_v3_report.txt`.

Additional checks (not in the report, computed from the same files on 2026-10-29):
- Exceedance hours by arm and UTC hour: every exceedance in every arm falls between 2026-10-25T14 and 2026-10-26T08,
  before the calibrated window starts. Gate arm: 2-5 per hour throughout; the other arms fall to 0-1 per
  hour after about 2026-10-26T02.
- Cause: in cold start the reconciler queues every live change, raises included, for approval
  (`pkg/controller/reconciler.go`, "Queueing ... conformal gate in cold start"; 45,966 such log lines). No change was
  approved during the run, so gated workloads kept 512Mi until calibrated.
- Workload restarts (kubernetes.io/container/restart_count): 0 in every arm. Controller restarts: 0.
- Controller non-evictable memory, hourly max: 14 MiB at start, 275-375 MiB from 2026-10-26T07 to the end.
- RiskBudgetUncertified: the Kubernetes events (1 h TTL) were not retained, and the exported log filter
  (run.sh collect) did not include the capping log line. The report therefore counts uncertified decisions from the
  scored log: finite bound > 1 GiB limit and > candidate, i.e. a raise that the reconciler capped at the limit.
  v3: 95 of 1155 calibrated decisions, all on spike-s1..s3; in none of those hours did the peak exceed 1 GiB.

## v2 segment 1 (exploratory)
Cluster ico-gate-ab2, same design; start 2026-10-23T21:50:55Z. The controller was OOM-killed from 2026-10-25T07:45Z
(metrics store never garbage-collected) and the run was stopped at 12:52Z. Segment 1 = launch to the first OOM.

    cd deploy/experiments/gke-ab-v2
    python3 ../live_report.py out ab-gate ab-nogate ab-margin ab-vpa --gate-log out/controller-full.json --until 2026-10-25T07:45

Output: `live_v2_segment1_report.txt`. Uncertified: 40 of 294 calibrated decisions, all on spike-s1..s3.

## Checks added 2026-10-30 (panel round 3)
The cluster was deleted about 3.8 h after the pre-registered 72 h, so the hourly bins cover 74 h (the "72 h" above is
the nominal duration).
- `live_v3_72h_report.txt`: `live_report.py ... --until 2026-10-28T13:33`, the data cut at 72 h: 46, 14, 6, 5 of 1491
  hours, Holm p = 0.0818. Only its whole-run section is meaningful (no gate log was passed, so no calibrated window).
- `live_v3_miss_detail.txt`: `miss_detail.py OPERATOR/deploy/experiments OPERATOR/deploy/experiments/gke-ab-v3/out`:
  per-container miss rates; all 34 misses have the bound below the candidate and the peak at or below the candidate.
- `pkg/conformal` coverage 98.0% (`go test -cover ./pkg/conformal/`, operator 6abaf8c, same Go code as 10699df).
