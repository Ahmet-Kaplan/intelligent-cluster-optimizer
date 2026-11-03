# Live v4 run: analysis plan, fixed before launch

Written and committed before `run.sh up`; the commit hash and the start time in `out/started_at` date it.
Changes after launch are listed at the end, with reasons.

## Why a fourth run
The pre-registered v3 run (deploy/experiments/gke-ab-v3/PREREGISTRATION.md) was unfavorable to the gate on the
primary outcome: hours exceeded 46/1554 (gate) vs 14 (nogate), 6 (margin), 5 (vpa); Holm-adjusted p = 0.081 for all
three comparisons. All of the gate arm's exceedances fell in the cold start (about the first 19 h). During cold start
the gate has no calibrated verdict, and the controller queued every live change for human approval, raises included.
None were approved, so the gate arm's containers stayed at their initial 512Mi while the other arms raised theirs.

v4 tests one change to that policy: **during cold start, a memory raise is applied without approval; only a memory
reduction waits for approval** (`coldStartNeedsApproval` in pkg/controller/admission_gate.go). Everything else is the
v3 design. v3 stays the pre-registered result of the original policy and is reported unchanged; v4 is a separate
confirmatory run of the modified policy, and both are reported whatever v4 shows.

## Design
Identical to v3 except where noted.
- **Demand:** `pattern.sh` (unchanged from v3) sets usage per 10-min wall-clock segment from (pattern, seed, segment) only. Every arm sees the same demand, and a restarted pod resumes at the clock's level.
- **Workloads:** 7 patterns (steady, cycle-1h, cycle-6h, spike, regime, leak-reset, noisy) x 3 seeds = 21 single-replica Deployments per arm. Initial request 512Mi, limit 1Gi.
- **Arms** (`configs.yaml`, unchanged from v3):
  - `ab-gate`: ICO with memoryRiskBudget 0.05.
  - `ab-nogate`: ICO with no gate.
  - `ab-margin`: ICO with no gate and safetyMargin 1.65.
  - `ab-vpa`: GKE VPA with updateMode Recreate, memory only, RequestsOnly, minReplicas 1, maxAllowed 1Gi.
- **Controller:** the v3 controller plus the cold-start change above (the commit that adds this file). The leak and
  anomaly vetoes are off in all ICO arms. Controller memory limit 2Gi.
- **Duration and cluster:** 72 h on GKE (cluster `ico-gate-ab4`), 4 x e2-highmem-4. Collection is scheduled at
  exactly 72 h after `started_at`; the analysis is cut at 72 h with `live_report.py --until` in any case.
- **Log export (change from v3):** the `run.sh collect` filter also keeps the "Capping recommended Memory" lines, so
  outcome (f) is counted directly rather than reconstructed.

## Outcomes
**Primary:** for each workload, the fraction of hours in which the hourly peak of non-evictable memory exceeded the
hour's minimum request.
- Data: GKE metrics at 60 s; an hour counts if it has >= 30 samples.
- Window: whole run, starting 1 h after launch, ending 72 h after launch.

**Secondary:**
- (a) The same outcome over the calibrated window, from the gate arm's first calibrated decision per workload. The same window is applied to the other arms.
- (b) Mean request in MiB.
- (c) Pod recreations, counted as distinct pod names.
- (d) Minutes over the request, and the mean overrun in MiB.
- (e) Gate log: the bound-miss rate, the bound slack over the peak, and the number of calibration scores per container.
- (f) RiskBudgetUncertified decisions: gate-arm "Capping recommended Memory" lines that follow a "Risk budget ... raised" line for the same container in the same reconcile.
- (g) Controller memory (non-evictable, hourly maximum) and restarts over the run.
- (h) New in v4: the same primary outcome restricted to the cold start (launch + 1 h to the gate arm's first calibrated decision per workload), and the number of cold-start raises applied and reductions queued in the gate arm.

## Tests
- **Unit of analysis:** the workload (21 per arm).
- **Primary comparisons, paired by workload:** gate vs nogate, gate vs margin, gate vs vpa.
  - Wilcoxon signed-rank test on per-workload exceedance rates, Holm-corrected over these 3 comparisons.
  - Mean paired difference with a 95% bootstrap CI over workloads (10,000 resamples).
- **Hour-level counts** are reported descriptively only.
- **Reporting:** all four arms and all 21 workloads go in a per-workload table, whatever the result. v4 is not pooled
  with v3.

## Changes after launch
(none)
