# Internal status page (status-api)

A small internal operations service: component health, incidents, and planned
maintenance, behind a boring cards UI and a clean JSON API. It demonstrates how
application health, incidents, maintenance, secrets, Kubernetes, and observability
fit together — intentionally simple (no PagerDuty/Statuspage, no graphs, no
accounts).

## Purpose
Answer, for internal users: *Are systems operational? Is there a known issue?
What's affected? What happened? Is there planned maintenance?*

## Architecture
- **status-api** — its own FastAPI service + Postgres database `status` (per-service
  ownership, like the other services). Tables: `status_components`,
  `status_incidents`, `status_maintenance_windows`.
- **Health collector** — runs the configured checks concurrently (short timeouts),
  maps each to a component status, and upserts the component rows. Seeded on
  startup, refreshed on an interval (`status_refresh_interval_seconds`). `GET
  /status` reads the stored rows (fast; never blocks on live checks).
- **Overall status** is derived (pure, tested function `derivation.py`):
  `critical` incident → `major_outage`; `major` → `partial_outage`; `minor` or any
  component degraded/down → `degraded`; maintenance active (nothing worse) →
  `maintenance`; else `operational`; no/only-unknown components → `unknown`.
- **UI** — a single self-contained HTML page at `GET /` (vanilla JS calls
  `GET /status`, renders cards). No build step, no graphs.

## Endpoints
Read (public):
```
GET /                              # the HTML status page
GET /status                        # full payload (overall + components + incidents + maintenance)
GET /status/components
GET /status/incidents
GET /status/incidents/{id}
GET /status/maintenance
GET /status/maintenance/{id}
```
Write (require `Authorization: Bearer $OPS_STATUS_TOKEN`):
```
POST  /status/incidents
PATCH /status/incidents/{id}
DELETE /status/incidents/{id}      # soft delete (deleted_at)
POST  /status/maintenance
PATCH /status/maintenance/{id}
DELETE /status/maintenance/{id}    # soft delete
```

## Auth model
A single internal token from `OPS_STATUS_TOKEN` (no user accounts). Missing token
→ **401**; wrong token → **403**. Comparison is constant-time
(`secrets.compare_digest`); the token is never logged or returned. Read endpoints
need no auth.

## Status / enum values
- component: `operational | degraded | down | maintenance | unknown`
- overall: `operational | degraded | partial_outage | major_outage | maintenance | unknown`
- incident status: `investigating | identified | monitoring | resolved`
- incident severity: `minor | major | critical`
- incident area: `platform | backend | frontend | external_provider | unknown`
- incident cause: `deployment | migration | infrastructure | third_party | config | data_import | code_bug | cache_sync | dependency_failure | unknown`
- maintenance status: `scheduled | in_progress | completed | cancelled`

## Run locally
```bash
docker compose up --build           # status-api on http://localhost:8004
open http://localhost:8004/         # the status page
curl -s localhost:8004/status | jq  # the JSON payload
```
The token in compose is `OPS_STATUS_TOKEN=dev-ops-token-change-me`.

### Create an incident (authenticated)
```bash
curl -X POST http://localhost:8004/status/incidents \
  -H "Authorization: Bearer dev-ops-token-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Pricing API degraded",
    "status": "investigating",
    "severity": "major",
    "affected_components": ["pricing-api", "webshop-api"],
    "area": "backend",
    "cause": "dependency_failure",
    "summary": "Pricing API has elevated latency after provider timeouts."
  }'
```
Then resolve it:
```bash
curl -X PATCH http://localhost:8004/status/incidents/<id> \
  -H "Authorization: Bearer dev-ops-token-change-me" \
  -H "Content-Type: application/json" \
  -d '{"status":"resolved","resolution":"Cached provider scores; projections recovered.","follow_up":"Tune timeouts."}'
```
Resolved incidents move from `active_incidents` to `recent_incidents`.

### Schedule maintenance
```bash
curl -X POST http://localhost:8004/status/maintenance \
  -H "Authorization: Bearer dev-ops-token-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Valkey restart",
    "status": "scheduled",
    "affected_components": ["valkey", "webshop-api"],
    "summary": "Restart Valkey and verify projection rebuild behavior.",
    "scheduled_start_at": "2026-01-15T20:00:00Z",
    "scheduled_end_at": "2026-01-15T20:15:00Z"
  }'
```

## Health checks
Configured via `STATUS_CHECKS` (JSON) or Helm `opsStatus.statusChecks`; defaults
cover the platform services + Postgres/Valkey/Elasticsearch. Each check is HTTP
(GET a `/ready` URL, expect a status) or TCP (connect host:port). Mapping:
`200` → operational, other response → degraded, timeout/connection error → down,
unknown → unknown. Timeouts are short (≈2s) and checks run concurrently.

## Observability
- Structured logs: `status.incident.created|updated|resolved|deleted`,
  `status.maintenance.created|updated|deleted`, with `incident_id` /
  `maintenance_id`, `status`, `severity`, `affected_components`, and the ambient
  `request_id` (bound by middleware).
- Prometheus gauges at `/metrics`: `status_components_total{status}`,
  `status_active_incidents_total{severity}`, `status_maintenance_windows_total{status}`.

## Kubernetes / Helm / ESO
status-api is a normal entry in the chart's `services` map (port 8004, db
`status`, `opsToken: true`). The ops token follows the same secret pattern as the
JWT secret:
- **dev (plain):** the chart creates `<release>-status` from `opsStatus.token`.
- **dev (ESO demo) / uat / stg / prd:** `opsStatus.existingSecret: commerce-status`
  and the **External Secrets Operator** materializes `commerce-status` (key
  `OPS_STATUS_TOKEN`) from Doppler — add `OPS_STATUS_TOKEN` to each Doppler config.
  See [SECRETS.md](SECRETS.md).

```yaml
# values-<env>.yaml
opsStatus:
  existingSecret: commerce-status   # ESO-managed; key OPS_STATUS_TOKEN
  statusChecks: []                  # optional override of the default checks
```

The migration runs via the per-env migration Job (status DB), and Reloader
rolling-restarts status-api if the token rotates.
