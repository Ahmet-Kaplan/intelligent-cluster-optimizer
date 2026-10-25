# Revision 4 (panel round 2) results

Generated on voximul by `scripts/run_revision4.sh` at code c586e91 (2026-10-24). Files:
- `frontier_r4.txt`: matched-violation frontier, all 296 containers, calibrated decisions only (eval_from 99), with
  VPA updater replay, error padding and paired bootstrap against VPA. `frontier_r4_from19.txt`: eval_from 19.
- `frontier_paired_r4*.txt`: `run/frontier_paired.py` on the per-container files (low targets, padding and VPA-updater pairs).
- `stats_eval_r4.md`: held-out leak selection (single split and 10 randomizations x 10 splits), one Holm family of
  paired comparisons (mean difference, bootstrap CI, sign-flip p), validity detail with CIs and per-container dispersion.
- `strata_r4.txt`: gate effect by memory-variability tertile (from frontier_r4 per-container data).

Operator envelope (ICO candidate) validity CI, computed 2026-10-24 on voximul from
`outputs/panel_live/ico_candidate/per_container.csv` with the validity_detail bootstrap (seed 0, 2000 resamples):
```
ico_candidate eps 0.01 eta 0: 0.0093 [0.0072, 0.0120] n=273 share>eps/1.5/2: 0.271 / 0.271 / 0.271
ico_candidate eps 0.01 eta 0.005: 0.0184 [0.0137, 0.0234] n=273 share>eps/1.5/2: 0.271 / 0.271 / 0.271
ico_candidate eps 0.05 eta 0: 0.0318 [0.0282, 0.0353] n=296 share>eps/1.5/2: 0.182 / 0.074 / 0.044
ico_candidate eps 0.05 eta 0.005: 0.0317 [0.0286, 0.0347] n=296 share>eps/1.5/2: 0.176 / 0.057 / 0.017
ico_candidate eps 0.1 eta 0: 0.0626 [0.0571, 0.0684] n=296 share>eps/1.5/2: 0.189 / 0.061 / 0.017
ico_candidate eps 0.1 eta 0.005: 0.0642 [0.0593, 0.0689] n=296 share>eps/1.5/2: 0.196 / 0.027 / 0.003
```
