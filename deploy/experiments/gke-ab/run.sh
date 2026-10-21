#!/usr/bin/env bash
# Live A/B run of the conformal admission gate on GKE.  Usage: run.sh up | status | collect | down
set -euo pipefail
PROJECT=${PROJECT:-project-82a946e9-425a-404f-acf}
ZONE=${ZONE:-us-central1-a}
CLUSTER=${CLUSTER:-ico-gate-ab}
REPO=us-central1-docker.pkg.dev/$PROJECT/optimizer
IMAGE=$REPO/controller:gate-$(git -C "$(dirname "$0")" rev-parse --short HEAD)
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$HERE/../../..
OUT=${OUT:-$HERE/out}
PATTERNS="steady cycle-1h cycle-6h spike spike-b regime leak-reset noisy noisy-b"

workloads() { # $1 = namespace
  sed "s/__NS__/$1/" "$HERE/workloads.tmpl.yaml"
  for w in $PATTERNS; do cat <<YAML
---
apiVersion: apps/v1
kind: Deployment
metadata: {name: $w, namespace: $1}
spec:
  replicas: 1
  strategy: {type: Recreate}
  selector: {matchLabels: {app: $w}}
  template:
    metadata: {labels: {app: $w}}
    spec:
      containers:
      - name: mem
        image: polinux/stress-ng
        command: [/bin/bash, /p/${w%-b}.sh]
        resources:
          requests: {cpu: 50m, memory: 512Mi}
          limits: {cpu: 200m, memory: 1Gi}
        volumeMounts: [{name: p, mountPath: /p}]
      volumes: [{name: p, configMap: {name: mem-patterns}}]
YAML
  done
}

case ${1:-} in
up)
  gcloud config set project "$PROJECT"
  gcloud artifacts repositories describe optimizer --location us-central1 >/dev/null 2>&1 ||
    gcloud artifacts repositories create optimizer --repository-format docker --location us-central1
  gcloud auth configure-docker us-central1-docker.pkg.dev -q
  docker buildx build --platform linux/amd64 -t "$IMAGE" --push "$ROOT"
  # On-demand nodes and no auto-upgrade: the gate's calibration lives in controller memory,
  # so a preemption or node upgrade mid-run would restart its cold start.
  gcloud container clusters describe "$CLUSTER" --zone "$ZONE" >/dev/null 2>&1 ||
    gcloud container clusters create "$CLUSTER" --zone "$ZONE" --num-nodes 2 \
      --machine-type e2-standard-4 --release-channel None --no-enable-autoupgrade \
      --no-enable-autorepair --monitoring SYSTEM --logging SYSTEM,WORKLOAD
  gcloud container clusters get-credentials "$CLUSTER" --zone "$ZONE"
  kubectl apply -f "$ROOT/config/crd/"
  kubectl kustomize "$ROOT/deploy" | sed "s#us-central1-docker.pkg.dev/k8s-resource-optimizer/optimizer/controller:latest#$IMAGE#" |
    perl -pe 's#^(\s+)- --api-addr=:8090#$1- --api-addr=:8090\n$1- --v=3#' | kubectl apply -f -
  kubectl -n intelligent-optimizer-system delete optimizerconfig workloads-optimizer --ignore-not-found
  for ns in gate-on gate-off; do workloads $ns | kubectl apply -f -; done
  kubectl apply -f "$HERE/configs.yaml"
  date -u +%FT%TZ > "$HERE/started_at"; echo "started $(cat "$HERE/started_at"), image $IMAGE";;
status)
  kubectl -n intelligent-optimizer-system get optimizerconfig,pods
  kubectl get pods -n gate-on; kubectl get pods -n gate-off
  kubectl -n intelligent-optimizer-system logs deploy/intelligent-optimizer-controller --since=24h |
    grep -c "conformal decision scored" || true;;
collect)
  mkdir -p "$OUT"
  kubectl -n intelligent-optimizer-system logs deploy/intelligent-optimizer-controller > "$OUT/controller.log"
  kubectl -n intelligent-optimizer-system get events -o json > "$OUT/events.json"
  for ns in gate-on gate-off; do kubectl -n $ns get pods,events -o json > "$OUT/$ns.json"; done
  echo "$IMAGE" > "$OUT/image.txt"; cp "$HERE/started_at" "$OUT/"; echo "collected to $OUT";;
down)
  gcloud container clusters delete "$CLUSTER" --zone "$ZONE" -q;;
*) echo "usage: $0 up|status|collect|down"; exit 1;;
esac
