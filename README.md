# commerce-platform

A **service-oriented** commerce platform. Each service owns its data and exposes
an HTTP API; **Postgres (one database per owning service) is the source of
truth**, **Valkey holds versioned read projections**, and a **Celery worker**
rebuilds those projections from Postgres. A React storefront consumes a single
customer-facing BFF.

```
                         ┌────────────┐
  React UI ───────────▶  │ webshop-api│  (BFF: reads projections, owns no DB)
  (webshop-ui)           └─────┬──────┘
                               │ HTTP (+JWT)         ┌───────────┐
                               ├───────────────────▶ │ orders-api│─▶ orders DB
                               │                      └─────┬─────┘
   ┌───────────┐  admin        │ verify JWT                 │ enqueue
   │backoffice │──writes──▶ backoffice DB                   ▼
   │   -api    │──enqueue──┐                          ┌──────────┐
   └───────────┘           ▼                          │  Valkey  │ ◀── read projections
   ┌───────────┐    ┌────────────┐   rebuild from PG  │ dk:*:v1  │
   │  auth-api │    │   worker   │ ─────────────────▶ └──────────┘
   │  + DB     │    │ +beat+flwr │
   └───────────┘    └────────────┘
        ▲ issues JWT; every service verifies it (shared secret)
```

Live, verified end-to-end: admin creates a product in **backoffice-api** →
projection rebuild is enqueued → **worker** writes `dk:product:v1:{id}` and
`dk:product-price:v1:{id}` to **Valkey** → **webshop-api** serves the catalog
from those projections → cart (in Valkey) → checkout calls **orders-api** →
`dk:order-summary:v1:{id}` is rebuilt.

---

## Why service-oriented (not "pure microservices")

This is deliberately **service-oriented**, not a dogmatic microservices fleet:

- **Real boundaries where they matter.** Each service is an independent runtime
  unit — its own process, port, container, and **its own Postgres database**. No
  service reads another service's tables; they integrate over **HTTP + JWT** and
  an **async task queue**. That is the part that teaches ownership and blast-radius.
- **One repo, one shared library, one image where it's cheap.** Cross-cutting
  concerns (config, logging, telemetry, the Valkey/projection contracts, auth,
  the Celery app) live in a single installable `cplatform` library so services
  stay tiny and consistent. The Python services even share one Docker image and
  differ only by the command they run. This is honest about the trade-off:
  splitting into N repos and N pipelines buys independent release cadence at a
  real cost, and this project doesn't pretend to need it.
- **The seams are where the learning is.** Auth issued by one service and
  verified by all; orders owned by exactly one service and reached only via its
  API; a read model that is a *contract*, rebuildable from the source of truth.

In short: microservice **boundaries**, monorepo **ergonomics**. A production
split into separate repos/pipelines would not change the runtime topology.

## Service ownership boundaries

| Service | Owns | Database | Reads projections | Notes |
| --- | --- | --- | --- | --- |
| **auth-api** | users, credentials, tokens | `auth` | — | Issues JWTs; password hashing (bcrypt); roles (customer/admin); access + refresh tokens. |
| **orders-api** | orders, order items, status | `orders` | — | Status state machine + commands; no other service writes orders. Enqueues `order-summary` rebuilds. |
| **backoffice-api** | products, prices (authoritative) | `backoffice` | — | Admin API (all writes admin-gated) + SQLAdmin UI at `/admin/db`. Enqueues product/price rebuilds; exposes projection metadata. |
| **webshop-api** | nothing (BFF) | none | product, product-price, order-summary | Customer-facing. Cart in Valkey. Calls orders-api for checkout/status. |
| **worker** | nothing (platform) | reads backoffice+orders | writes all | Celery worker: per-entity rebuilds, nightly full rebuild, stale-key cleanup. Beat schedules; Flower monitors. |
| **status-api** | components, incidents, maintenance | `status` | — | Internal status page + ops API. Health collector; token-gated writes. See [docs/STATUS_PAGE.md](docs/STATUS_PAGE.md). |
| **webshop-ui** | — | — | via webshop-api only | React + TS + Vite storefront. |

**auth-api's role.** It is the only issuer of identity. Other services never
call it at request time — they verify the JWT locally with the shared secret
(`cplatform.auth`). This is the auth boundary: a service trusts a request
because the token validates, not because of where it came from. (Kept simple:
symmetric HS256, two roles — the point is to demonstrate the boundary, not build
a full IAM.)

**orders-api's ownership.** Orders, items, and the status state machine
(`created → paid → shipped`, `created|paid → cancelled`, `paid|shipped →
refunded`) live behind orders-api's API exclusively. webshop-api places and
reads orders by calling it (forwarding a minted customer token), never by
touching the orders database.

