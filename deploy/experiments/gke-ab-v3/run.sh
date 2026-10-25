#!/usr/bin/env bash
# Live v3 run of the conformal admission gate on GKE: the v2 design with the fixed controller (metrics GC).
# Usage: PROJECT=<gcp project> run.sh up | status | collect | down       (analysis plan: PREREGISTRATION.md)
set -euo pipefail
export PATH="$(gcloud info --format='value(installation.sdk_root)')/bin:$PATH"  # gke-gcloud-auth-plugin
PROJECT=${PROJECT:?set PROJECT to your GCP project id}
ZONE=${ZONE:-us-central1-a}
CLUSTER=${CLUSTER:-ico-gate-ab3}
REPO=us-central1-docker.pkg.dev/$PROJECT/optimizer
IMAGE=$REPO/controller:gate-$(git -C "$(dirname "$0")" rev-parse --short HEAD)
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$HERE/../../..
OUT=${OUT:-$HERE/out}
ARMS="ab-gate ab-nogate ab-margin ab-vpa"
PATTERNS="steady cycle-1h cycle-6h spike regime leak-reset noisy"
SEEDS="1 2 3"

workloads() { # $1 = namespace
  cat <<YAML
apiVersion: v1
kind: Namespace
metadata: {name: $1}
---
apiVersion: v1
kind: ConfigMap
metadata: {name: pattern, namespace: $1}
data:
  pattern.sh: |
$(sed 's/^/    /' "$HERE/pattern.sh")
YAML
  for p in $PATTERNS; do for s in $SEEDS; do cat <<YAML
---
apiVersion: apps/v1
kind: Deployment
metadata: {name: $p-s$s, namespace: $1}
spec:
  replicas: 1
  strategy: {type: Recreate}
  selector: {matchLabels: {app: $p-s$s}}
  template:
    metadata: {labels: {app: $p-s$s}}
    spec:
      containers:
      - name: mem
        image: polinux/stress-ng
        command: [/bin/bash, /p/pattern.sh, $p, "$s"]
        resources:
          requests: {cpu: 50m, memory: 512Mi}
          limits: {cpu: 200m, memory: 1Gi}
        volumeMounts: [{name: p, mountPath: /p}]
      volumes: [{name: p, configMap: {name: pattern}}]
YAML
    if [ "$1" = ab-vpa ]; then cat <<YAML
---
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata: {name: $p-s$s, namespace: $1}
spec:
  targetRef: {apiVersion: apps/v1, kind: Deployment, name: $p-s$s}
  updatePolicy: {updateMode: Recreate, minReplicas: 1}
  resourcePolicy:
    containerPolicies:
    - containerName: mem
      controlledResources: [memory]
      controlledValues: RequestsOnly
      minAllowed: {memory: 64Mi}
      maxAllowed: {memory: 1Gi}
YAML
    fi
  done; done
}

