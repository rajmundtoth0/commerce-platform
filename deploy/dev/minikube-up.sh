#!/usr/bin/env bash
# Deploy the whole platform to a local minikube cluster.
#
#   ./deploy/dev/minikube-up.sh
#
# Builds the two images, loads them into minikube (so no registry is needed),
# then helm-installs the chart with the dev values into the `commerce-dev`
# namespace (in-cluster Postgres + Valkey, single replicas).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

NS="${NAMESPACE:-commerce-dev}"
RELEASE="${RELEASE:-commerce}"
PY_IMAGE="commerce-platform-py:local"
UI_IMAGE="commerce-platform-ui:local"

echo "==> Ensuring minikube is running"
minikube status >/dev/null 2>&1 || minikube start

echo "==> Building images"
docker build -f docker/Dockerfile.python -t "$PY_IMAGE" .
docker build -f docker/Dockerfile.ui -t "$UI_IMAGE" .

echo "==> Loading images into minikube"
minikube image load "$PY_IMAGE"
minikube image load "$UI_IMAGE"

echo "==> helm upgrade --install ($RELEASE -> $NS)"
helm upgrade --install "$RELEASE" deploy/helm/commerce-platform \
  --namespace "$NS" --create-namespace \
  -f deploy/helm/commerce-platform/values.yaml \
  -f deploy/helm/commerce-platform/values-dev.yaml \
  --wait --timeout 5m

cat <<EOF

==> Deployed. Reach the services with port-forwards:
  kubectl -n $NS port-forward svc/webshop-ui 5173:80      # storefront
  kubectl -n $NS port-forward svc/webshop-api 8000:8000   # BFF /docs
  kubectl -n $NS port-forward svc/backoffice-api 8001:8001 # admin
  kubectl -n $NS port-forward svc/flower 5555:5555        # Celery monitor

Tear down:  helm -n $NS uninstall $RELEASE
EOF
