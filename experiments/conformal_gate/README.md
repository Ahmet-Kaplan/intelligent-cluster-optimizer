# Conformal gate evaluation harness

Trace-driven evaluation of the conformal admission and leak gates reported in the paper
"Calibrated Risk for Kubernetes Vertical Autoscaling: Conformal Admission and Leak Gates in a Layered Safety Pipeline"
(Section "Conformal Gate Evaluation"). The Go implementation of the admission gate is in `pkg/conformal`, and the
live GKE experiments are in `deploy/experiments/gke-ab` (v1) and `deploy/experiments/gke-ab-v2` (v2, pre-registered).

## Layout
- `src/cgate/`: data preparation, leak injection, baselines (ICO engine, VPA formula, VPA with updater, error
  padding, fixed headroom), conformal admission (`conformal.py`), conformal leak gate (`leak_conformal.py`), metrics.
- `run/`: Hydra entry points (`prepare.py`, `forecast.py`, `conformal_eval.py`, `frontier_eval.py`, `leak_eval.py`,
  `stats_eval.py`, ...). `conf/`: their configurations.
- `scripts/`: the exact command sequences used for each revision (`run_alibaba.sh`, `run_panel.sh`,
  `run_revision.sh`, `run_revision4.sh`).
- `results/`: every table in the paper, with a header naming the command and code version that produced it.

## Reproduce
1. `uv sync` (Python >= 3.12). Foundation-model forecasts need a GPU and the optional model packages in `pyproject.toml`.
2. `bash scripts/run_alibaba.sh` downloads the public Alibaba cluster-trace v2018
   (https://github.com/alibaba/clusterdata) and prepares 300 containers with five injection seeds (~34 min).
3. `bash scripts/run_panel.sh`, then `scripts/run_revision.sh`, then `scripts/run_revision4.sh` regenerate the results.
4. `uv run pytest` runs the unit tests.