case ${1:-} in
up)
  gcloud config set project "$PROJECT"
  gcloud artifacts repositories describe optimizer --location us-central1 >/dev/null 2>&1 ||
    gcloud artifacts repositories create optimizer --repository-format docker --location us-central1
  gcloud auth configure-docker us-central1-docker.pkg.dev -q
  docker buildx build --platform linux/amd64 -t "$IMAGE" --push "$ROOT"
  # On-demand nodes and a no-upgrades exclusion: the gate's calibration lives in controller memory.
  gcloud container clusters describe "$CLUSTER" --zone "$ZONE" >/dev/null 2>&1 || {
    gcloud container clusters create "$CLUSTER" --zone "$ZONE" --num-nodes 4 \
      --machine-type e2-highmem-4 --release-channel stable --enable-vertical-pod-autoscaling \
      --monitoring SYSTEM --logging SYSTEM,WORKLOAD
    gcloud container clusters update "$CLUSTER" --zone "$ZONE" \
      --add-maintenance-exclusion-name ab-run --add-maintenance-exclusion-scope no_upgrades \
      --add-maintenance-exclusion-start "$(date -u +%FT%TZ)" \
      --add-maintenance-exclusion-end "$(date -u -v+6d +%FT%TZ)"
  }
  gcloud container clusters get-credentials "$CLUSTER" --zone "$ZONE"
  SA="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')-compute@developer.gserviceaccount.com"
  gcloud artifacts repositories add-iam-policy-binding optimizer --location us-central1 \
    --member "serviceAccount:$SA" --role roles/artifactregistry.reader >/dev/null
  kubectl apply -f "$ROOT/config/crd/"
  kubectl kustomize "$ROOT/deploy" | sed "s#us-central1-docker.pkg.dev/k8s-resource-optimizer/optimizer/controller:latest#$IMAGE#" |
    perl -pe 's#^(\s+)- --api-addr=:8090#$1- --api-addr=:8090\n$1- --v=3#' | kubectl apply -f -
  kubectl -n intelligent-optimizer-system delete optimizerconfig workloads-optimizer --ignore-not-found
  for ns in $ARMS; do workloads $ns | kubectl apply -f -; done
  kubectl apply -f "$HERE/configs.yaml"
  kubectl -n intelligent-optimizer-system rollout status deploy/intelligent-optimizer-controller --timeout 300s
  date -u +%FT%TZ > "$HERE/started_at"; echo "started $(cat "$HERE/started_at"), image $IMAGE";;
status)
  kubectl -n intelligent-optimizer-system get optimizerconfig,pods
  for ns in $ARMS; do echo "$ns: $(kubectl -n $ns get pods --no-headers | grep -c Running) running"; done
  kubectl get vpa -n ab-vpa --no-headers | head -3;;
collect)
  mkdir -p "$OUT"
  # Cloud Logging keeps the whole controller log; export the lines the analysis uses (scored decisions, raises,
  # cold-start queueing, uncertified bounds, skips and applied recommendations).
  gcloud logging read "resource.type=\"k8s_container\" AND resource.labels.cluster_name=\"$CLUSTER\" AND resource.labels.container_name=\"controller\" AND jsonPayload.message:(\"conformal decision scored\" OR \"Risk budget\" OR \"cold start\" OR \"Skipping\" OR \"Recommendation for\" OR \"exceeds the memory limit\")" \
    --freshness=6d --limit=3000000 --format=json > "$OUT/controller-full.json"
  for m in memory/used_bytes memory/request_bytes restart_count; do
    python3 "$ROOT/deploy/experiments/gke-ab/export_metrics.py" "$PROJECT" "$CLUSTER" "$(cat "$HERE/started_at")" "$m" \
      "$OUT/${m//\//_}.json" --ns-prefix ab- || echo "monitoring export failed for $m"
  done
  # The controller's own memory and CPU, to check that the store stays bounded.
  for m in memory/used_bytes cpu/core_usage_time restart_count; do
    python3 "$ROOT/deploy/experiments/gke-ab/export_metrics.py" "$PROJECT" "$CLUSTER" "$(cat "$HERE/started_at")" "$m" \
      "$OUT/controller_${m//\//_}.json" --ns-prefix intelligent-optimizer || echo "monitoring export failed for controller $m"
  done
  kubectl get events -A -o json > "$OUT/events.json"
  kubectl get vpa -n ab-vpa -o json > "$OUT/vpa.json"
  for ns in $ARMS; do kubectl -n $ns get pods,deploy,rs -o json > "$OUT/$ns.json"; done
  echo "$IMAGE" > "$OUT/image.txt"; cp "$HERE/started_at" "$OUT/"; echo "collected to $OUT";;
down)
  # Delete the run's PVC first: its persistent disk is otherwise left behind by the cluster delete.
  kubectl -n intelligent-optimizer-system delete pvc optimizer-backup --wait=false --ignore-not-found || true
  kubectl -n intelligent-optimizer-system delete deploy intelligent-optimizer-controller --ignore-not-found || true
  sleep 60
  gcloud container clusters delete "$CLUSTER" --zone "$ZONE" -q;;
*) echo "usage: $0 up|status|collect|down"; exit 1;;
esac
