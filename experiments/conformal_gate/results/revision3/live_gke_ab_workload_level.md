<!-- Source: python3 deploy/experiments/live_report.py gke-ab/out gate-on gate-off --gate-log gke-ab/out/controller-gate.json --vetoes gke-ab/out/controller-vetoes.json (operator repo, commit 9df4689); controller-vetoes.json re-exported from Cloud Logging 2026-10-24; generated 2026-10-23T21:46:20Z -->

## whole run: per-workload hours exceeded / hours (mean request MiB)
| workload | gate-on | gate-off |
|---|---|---|
| cycle-1h | 0/47 (632) | 1/47 (545) |
| cycle-6h | 0/47 (621) | 10/47 (497) |
| leak-reset | 10/47 (657) | 5/47 (626) |
| noisy | 0/47 (538) | 0/47 (521) |
| noisy-b | 0/47 (549) | 0/47 (523) |
| regime | 0/47 (655) | 6/47 (290) |
| spike | 7/47 (828) | 22/47 (293) |
| spike-b | 7/47 (753) | 2/47 (687) |
| steady | 0/47 (421) | 0/47 (365) |
| **total** | 24/423 = 0.057 (628) | 46/423 = 0.109 (483) |

Workload-level, gate-on minus other arm (per-workload exceedance rate): mean diff [95% bootstrap CI over workloads], Wilcoxon p, Holm p, workloads lower/higher
- vs gate-off: -0.0520 [-0.1442, +0.0307], p = 0.249, Holm p = 0.249, 4 lower / 2 higher of 9

Replayed trailing-24 h-max rules on the gate arm's usage (hours exceeded / hours, mean request MiB):
- max(24 h) x 1.0: 20/423 = 0.047, mean request 487
- max(24 h) x 1.15: 7/423 = 0.017, mean request 560

## calibrated window: per-workload hours exceeded / hours (mean request MiB)
| workload | gate-on | gate-off |
|---|---|---|
| cycle-1h | 0/29 (706) | 0/29 (546) |
| cycle-6h | 0/26 (706) | 0/26 (606) |
| leak-reset | 0/25 (777) | 0/25 (703) |
| noisy | 0/28 (553) | 0/28 (529) |
| noisy-b | 0/28 (570) | 0/28 (523) |
| regime | 0/27 (756) | 3/27 (320) |
| spike | 0/29 (1024) | 13/29 (295) |
| spike-b | 0/29 (903) | 0/29 (727) |
| steady | 0/29 (365) | 0/29 (365) |
| **total** | 0/250 = 0.000 (707) | 16/250 = 0.064 (513) |

Workload-level, gate-on minus other arm (per-workload exceedance rate): mean diff [95% bootstrap CI over workloads], Wilcoxon p, Holm p, workloads lower/higher
- vs gate-off: -0.0622 [-0.1618, +0.0000], p = 0.18, Holm p = 0.18, 2 lower / 0 higher of 9

Replayed trailing-24 h-max rules on the gate arm's usage (hours exceeded / hours, mean request MiB):
- max(24 h) x 1.0: 2/250 = 0.008, mean request 494
- max(24 h) x 1.15: 0/250 = 0.000, mean request 568

## Operations per arm (whole run)
| arm | pods created | request changes | minutes over request | mean overrun MiB (when over) |
|---|---|---|---|---|
| gate-on | 36 | 19 | 414/25992 = 0.0159 | 70 |
| gate-off | 234 | 116 | 682/25992 = 0.0262 | 220 |

## Gate log: scored 404, calibrated 233, bound misses 2 (0.0086); median bound slack over peak 0.662; bound above 1 GiB limit 45; bound below candidate 78; calibrated decisions per container 19-28

## Vetoes by other layers (log lines; one per reconcile, ~30 s): {('gate-off', 'anomaly'): 9885, ('gate-off', 'leak'): 2232, ('gate-on', 'anomaly'): 9602, ('gate-on', 'leak'): 1959}
