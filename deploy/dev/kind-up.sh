#!/usr/bin/env bash
# Deploy the whole platform to a local kind (Kubernetes-in-Docker) cluster.
#
#   ./deploy/dev/kind-up.sh
#
# Creates a kind cluster, builds the two images, loads them into the cluster
# (kind nodes can't see the host's Docker images otherwise), then helm-installs
# the chart with the dev values (in-cluster Postgres + Valkey, single replicas).
#
# kind is the upstream Kubernetes project's own tool and the de-facto standard in
# CI, so local here matches the CI deploy-smoke job (.github/workflows/ci.yml).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

CLUSTER="${CLUSTER:-commerce}"
NS="${NAMESPACE:-commerce-dev}"
RELEASE="${RELEASE:-commerce}"
PY_IMAGE="commerce-platform-py:local"
UI_IMAGE="commerce-platform-ui:local"

echo "==> Ensuring kind cluster '$CLUSTER' exists"
if ! kind get clusters | grep -qx "$CLUSTER"; then
  kind create cluster --name "$CLUSTER"
fi
kubectl config use-context "kind-${CLUSTER}"

echo "==> Building images"
docker build -f docker/Dockerfile.python -t "$PY_IMAGE" .
docker build -f docker/Dockerfile.ui -t "$UI_IMAGE" .

echo "==> Loading images into kind (must re-run after every rebuild)"
kind load docker-image "$PY_IMAGE" --name "$CLUSTER"
kind load docker-image "$UI_IMAGE" --name "$CLUSTER"

echo "==> helm upgrade --install ($RELEASE -> $NS)"
helm upgrade --install "$RELEASE" deploy/helm/commerce-platform \
  --namespace "$NS" --create-namespace \
  -f deploy/helm/commerce-platform/values.yaml \
  -f deploy/helm/commerce-platform/values-dev.yaml \
  --wait --timeout 5m

cat <<EOF

==> Deployed to kind cluster '$CLUSTER'. Reach the services with port-forwards:
  kubectl -n $NS port-forward svc/webshop-ui 5173:80      # storefront
  kubectl -n $NS port-forward svc/webshop-api 8000:8000   # BFF /docs
  kubectl -n $NS port-forward svc/backoffice-api 8001:8001 # admin
  kubectl -n $NS port-forward svc/flower 5555:5555        # Celery monitor

After a code change:
  docker build -f docker/Dockerfile.python -t $PY_IMAGE .
  kind load docker-image $PY_IMAGE --name $CLUSTER
  kubectl -n $NS rollout restart deploy/webshop-api   # restart what changed

Tear down:
  helm -n $NS uninstall $RELEASE
  kind delete cluster --name $CLUSTER
EOF