## Valkey projection strategy

Postgres is truth; **Valkey is a rebuildable read model**. Projection keys are an
explicit, **versioned contract** that consumers depend on *instead of* any
database schema:

```
dk:product:v1:{product_id}
dk:product-price:v1:{product_id}
dk:order-summary:v1:{order_id}

└┬┘ └───┬────┘ └┬┘ └────┬────┘
 ns    name    key ver  entity id
```

Each value is a self-describing envelope `{ "schema_version": N, "data": {…} }`.
The **key version** changes on a breaking key/identity change; the **schema
version** changes when the payload shape evolves. On read, a schema mismatch is
treated as a **miss** (counted `stale`) — a half-migrated cache degrades to
"rebuild needed" rather than serving payloads consumers can't parse.

`cplatform.contracts` defines the payload models + specs once; the worker writes
them (`SyncProjectionWriter`) and webshop-api reads them
(`AsyncProjectionReader`). One key layout, one envelope codec — producer and
consumer cannot drift.

**How projections stay fresh:**
1. On a write, the owning service **enqueues** a Celery task (e.g.
   `projections.rebuild_product`). Enqueue failures are logged but never fail the
   write — drift is expected and reconciled.
2. The worker reads the authoritative row and writes the projection. Rebuilding a
   deleted entity removes its key (self-healing).
3. **Beat** runs a nightly `rebuild_all` (clear + rebuild every family) and an
   hourly `cleanup_stale` (drop keys whose backing row is gone).
4. List `platform-admin projections` to see the registered contracts/versions.

Valkey is also the **Celery broker** (db 1) and **result backend** (db 2),
separate from the projection keyspace (db 0).

## Celery / Flower worker architecture

- **worker** — Celery worker consuming from Valkey. Tasks: `rebuild_product`,
  `rebuild_price`, `rebuild_order_summary`, `rebuild_all`, `cleanup_stale`.
  Producers enqueue **by task name** (`send_task`) and never import worker code —
  the queue is the contract.
- **beat** — Celery Beat scheduler (single replica) for the nightly rebuild and
  hourly cleanup.
- **flower** — Celery's monitoring UI (Horizon-like) at `:5555`.
- The worker exposes Prometheus metrics on `:9100` and emits structured logs with
  `task_id`.

## Repository layout

```
apps/
├── webshop-ui/        React + TS + Vite storefront (home+slider, PDP, cart, checkout)
├── webshop-api/       FastAPI BFF (catalog from projections, Valkey cart, checkout)
├── backoffice-api/    FastAPI admin API + SQLAdmin (authoritative products/prices)
├── auth-api/          FastAPI auth (users, login, JWT, refresh, roles)
├── orders-api/        FastAPI orders (state machine, commands)
└── worker/            Celery worker + beat tasks
libs/platform/cplatform/   shared library (config, logging, telemetry, valkey,
                           projections, db, auth, celery_app, http, middleware,
                           ops, metrics, errors, contracts, service factory)
deploy/helm/commerce-platform/   one chart, all services (values-driven)
deploy/argocd/                   ArgoCD Application
docker/                          Dockerfile.python (all services), Dockerfile.ui
infra/postgres/init.sql          creates auth/orders/backoffice databases
tests/                           hermetic tests for every service (37 tests)
```

> The shared library package is named `cplatform` (not `platform`) to avoid
> shadowing Python's stdlib `platform` module.

## Local development

```bash
docker compose up --build
```

Brings up Postgres (3 databases), Valkey, runs migrations per service, then all
services + worker + beat + flower + UI.

| URL | Service |
| --- | --- |
| http://localhost:5173 | webshop-ui (storefront) |
| http://localhost:8000/docs | webshop-api (BFF) |
| http://localhost:8001/docs | backoffice-api (admin; SQLAdmin at `/admin/db`) |
| http://localhost:8002/docs | auth-api |
| http://localhost:8003/docs | orders-api |
| http://localhost:8004 | status-api (internal status page; `/docs` for API) |
| http://localhost:5555 | Flower |
| http://localhost:5602 | Kibana (only with `--profile elk`) |

