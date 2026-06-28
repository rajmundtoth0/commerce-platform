# Secrets management (Doppler + External Secrets Operator + Reloader)

One source of truth for secrets across **local, CI, and Kubernetes** — Doppler —
delivered to each runtime by the idiomatic tool for that runtime:

```
                         ┌─────────────────────────┐
                         │   Doppler (SecretOps)    │  project: commerce-platform
                         │  configs: dev/uat/stg/prd│  keys: JWT_SECRET, POSTGRES_PASSWORD, ...
                         └───────────┬─────────────┘
        local CLI ┌─────────────────┼──────────────────┐ k8s
                  ▼                  ▼ CI               ▼
        doppler run -- ...   Doppler GH action   External Secrets Operator
        (injects env)        (fetch creds)       SecretStore → ExternalSecret
                                                         │
                                                 native k8s Secret
                                                 (commerce-jwt, commerce-postgres)
                                                         │  chart `existingSecret`
                                                         ▼
                                                 env in pods  ──(rotation)──► Reloader
                                                                              rolling-restart
```

Why this shape: the **app and Helm chart never change** — they always read plain
env vars / a native k8s `Secret` (`existingSecret`). Doppler is purely an
injection-time concern, and because it's fronted by the **External Secrets
Operator**, the backend is swappable (Doppler → Scaleway Secret Manager → Vault)
by editing only the `SecretStore`.

> Personal data (users, orders, logs) lives in **Scaleway** (EU). Doppler only
> ever holds **credentials**, not GDPR-relevant personal data — so it doesn't
> affect data residency. See `docs/DEPLOY_SCALEWAY.md`.

## Doppler setup (once)
Create a Doppler project `commerce-platform` with configs `dev`, `uat`, `stg`,
`prd`. In each, set at least:
- `JWT_SECRET`
- `POSTGRES_PASSWORD`

(Optionally centralize non-secret config too; the k8s path below only syncs the
two credentials the chart needs.)

## Local development
```bash
doppler login
doppler setup          # reads doppler.yaml -> project commerce-platform, config dev
doppler run -- docker compose up --build      # injects JWT_SECRET, POSTGRES_*, VALKEY_URL...
```
`.env` / `.env.example` remain as documentation, but Doppler is the source of truth.

## Kubernetes (the ESO pattern)
The chart renders, behind `externalSecrets.enabled`:
- a **`SecretStore`** (Doppler provider, auth = a bootstrap `doppler-token` Secret), and
- one **`ExternalSecret`** per target Secret (`commerce-jwt`, `commerce-postgres`).

ESO reconciles each `ExternalSecret` → writes the native Secret the chart already
consumes via `global.jwtExistingSecret` / `global.postgres.existingSecret`. So
enabling ESO is just: install the operator, drop in the bootstrap token, set
`externalSecrets.enabled=true` (already set for uat/stg/prd).

**Bootstrap token ("secret zero")** — the one Doppler *service token*, scoped to
that env's config:
```bash
kubectl -n commerce-stg create secret generic doppler-token \
  --from-literal=dopplerToken=dp.st.stg.xxxxxxxx
```

### Rotation → Reloader
ESO updates the k8s Secret when a value rotates in Doppler, but env vars are read
once at container start. **stakater/reloader** watches the Secrets and triggers a
**rolling restart** of the annotated Deployments (added automatically when
`reloader.enabled=true`). No manual `kubectl rollout restart` needed.
(Don't use the Helm `checksum/secret` trick here — ESO writes the Secret
out-of-band, so a chart-time checksum never changes on rotation.)

## Local demo on kind (full pattern)
Show ESO + Reloader + Doppler end-to-end on your laptop:
```bash
WITH_ESO=1 DOPPLER_TOKEN=dp.st.dev.xxxxxxxx ./deploy/dev/kind-up.sh
```
This installs ESO + reloader, bootstraps the `doppler-token` Secret, and deploys
with `values-dev-eso.yaml` (chart stops creating secrets; ESO syncs them from the
Doppler `dev` config; the in-cluster Postgres uses that same synced password).

Verify:
```bash
kubectl -n commerce-dev get externalsecret,secretstore
kubectl -n commerce-dev get secret commerce-jwt commerce-postgres
# rotate POSTGRES_PASSWORD in Doppler -> watch reloader roll the pods:
kubectl -n commerce-dev get pods -w
```

Plain `./deploy/dev/kind-up.sh` (no `WITH_ESO`) still works with chart-managed
secrets — no Doppler account required for a basic local run.

## CI
Store a single `DOPPLER_TOKEN` (service token) as a GitHub secret and use the
Doppler GitHub action / `doppler secrets download` to fetch what a job needs
(e.g. registry credentials), instead of many individual GH secrets.

## Swapping the backend (portability)
To move off Doppler (e.g. to Scaleway Secret Manager for full single-cloud), keep
every `ExternalSecret` and the chart unchanged — edit only the `SecretStore`
provider block (`externalSecrets.provider` + its auth). That decoupling is the
main reason to front Doppler with ESO rather than Doppler's own operator.
