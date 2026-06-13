# commerce-platform

A frontend-agnostic commerce API. **Postgres is the source of truth**; **Redis holds
versioned, rebuildable read projections**. The HTTP API is consumable by React, Vue,
mobile apps, CLIs, or any HTTP client.

The project is deliberately small but production-shaped: clean module boundaries, an
explicit write-model → read-projection seam, first-class observability, and a complete
local-to-Kubernetes deployment path.

```
HTTP client ──► FastAPI ──► Service (write model) ──► Postgres   (source of truth)
                   │                  │
                   │                  └── domain event ──► Projection writer ──► Redis
                   │                                                              (read model)
                   └── GET reads ◄──────────────────────────────────────────────┘
                                         (fall back to Postgres + backfill on miss)
```

---

## Table of contents

- [Architecture](#architecture)
- [Module layout](#module-layout)
- [Projection design & Redis key strategy](#projection-design--redis-key-strategy)
- [Local setup](#local-setup)
- [Database migrations](#database-migrations)
- [Rebuilding projections](#rebuilding-projections)
- [Observability](#observability)
- [Testing, linting, type safety](#testing-linting-type-safety)
- [CI/CD flow](#cicd-flow)
- [Kubernetes deployment path (Helm + ArgoCD)](#kubernetes-deployment-path-helm--argocd)
- [API surface](#api-surface)
- [Engineering principles](#engineering-principles)

---

## Architecture

Two models, one clear boundary:

- **Write model (authoritative).** All mutations go through a per-domain *service* that
  owns business rules and persists to Postgres. Services know nothing about HTTP.
- **Read model (projections).** After a successful write, a service publishes a **domain
  event** carrying a self-contained snapshot. A **projection writer** subscribes and
  updates Redis. The public read endpoints serve from Redis and fall back to Postgres on a
  miss, lazily backfilling the cache.

Redis is never the source of truth. Every projection can be fully reconstructed from
Postgres by the rebuild job, so a Redis flush, a schema bump, or cache drift is always
recoverable.

The event bus (`app/shared/events.py`) is intentionally in-process and broker-free. A
projection write failing is **logged and counted as a metric but never rolls back the
authoritative write** — drift is expected and repaired by the rebuild job. This keeps
failure modes visible instead of hidden.

> **Consistency note.** Events fire inside the request transaction, so there is a small
> window where Redis can be updated just before the Postgres commit. This is an
> intentional trade-off for a *read model*: reads are allowed to be slightly stale or
> momentarily ahead, and the rebuild job is the reconciliation backstop. If strict
> read-after-write on the cache were required, you would move publication to an
> after-commit hook or an outbox.

## Module layout

```
app/
├── main.py                 # composition root: app factory, middleware, handlers, wiring
├── models.py               # imports every ORM model so Base.metadata is complete
├── bootstrap.py            # wires projection writers to the bus + the rebuild registry
├── core/
│   ├── config.py           # pydantic-settings; the only reader of the environment
│   ├── database.py         # async engine, session dependency, declarative Base
│   ├── redis.py            # async Redis client (read-model cache)
│   ├── logging.py          # structured JSON logs + request/trace id context
│   ├── telemetry.py        # OpenTelemetry for FastAPI / SQLAlchemy / Redis
│   ├── metrics.py          # Prometheus metrics (HTTP + projections)
│   ├── middleware.py       # request-id correlation + metrics middleware
│   └── health.py           # /health, /ready, /metrics
├── modules/
│   ├── products/           # CRUD, authoritative in Postgres, projection: dk:product:v1
│   ├── pricing/            # price per product,          projection: dk:product-price:v1
│   ├── cart/               # cart writes in PG; cart *view* assembled from projections
│   ├── orders/            # checkout snapshots the priced cart into an immutable order
│   └── users/             # plain Postgres CRUD — deliberately has no projection
├── shared/
│   ├── events.py           # typed in-process event bus
│   ├── exceptions.py       # domain error hierarchy -> HTTP via one handler
│   ├── projection.py       # RedisProjection base: versioned keys + schema envelope
│   ├── dto.py              # APIModel, Page[T], ErrorResponse
│   └── deps.py             # shared FastAPI dependencies
└── cli/
    └── main.py             # `commerce` CLI: rebuild / list-projections
```

Each module is self-contained: `models.py` (write model), `schemas.py` (API DTOs +
projection payload), `service.py` (use cases), `projections.py` (writer + event
subscriptions), `router.py` (HTTP). `users` shows a module that needs *no* projection —
boundaries are explicit, projections are added only where a read path warrants one.

## Projection design & Redis key strategy

Projection keys are a **contract** that read consumers may depend on, so both the key
layout and the payload are versioned:

```
dk:product:v1:{product_id}
dk:product-price:v1:{product_id}

└┬┘ └──┬───┘ └┬┘ └────┬─────┘
 │     │      │       └ entity id
 │     │      └ key version  (changes on a breaking key/identity change)
 │     └ projection name
 └ namespace ("dk")
```

Each value is a **self-describing envelope**:

```json
{ "schema_version": 1, "data": { "id": "…", "sku": "…", "name": "…", "active": true } }
```

- **Key version** (in the key) changes when the key layout or identity changes — a
  breaking change for consumers, so old and new coexist under different prefixes.
- **Schema version** (in the envelope) changes when the payload shape evolves. On read,
  a mismatch is treated as a **miss** (counted as `stale`) rather than served as garbage,
  so a half-migrated cache degrades safely to "rebuild needed".

`app/shared/projection.py` is the single place that builds keys, (de)serializes the
envelope, and emits metrics. Both the event-driven writers and the full-rebuild job use
the *same* `write()` path — there is exactly one way a projection is produced.

## Local setup

### With Docker Compose (recommended)

```bash
docker compose up --build
# Postgres + Redis start, migrations run once, then the API comes up.
curl localhost:8000/health
open http://localhost:8000/docs        # interactive OpenAPI UI
```

### Without containers

Requires Python 3.12+, plus a local Postgres and Redis. [`uv`](https://docs.astral.sh/uv/)
is recommended but any venv + pip works.

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

cp .env.example .env          # adjust POSTGRES_DSN / REDIS_URL as needed
alembic upgrade head          # create the schema
uvicorn app.main:app --reload
```

Configuration is 12-factor — see `.env.example` and `app/core/config.py`. Postgres DSNs
must use the async driver, e.g. `postgresql+asyncpg://user:pass@host:5432/db`.

## Database migrations

[Alembic](https://alembic.sqlalchemy.org/) with an **async** env; the database URL is
sourced from app settings so there is one connection source of truth.

```bash
alembic upgrade head                       # apply migrations
alembic revision --autogenerate -m "msg"   # generate a new migration from model changes
alembic downgrade -1                        # roll back one revision
```

`app/models.py` imports every model so `Base.metadata` is fully populated for
autogenerate. Constraint/index names use a stable naming convention
(`app/core/database.py`) for deterministic migrations.

## Rebuilding projections

The read model is disposable. Rebuild every Redis projection from Postgres at any time:

```bash
commerce rebuild               # local CLI
docker compose run --rm api rebuild
kubectl exec deploy/commerce-platform -- commerce rebuild   # or run as a Job
```

Run it after a key/schema version bump, a Redis flush, or any suspected drift. Rebuilding
clears each projection family and rewrites it from the authoritative rows (orphaned keys
with no backing row are removed). Add a new projection by implementing a `RedisProjection`
subclass and registering a `Rebuilder` in `app/bootstrap.py`.

## Observability

Observable from day one:

- **Structured JSON logs** (`structlog`). Every line is one JSON object and automatically
  carries `request_id` and `trace_id` via context vars. Inbound `X-Request-ID` is honored
  (and echoed) so correlation survives across services.
- **Prometheus metrics** at `GET /metrics`:
  - `http_requests_total{method,path,status}`, `http_request_duration_seconds`
  - `projection_writes_total{domain,result}` (`ok`/`error`)
  - `projection_reads_total{domain,result}` (`hit`/`miss`/`stale`)
  - `projection_rebuilds_total{domain,result}`

  HTTP metrics are labeled by **route template** (`/products/{product_id}`), not raw path,
  to avoid cardinality blow-up.
- **OpenTelemetry tracing** for FastAPI, SQLAlchemy, and Redis. Spans are always created;
  the OTLP exporter is attached only when `OTEL_EXPORTER_OTLP_ENDPOINT` is set, so local
  and test runs need no collector.
- **Health endpoints**: `GET /health` (liveness, cheap) and `GET /ready` (readiness;
  probes Postgres and Redis and returns `503` when a dependency is down so Kubernetes
  stops routing to the pod).

## Testing, linting, type safety

The test suite is **hermetic** — no Postgres or Redis required. Tests run against a
temp-file SQLite database (async, via `aiosqlite`) and `fakeredis`, while exercising the
real services, routers, projection writers, and event wiring.

```bash
pytest                 # unit + API + projection tests with coverage
ruff check .           # lint
ruff format --check .  # formatting
mypy .                 # strict static typing on app/ (tests/alembic relaxed)
```

- **Ruff** for linting (pyflakes, isort, bugbear, pyupgrade, async checks) and formatting.
- **mypy `--strict`** on application code, with the Pydantic plugin.
- **pytest** (`pytest-asyncio`) covering API endpoints, services + event-driven
  projection updates, the projection key/version contract, and the full rebuild path.

## CI/CD flow

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and PR:

1. **quality** — install deps (`uv`), `ruff check`, `ruff format --check`, `mypy`, `pytest`.
2. **docker** — build the production image with Buildx + layer cache (no push by default).

To publish, add a registry login and `push: true` (or a `release` workflow) and tag the
image. The same image serves the API (`api`), runs migrations (`migrate`), and runs the
projection rebuild (`rebuild`) via the entrypoint subcommand.

## Kubernetes deployment path (Helm + ArgoCD)

A Helm chart lives in [`deploy/helm/commerce-platform`](deploy/helm/commerce-platform) and
an ArgoCD `Application` in [`deploy/argocd`](deploy/argocd).

The chart is configurable: image repository/tag, replica count, env vars, Postgres/Redis
connection settings (via plain values or an existing `Secret`), resource requests/limits,
and liveness/readiness probes wired to `/health` and `/ready`. A pre-install/pre-upgrade
**migration Job** (`migrate`) runs Alembic before the new pods roll out.

```bash
# Render / install directly with Helm
helm lint deploy/helm/commerce-platform
helm template commerce deploy/helm/commerce-platform | less
helm upgrade --install commerce deploy/helm/commerce-platform \
  --namespace commerce --create-namespace \
  --set image.repository=ghcr.io/you/commerce-platform \
  --set image.tag=v0.1.0 \
  --set env.POSTGRES_DSN="postgresql+asyncpg://commerce:pass@pg:5432/commerce" \
  --set env.REDIS_URL="redis://redis:6379/0"
```

**GitOps with ArgoCD.** Point the `Application` at your fork/branch; ArgoCD renders the
chart and keeps the cluster in sync with git:

```bash
kubectl apply -n argocd -f deploy/argocd/application.yaml
```

Flow: **push image → bump `image.tag` in values (git) → ArgoCD syncs → migration Job runs
→ Deployment rolls out → readiness probe gates traffic.**

## API surface

All endpoints are under `/api/v1`. Highlights:

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/products` | create (writes PG, publishes event) |
| `GET` | `/products/{id}` | **reads `dk:product:v1` projection**, PG fallback + backfill |
| `PATCH` / `DELETE` | `/products/{id}` | update / delete |
| `PUT` | `/products/{id}/price` | set price (integer minor units) |
| `GET` | `/products/{id}/price` | **reads `dk:product-price:v1` projection** |
| `POST` | `/users` | create user |
| `POST` | `/users/{id}/cart/items` | add to cart; view assembled from projections |
| `GET` | `/users/{id}/cart` | priced cart view; flags unpriced lines |
| `POST` | `/users/{id}/orders` | checkout: snapshot prices into an immutable order |
| `GET` | `/health`, `/ready`, `/metrics` | ops |

Interactive docs at `/docs`. Errors share one envelope:
`{ "code", "message", "details", "request_id" }`.

## Engineering principles

- Explicit, simple modules; clear boundaries over framework magic.
- Write model and read projections are separate by design.
- Projection keys are a versioned contract.
- Failure modes are visible (logged + metered), not silently swallowed.
- Observable from day one; deployable from day one.
- Optimized for maintainability, deployability, and operational clarity.
