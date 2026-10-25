<!-- Source: voximul outputs (leak_eval_thin, baselines, conformal, panel per_container.csv); script run/stats_eval.py; generated 2026-10-20T20:20Z. Folds = crc32(container_id) % 2. Wilcoxon signed-rank (scipy 1.18.1), Holm over all listed comparisons. -->
## Leak gates: operating point selected on fold A (max recall s.t. healthy FPR <= target), reported on fold B
| FPR target | method | selected param | fold-B recall | fold-B healthy FPR | fold-B violation |
|---|---|---|---|---|---|
| 0.05 | resid_lgbm_t6 | 0.2 | 0.137 | 0.053 | 0.0039 |
| 0.05 | resid_lgbm | 0.01 | 0.096 | 0.016 | 0.0036 |
| 0.05 | seasonal_diff_t6_cusum | 0.001 | 0.096 | 0.029 | 0.0036 |
| 0.05 | frozen_profile_t24 | 0.2 | 0.068 | 0.038 | 0.0036 |
| 0.05 | frozen_profile_t24_cusum | 0.1 | 0.055 | 0.033 | 0.0036 |
| 0.05 | frozen_profile_t12_cusum | 0.01 | 0.055 | 0.022 | 0.0038 |
| 0.1 | resid_lgbm | 0.1 | 0.178 | 0.049 | 0.0037 |
| 0.1 | resid_lgbm_cusum | 0.001 | 0.164 | 0.058 | 0.0044 |
| 0.1 | resid_lgbm_t6 | 0.2 | 0.137 | 0.053 | 0.0039 |
| 0.1 | resid_lgbm_t6_cusum | 0.05 | 0.123 | 0.073 | 0.0041 |
| 0.1 | frozen_profile_t6_cusum | 0.001 | 0.110 | 0.036 | 0.0036 |
| 0.1 | seasonal_diff_t6_cusum | 0.001 | 0.096 | 0.029 | 0.0036 |
| 0.35 | resid_lgbm_cusum | 0.05 | 0.329 | 0.343 | 0.0081 |
| 0.35 | seasonal_diff | 0.1 | 0.301 | 0.278 | 0.0077 |
| 0.35 | frozen_profile_t6_cusum | 0.1 | 0.274 | 0.223 | 0.0060 |
| 0.35 | seasonal_diff_t6_cusum | 0.1 | 0.233 | 0.234 | 0.0053 |
| 0.35 | frozen_profile_t12_cusum | 0.2 | 0.233 | 0.212 | 0.0057 |
| 0.35 | frozen_profile | 0.05 | 0.233 | 0.207 | 0.0073 |

## Paired Wilcoxon signed-rank tests, Holm-corrected over all comparisons below
| comparison | metric | mean diff | n | p | p (Holm) |
|---|---|---|---|---|---|
| seasonal_naive vs univariate | bound_slack | +0.0686 | 296 | 5.4e-46 | 1.1e-44 |
| univariate vs holt_winters | bound_slack | -0.0332 | 296 | 3.6e-40 | 7.2e-39 |
| lgbm vs holt_winters | bound_slack | -0.0318 | 296 | 1.3e-39 | 2.5e-38 |
| toto2_313m vs holt_winters | bound_slack | -0.0399 | 296 | 2.2e-38 | 3.9e-37 |
| timesfm3 vs holt_winters | bound_slack | -0.0325 | 296 | 4.8e-38 | 8.2e-37 |
| toto2_22m vs holt_winters | bound_slack | -0.0332 | 296 | 3e-36 | 4.7e-35 |
| toto2_4m vs holt_winters | bound_slack | -0.0309 | 296 | 4.2e-32 | 6.3e-31 |
| modify vs B3_ico_olsgate_6h | slack | +0.0157 | 296 | 1.1e-25 | 1.6e-24 |
| seasonal_naive vs holt_winters | bound_slack | +0.0354 | 296 | 3.6e-19 | 4.7e-18 |
| toto2_4m vs univariate | bound_slack | +0.0024 | 296 | 3.7e-14 | 4.5e-13 |
| modify vs B3_ico_nogate | slack | +0.0016 | 296 | 2.4e-13 | 2.7e-12 |
| modify vs B3_ico_olsgate_6h | violation_rate | -0.0110 | 296 | 7.7e-08 | 7.7e-07 |
| toto2_313m vs univariate | bound_slack | -0.0067 | 296 | 5e-05 | 0.00045 |
| timesfm3 vs univariate | bound_slack | +0.0007 | 296 | 9.7e-05 | 0.00078 |
| modify vs B3_ico_nogate | violation_rate | -0.0015 | 296 | 0.00019 | 0.0013 |
| veto vs B3_ico_nogate | violation_rate | +0.0023 | 296 | 0.0013 | 0.0078 |
| veto vs B3_ico_nogate | slack | -0.0002 | 296 | 0.0091 | 0.045 |
| toto2_22m vs univariate | bound_slack | +0.0000 | 296 | 0.035 | 0.14 |
| lgbm vs univariate | bound_slack | +0.0014 | 296 | 0.046 | 0.14 |
| modify vs B1_vpa | slack | -0.0054 | 296 | 0.089 | 0.18 |
| modify vs B1_vpa | violation_rate | -0.0007 | 296 | 0.3 | 0.3 |
