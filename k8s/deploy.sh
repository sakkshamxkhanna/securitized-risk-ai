#!/usr/bin/env bash
# One-command local deployment: builds the image, loads it into the kind
# cluster (kind nodes do not share the host docker image store), applies
# manifests, and waits for readiness.
set -euo pipefail

CLUSTER="securitized-risk"
NS="securitized-risk"
IMAGE="securitized-risk-ai:local"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

step() { printf "\n\033[1;34m==> %s\033[0m\n" "$1"; }

step "Ensuring kind cluster '$CLUSTER' exists"
if ! kind get clusters 2>/dev/null | grep -qx "$CLUSTER"; then
  kind create cluster --config "$ROOT/k8s/kind-cluster.yaml"
else
  echo "cluster already exists"
fi
kubectl config use-context "kind-$CLUSTER" >/dev/null

step "Building image $IMAGE"
docker build -f "$ROOT/docker/Dockerfile" -t "$IMAGE" "$ROOT"

step "Loading image into kind"
kind load docker-image "$IMAGE" --name "$CLUSTER"

step "Applying manifests"
kubectl apply -f "$ROOT/k8s/00-namespace.yaml"
kubectl apply -f "$ROOT/k8s/01-config.yaml"
kubectl apply -f "$ROOT/k8s/02-redis.yaml"
kubectl apply -f "$ROOT/k8s/04-surveillance-cronjob.yaml"
kubectl apply -f "$ROOT/k8s/05-report-server.yaml"

step "Waiting for Redis"
kubectl -n "$NS" rollout status deploy/redis --timeout=180s

step "Waiting for report server"
kubectl -n "$NS" rollout status deploy/report-server --timeout=180s

step "Cluster state"
kubectl -n "$NS" get all

cat <<EOF

Deployed.

  Trigger a surveillance run:
    kubectl -n $NS create job --from=cronjob/monthly-surveillance run-\$(date +%s)

  Follow the run:
    kubectl -n $NS logs -f -l app=surveillance --tail=100

  View the report:
    open http://localhost:30080

EOF
