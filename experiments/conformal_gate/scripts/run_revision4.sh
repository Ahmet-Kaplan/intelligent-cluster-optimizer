#!/usr/bin/env bash
# Revision round 4 (panel r2): frontier on calibrated decisions with all containers, a VPA-updater replay, an
# error-padding family and paired bootstrap; leak gates over 10 p-value randomizations x 10 splits; one Holm family.
set -euo pipefail
export UV_PROJECT_ENVIRONMENT=.venv-fm
UV=~/.local/bin/uv
$UV run python run/frontier_eval.py hydra.run.dir=outputs/hydra/frontier_r4 > outputs/frontier_r4.txt 2>&1 &
$UV run python run/frontier_eval.py eval_from=19 out_dir=outputs/frontier_r4_from19 \
    hydra.run.dir=outputs/hydra/frontier_r4_from19 > outputs/frontier_r4_from19.txt 2>&1 &
for i in 1 2 3 4 5 6 7 8 9; do
  $UV run python run/leak_eval.py theta_rep=$i out_dir=outputs/leak_eval_r4/theta_$i \
      hydra.run.dir=outputs/hydra/leak_r4_$i > outputs/leak_eval_r4_$i.txt 2>&1 &
  [ $((i % 3)) -eq 0 ] && wait
done
wait
$UV run python run/strata_eval.py outputs/frontier_r4/per_container.csv outputs/prepared_alibaba > outputs/strata_r4.txt 2>&1
$UV run python run/stats_eval.py > outputs/stats_eval_r4.txt 2>&1
echo "REVISION4 DONE"
