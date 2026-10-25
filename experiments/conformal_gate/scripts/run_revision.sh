#!/usr/bin/env bash
# Revision round 2: corrected metrics (floored bounds, no skipped horizons, robust sharpness), validity detail,
# FM context sensitivity, frontier and statistics. Regenerates every table in Section V-G.
set -euo pipefail
export UV_PROJECT_ENVIRONMENT=.venv-fm
UV=~/.local/bin/uv
$UV run python run/forecast.py model=toto2_22m context=8192 out_dir=outputs/forecasts_toto2_22m_ctx8192 \
    hydra.run.dir=outputs/hydra/forecast_toto2_22m_ctx8192
ev() { $UV run python run/conformal_eval.py forecast_dir=$1 "variants=$2" skip_decisions=24 \
         out_dir=outputs/panel/$3 hydra.run.dir=outputs/hydra/panel_$3 > outputs/panel_$3.txt 2>&1; }
ev outputs/forecasts "[univariate,covariate]" chronos2
ev outputs/forecasts_hw "[holt_winters]" holt_winters
ev outputs/forecasts_baselines "[seasonal_naive,lgbm]" baselines
for m in toto2_4m toto2_22m toto2_313m timesfm3; do ev outputs/forecasts_$m "[$m]" $m; done
ev outputs/forecasts_toto2_22m_ctx8192 "[toto2_22m]" toto2_22m_ctx8192_tmp
mkdir -p outputs/panel_ctx && rm -rf outputs/panel_ctx/toto2_22m_ctx8192 && mv outputs/panel/toto2_22m_ctx8192_tmp outputs/panel_ctx/toto2_22m_ctx8192
$UV run python run/conformal_eval.py hydra.run.dir=outputs/hydra/conformal_eval > outputs/conformal_summary_r2.txt 2>&1
$UV run python run/frontier_eval.py hydra.run.dir=outputs/hydra/frontier > outputs/frontier_r2.txt 2>&1
$UV run python run/stats_eval.py > outputs/stats_eval_r2.txt 2>&1
for e in 0.01 0.05 0.1; do $UV run python run/panel_summary.py outputs/panel $e 0.005 > outputs/panel_summary_r2_eps$e.txt 2>&1; done
$UV run python run/panel_summary.py outputs/panel 0.01 0.0 > outputs/panel_summary_r2_eps0.01_static.txt 2>&1
echo "REVISION DONE"