> Centralized logging is opt-in to keep normal runs light. Start it with
> `docker compose --profile elk up -d` (adds Elasticsearch on host `:9201`,
> Kibana on `:5602`, and a Filebeat shipper). See [Observability](#observability).

A seed admin (`admin@example.com` / `admin12345`) is created by auth-api on
startup. Quick tour:

```bash
ADMIN=$(curl -s -X POST localhost:8002/auth/login -H 'content-type: application/json' \
  -d '{"email":"admin@example.com","password":"admin12345"}' | jq -r .access_token)
# Create a featured product + price (backoffice-api, admin-gated)
PID=$(curl -s -X POST localhost:8001/products -H "authorization: Bearer $ADMIN" \
  -H 'content-type: application/json' \
  -d '{"sku":"DEMO-1","name":"Widget","featured":true}' | jq -r .id)
curl -s -X PUT localhost:8001/products/$PID/price -H "authorization: Bearer $ADMIN" \
  -H 'content-type: application/json' -d '{"currency":"USD","amount_minor":4999}'
# The worker rebuilds the projections; the storefront now shows it:
curl -s localhost:8000/catalog/featured | jq
```

### Running without containers

Requires Python 3.12+, Node 22+, a Postgres and a Valkey/Redis. Install with
[`uv`](https://docs.astral.sh/uv/):

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"          # installs platform + all services (one dist)
cp .env.example .env
# migrate each owning DB, then run a service:
(cd apps/auth-api && alembic upgrade head)
uvicorn auth_api.main:app --port 8002
# worker:
celery -A worker.celery_app worker -l info
```

## Database migrations

Each owning service has its **own** Alembic environment (`apps/<svc>/alembic`,
sync engine via `psycopg`) and migration history — databases are never shared.

```bash
cd apps/orders-api
alembic upgrade head
alembic revision --autogenerate -m "add field"
```

In Docker Compose, one-shot `migrate-*` services run before each API starts. In
Kubernetes, a single pre-install/upgrade **Job** runs all three in turn.

## Observability

Every service is observable from day one:

- **Structured JSON logs** (`structlog`). Each line carries `service`,
  `request_id`, `trace_id`, and — in the worker — `task_id`. Projection writes
  add `domain`, `projection_key`, `projection_version`. Inbound `X-Request-ID` is
  honoured and echoed so correlation crosses service boundaries.
- **Prometheus metrics** at `/metrics` (and `:9100` for the worker), labeled by
  `service`:
  - `http_requests_total{method,path,status}`, `http_request_duration_seconds`
  - `celery_task_duration_seconds`, `celery_task_failures_total`
  - `projection_writes_total{domain,result}`,
    `projection_reads_total{domain,result=hit|miss|stale}`,
    `projection_rebuilds_total{domain,result}`
- **OpenTelemetry** tracing for FastAPI, SQLAlchemy, Valkey, and Celery tasks.
  Spans are always created; OTLP export is enabled only when
  `OTEL_EXPORTER_OTLP_ENDPOINT` is set.
- **Health**: `/health` (liveness) and `/ready` (probes Postgres/Valkey, returns
  503 when a dependency is down).

### Centralized logging (ELK)

The same structured JSON logs are shipped to **Elasticsearch** and explored in
**Kibana**. The shipper is **Filebeat** — there is intentionally **no Logstash**:
because the app already emits JSON, a Filebeat `decode_json_fields` step parses
each line into top-level fields (`service`, `level`, `request_id`, `trace_id`,
`domain`, `projection_key`, …), so search/filter/aggregate works out of the box.
Only records carrying a `service` field are kept (plain-text/uvicorn noise is
dropped).

Architectural split (the part that matters): the **collector is always
in-cluster** (a Filebeat DaemonSet, one per node), while the **storage tier**
(Elasticsearch + Kibana) is in-cluster only for dev and **managed/external** for
uat/stg/prd — heavy, stateful Elasticsearch shouldn't share a failure/resource
domain with the app in production.

| Env | Filebeat | Elasticsearch / Kibana | Index |
| --- | --- | --- | --- |
| **local (compose)** | container (autodiscover by image) | `elasticsearch`/`kibana` containers (`--profile elk`) | `commerce-logs-YYYY.MM.DD` |
| **dev** | DaemonSet | in-cluster single-node (demo) | `commerce-logs-*` |
| **uat/stg/prd** | DaemonSet | **managed** (`elk.elasticsearch.host` + Kibana off) | `commerce-logs-<env>-*` |

```bash
# Local: bring up logging alongside the stack
docker compose --profile elk up -d
open http://localhost:5602          # Kibana — create a data view "commerce-logs-*"
curl 'localhost:9201/_cat/indices/commerce-logs-*?v'
```

In Kubernetes it's a Helm toggle (`elk.enabled`, off by default):
`elk.inCluster=true` deploys a demo Elasticsearch+Kibana (dev); otherwise the
Filebeat DaemonSet ships to `elk.elasticsearch.host` (per-env values). Because
every log line carries `trace_id`, you can pivot log ↔ trace across Kibana and
your OTel backend.

## CI/CD flow

GitHub Actions (`.github/workflows/ci.yml`):

1. **python** — install (`uv`), `ruff check`, `ruff format --check`, `mypy
   --strict`, `pytest` (hermetic: SQLite + fakeredis, no services needed).
2. **ui** — `npm ci`, `npm run lint`, `npm run build`.
3. **helm** — `helm lint` + `helm template`.
4. **images** — build the Python and UI images with Buildx layer cache.

To ship, push the images to a registry and bump `global.image.*Tag` in git —
ArgoCD takes it from there.

## Kubernetes deployment (Helm + ArgoCD)

One Helm chart deploys everything; the `services` map in `values.yaml` is the
source of truth (each entry → a Deployment, plus a Service if it exposes a port).
Configurable: image repos/tags, replica counts, per-service env, Postgres/Valkey
connection settings (inline or via existing Secrets), resource requests/limits,
and liveness/readiness probes. A pre-install/upgrade Job runs all migrations.

```bash
helm lint deploy/helm/commerce-platform
helm template commerce deploy/helm/commerce-platform | less
helm upgrade --install commerce deploy/helm/commerce-platform \
  -n commerce --create-namespace \
  --set global.image.pyTag=v0.2.0 --set global.image.uiTag=v0.2.0 \
  --set postgres.enabled=false --set valkey.enabled=false \
  --set global.postgres.host=my-pg --set global.postgres.existingSecret=commerce-postgres
```

In-cluster Postgres/Valkey (`postgres.enabled` / `valkey.enabled`) are for demos;
point `global.postgres` / `global.valkey` at managed instances for production.

### Environments

Four environments, each a base `values.yaml` + an environment overlay
(`values-<env>.yaml`) and an ArgoCD `Application` (`deploy/argocd/<env>.yaml`):

| Env | Cluster | Postgres / Valkey | Image tag | Replicas | Argo sync |
| --- | --- | --- | --- | --- | --- |
| **dev** | local **minikube** | in-cluster (demo) | `:local` (loaded into minikube) | 1 each | auto |
| **uat** | TBD (real) | managed (existing Secrets) | `:uat` | modest | auto |
| **stg** | TBD (real) | managed | `:stg` | ~prd shape | auto |
| **prd** | TBD (real) | managed | pinned `:0.2.0` | 2–3 | **manual** (pinned git tag) |

dev is wired to run **now**; uat/stg/prd render to valid manifests and are ready
to point at clusters when they exist (fill the host/secret placeholders in their
`values-<env>.yaml`).

**stg on Scaleway** has a complete path: Terraform (`deploy/terraform/stg` —
Kapsule + managed Postgres + managed Redis + Container Registry), a chart Ingress
(Scaleway LB + cert-manager TLS), and TLS-ready DSNs. See the runbook:
[docs/DEPLOY_SCALEWAY.md](docs/DEPLOY_SCALEWAY.md).

**Secrets** use **Doppler** as the source of truth, delivered per-runtime:
`doppler run` locally, and the **External Secrets Operator** (+ stakater/reloader
for rotation) in Kubernetes — syncing into the same `existingSecret` the chart
already reads, so it's backend-swappable (Doppler ↔ Scaleway SM ↔ Vault). Demo it
locally with `WITH_ESO=1 DOPPLER_TOKEN=... ./deploy/dev/kind-up.sh`. See
[docs/SECRETS.md](docs/SECRETS.md).

**dev — local minikube (works today):**

```bash
./deploy/dev/minikube-up.sh     # builds images, loads them into minikube, helm installs
# then port-forward, e.g.:
kubectl -n commerce-dev port-forward svc/webshop-ui 5173:80
```

Or directly: `helm upgrade --install commerce deploy/helm/commerce-platform
-f deploy/helm/commerce-platform/values.yaml
-f deploy/helm/commerce-platform/values-dev.yaml -n commerce-dev --create-namespace`.

**GitOps with ArgoCD (per environment):**

```bash
kubectl apply -n argocd -f deploy/argocd/uat.yaml   # or dev.yaml / stg.yaml / prd.yaml
```

Each Application points at the chart with `valueFiles: [values.yaml,
values-<env>.yaml]`. dev/uat/stg auto-sync from `master`; **prd is manual and
pinned to an immutable git tag** so a human promotes releases.

Flow: **push images → bump tag in the env overlay (or the prd Application's
`targetRevision`) → ArgoCD syncs → migration Job runs → Deployments roll out →
readiness probes gate traffic.**

## Engineering principles

- Service boundaries are real (own DB, own API); integration is HTTP + queue.
- Postgres is truth; Valkey is a rebuildable read model.
- Projection keys are versioned contracts; consumers depend on them, not schemas.
- Failure modes are visible (logged + metered), never silently swallowed.
- Observable and deployable from day one.
- Kept simple enough to finish, structured enough to show senior judgment.
