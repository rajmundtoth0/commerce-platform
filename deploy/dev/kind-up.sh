#!/usr/bin/env bash
# Deploy the whole platform to a local kind (Kubernetes-in-Docker) cluster.
#
#   ./deploy/dev/kind-up.sh                 # plain run (chart-managed secrets)
#   WITH_ESO=1 DOPPLER_TOKEN=dp.st.dev.xxx ./deploy/dev/kind-up.sh
#                                           # full demo: External Secrets Operator
#                                           # (Doppler) + stakater/reloader
#
# Builds the two images, loads them into kind, then helm-installs the chart with
# the dev values (in-cluster Postgres + Valkey, single replicas).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

CLUSTER="${CLUSTER:-commerce}"
NS="${NAMESPACE:-commerce-dev}"
RELEASE="${RELEASE:-commerce}"
WITH_ESO="${WITH_ESO:-0}"
PY_IMAGE="commerce-platform-py:local"
UI_IMAGE="commerce-platform-ui:local"
EXTRA_VALUES=()

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

if [ "$WITH_ESO" = "1" ]; then
  : "${DOPPLER_TOKEN:?set DOPPLER_TOKEN to a Doppler service token for the 'dev' config}"
  echo "==> Installing External Secrets Operator + reloader"
  helm repo add external-secrets https://charts.external-secrets.io >/dev/null 2>&1 || true
  helm repo add stakater https://stakater.github.io/stakater-charts >/dev/null 2>&1 || true
  helm repo update >/dev/null
  helm upgrade --install external-secrets external-secrets/external-secrets \
    -n external-secrets --create-namespace --set installCRDs=true --wait
  helm upgrade --install reloader stakater/reloader \
    -n reloader --create-namespace --wait

  echo "==> Bootstrapping Doppler token Secret in $NS"
  kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -
  kubectl -n "$NS" create secret generic doppler-token \
    --from-literal=dopplerToken="$DOPPLER_TOKEN" \
    --dry-run=client -o yaml | kubectl apply -f -

  EXTRA_VALUES=(-f deploy/helm/commerce-platform/values-dev-eso.yaml)
  echo "==> ESO mode: secrets come from Doppler (config 'dev'); reloader auto-rolls on rotation"
fi

echo "==> helm upgrade --install ($RELEASE -> $NS)"
helm upgrade --install "$RELEASE" deploy/helm/commerce-platform \
  --namespace "$NS" --create-namespace \
  -f deploy/helm/commerce-platform/values.yaml \
  -f deploy/helm/commerce-platform/values-dev.yaml \
  "${EXTRA_VALUES[@]}" \
  --wait --timeout 5m

cat <<EOF

==> Deployed to kind cluster '$CLUSTER'. Reach the services with port-forwards:
  kubectl -n $NS port-forward svc/webshop-ui 5173:8080     # storefront
  kubectl -n $NS port-forward svc/webshop-api 8000:8000    # BFF /docs
  kubectl -n $NS port-forward svc/backoffice-api 8001:8001 # admin
  kubectl -n $NS port-forward svc/flower 5555:5555         # Celery monitor

After a code change:
  docker build -f docker/Dockerfile.python -t $PY_IMAGE .
  kind load docker-image $PY_IMAGE --name $CLUSTER
  kubectl -n $NS rollout restart deploy/webshop-api   # restart what changed

Tear down:
  helm -n $NS uninstall $RELEASE
  kind delete cluster --name $CLUSTER
EOF
