#!/usr/bin/env bash
# Stream the 29 GB Alibaba v2018 trace through prepare.py without storing it on disk.
set -euo pipefail
U=http://aliopentrace.oss-cn-beijing.aliyuncs.com/v2018Traces/container_usage.tar.gz
curl -sS --retry 5 "$U" | tar -xzOf - container_usage.csv \
  | ~/.local/bin/uv run python run/prepare.py data.alibaba_path=- data.keep_frac=0.02 \
      out_dir=outputs/prepared_alibaba hydra.run.dir=outputs/hydra/prepare_alibaba
echo "DONE exit=0"
