# Deploying staging to Scaleway (fr-par)

End-to-end runbook for standing up the **stg** environment on Scaleway. Nothing
here provisions automatically — you run Terraform and ArgoCD yourself.

## What gets created

| Component | Scaleway product | Defined in |
| --- | --- | --- |
| Kubernetes | Kapsule cluster + node pool | `deploy/terraform/stg` |
| Postgres (auth/orders/backoffice DBs) | Managed Database for PostgreSQL | `deploy/terraform/stg` |
| Valkey/Redis (TLS) | Managed Database for Redis | `deploy/terraform/stg` |
| Image registry | Container Registry | `deploy/terraform/stg` |
| Elasticsearch + Kibana | **in-cluster** (no managed ES on Scaleway) | Helm `elk.inCluster=true` |
| Ingress + TLS | Scaleway LB (ingress-nginx) + cert-manager | Helm `ingress.*` |
| Workloads | the Helm chart | `deploy/helm/commerce-platform` + `values-stg.yaml` |

## 0. Prerequisites

```bash
# Scaleway CLI + API keys (IAM -> API keys)
export SCW_ACCESS_KEY=...  SCW_SECRET_KEY=...  SCW_DEFAULT_PROJECT_ID=...
# tools: terraform >=1.6, kubectl, helm, scw
```

## 1. Provision infrastructure (Terraform)

```bash
cd deploy/terraform/stg
cp terraform.tfvars.example terraform.tfvars   # set project_id, pg_password, redis_password
terraform init
terraform apply
# capture outputs you'll need:
terraform output registry_endpoint
terraform output postgres_host
terraform output postgres_port
terraform output redis_id           # then: scw redis cluster get <id>  -> host:port
terraform output -raw kubeconfig > $HOME/.kube/commerce-stg.yaml
export KUBECONFIG=$HOME/.kube/commerce-stg.yaml
kubectl get nodes
```

## 2. Cluster add-ons

```bash
# Ingress controller (provisions a Scaleway Load Balancer)
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx -n ingress-nginx --create-namespace

# cert-manager + a Let's Encrypt ClusterIssuer named `letsencrypt-prod`
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager -n cert-manager --create-namespace \
  --set crds.enabled=true
# (apply your ClusterIssuer; HTTP-01 via the nginx class, or DNS-01 via Scaleway)

# ArgoCD
kubectl create ns argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

Point DNS: create A records for `shop.stg.example.com` / `api.stg.example.com`
at the ingress LoadBalancer's external IP (`kubectl -n ingress-nginx get svc`).

## 3. Secrets — Doppler + External Secrets Operator

stg/prd use **ESO** (Doppler backend): the chart syncs `commerce-jwt` /
`commerce-postgres` from Doppler. Full details in [docs/SECRETS.md](SECRETS.md).

```bash
# operators (once per cluster)
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets \
  -n external-secrets --create-namespace --set installCRDs=true
helm repo add stakater https://stakater.github.io/stakater-charts
helm install reloader stakater/reloader -n reloader --create-namespace

# bootstrap "secret zero": the Doppler service token for the stg config
kubectl create ns commerce-stg
kubectl -n commerce-stg create secret generic doppler-token \
  --from-literal=dopplerToken=dp.st.stg.xxxxxxxx
```
Put `JWT_SECRET` and `POSTGRES_PASSWORD` (matching the Terraform `pg_password`) in
the Doppler `stg` config — ESO materializes the k8s Secrets, and Reloader
rolling-restarts pods when they rotate. `values-stg.yaml` already sets
`externalSecrets.enabled` + `reloader.enabled`.

> Quick alternative without Doppler: create the two Secrets directly —
> `kubectl -n commerce-stg create secret generic commerce-jwt --from-literal=JWT_SECRET=...`
> and `commerce-postgres --from-literal=POSTGRES_PASSWORD=...` — and set
> `externalSecrets.enabled=false`.
>
> For full single-cloud/EU, swap ESO's `SecretStore` provider to Scaleway Secret
> Manager — the ExternalSecrets and chart stay identical.

## 4. Wire `values-stg.yaml`

Fill the `<...>` placeholders in
`deploy/helm/commerce-platform/values-stg.yaml` from the Terraform outputs:
- `global.image.*Repository` → `registry_endpoint` (`rg.fr-par.scw.cloud/<ns>/...`)
- `global.postgres.host` → `postgres_host`
- `global.valkey.*` → `rediss://<redis-host>:6379/<db>` (managed Redis is TLS)
- `ingress.hosts[*].host` → your real DNS names

The chart already sets `postgres.enabled=false`, `valkey.enabled=false`,
`postgres.dsnParams="?ssl=require"`, and `elk.inCluster=true` for stg.

## 5. Build & push images

Either run the manual workflow **Release to staging (Scaleway)**
(`.github/workflows/release-stg.yml`, needs repo var `SCW_REGISTRY_ENDPOINT` +
secret `SCW_SECRET_KEY`), or locally:

```bash
docker login rg.fr-par.scw.cloud -u nologin -p "$SCW_SECRET_KEY"
REG=$(cd deploy/terraform/stg && terraform output -raw registry_endpoint)
docker build -f docker/Dockerfile.python -t $REG/commerce-platform-py:stg .
docker build -f docker/Dockerfile.ui     -t $REG/commerce-platform-ui:stg .
docker push $REG/commerce-platform-py:stg
docker push $REG/commerce-platform-ui:stg
```

## 6. Deploy via ArgoCD

```bash
kubectl apply -n argocd -f deploy/argocd/stg.yaml
# ArgoCD renders the chart with values.yaml + values-stg.yaml into commerce-stg,
# runs the post-install migration Job (waits for managed PG, migrates, seeds admin),
# then rolls out all services. Watch:
kubectl -n commerce-stg get pods -w
```

Smoke once DNS + TLS resolve:
```bash
curl -fsS https://api.stg.example.com/health
open https://shop.stg.example.com
```

## Notes & trade-offs
- **No managed Elasticsearch on Scaleway** → ES + Kibana run in-cluster for stg.
  For prod, run the ECK operator with persistent volumes (or ship to Elastic Cloud).
- **Managed PG/Redis require TLS** → DSNs use `?ssl=require` and `rediss://`.
- The in-cluster demo Postgres/Valkey deployments are **disabled** for stg/prd.
- Keep node pool small (`PLAY2-NANO` ×2) for a cheap staging footprint; scale via
  `node_pool_max` and per-service `replicas` in `values-stg.yaml`.
