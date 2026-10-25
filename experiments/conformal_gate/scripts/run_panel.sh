#!/usr/bin/env bash
# Forecaster panel: baselines + Toto 2.0 sizes + TimesFM 3.0, then conformal eval of all forecasters on a common start.
set -euo pipefail
export UV_PROJECT_ENVIRONMENT=.venv-fm
UV=~/.local/bin/uv
$UV run python run/baseline_forecast.py hydra.run.dir=outputs/hydra/baseline_forecast
for m in toto2_4m toto2_22m toto2_313m timesfm3; do
  $UV run python run/forecast.py model=$m out_dir=outputs/forecasts_$m hydra.run.dir=outputs/hydra/forecast_$m
done
ev() { $UV run python run/conformal_eval.py forecast_dir=$1 "variants=$2" skip_decisions=24 \
         out_dir=outputs/panel/$3 hydra.run.dir=outputs/hydra/panel_$3 > outputs/panel_$3.txt 2>&1; }
mkdir -p outputs/panel
ev outputs/forecasts "[univariate,covariate]" chronos2
ev outputs/forecasts_hw "[holt_winters]" holt_winters
ev outputs/forecasts_baselines "[seasonal_naive,lgbm]" baselines
for m in toto2_4m toto2_22m toto2_313m timesfm3; do ev outputs/forecasts_$m "[$m]" $m; done
echo "PANEL DONE"
