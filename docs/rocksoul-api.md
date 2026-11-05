# ROCKSOUL Product API v1

## Boundary
The API adapts the existing ROCKSOUL SQLite stores, explainable router, execution trace store and execution engine. Provider implementations remain in the g4f runtime; this API does not add a second provider registry.

## Start
```bash
pip install 'g4f[rocksoul-api]'
set ROCKSOUL_API_KEY=replace-with-a-long-random-secret
python -m g4f.rocksoul_api
```

Defaults to loopback `127.0.0.1:8765`. Binding beyond loopback requires `ROCKSOUL_API_KEY`. Execution always requires the key, including loopback deployments.

## Endpoints
- `GET /healthz` — process liveness.
- `GET /api/v1/status` — aggregate provider/model/run counts.
- `GET /api/v1/providers` — provider lifecycle and health summary.
- `GET /api/v1/routes/{model}/explain` — canonical route explanation; optional comma-separated `requirements` and `providers_filter`.
- `GET /api/v1/traces/{request_id}` — persisted execution trace.
- `POST /api/v1/execute` — bounded non-streaming execution, requires `X-ROCKSOUL-API-Key`.

OpenAPI docs: `/api/docs`.

## Safety
Unknown request fields are rejected. Message count, attempt count, timeout and total duration are bounded. Arbitrary provider objects are never accepted. Streaming is rejected by this JSON endpoint to avoid partial-response replay ambiguity. API keys are compared in constant time and never returned. Do not expose execution publicly without user/session and tenant authorization.

## Deployment
Keep the API on a private network. The Next.js console proxies browser requests through same-origin `/api/*` rewrites to `ROCKSOUL_API_INTERNAL_URL`; the API key must remain server-side and must never use a `NEXT_PUBLIC_*` variable.

## Not included
Multi-tenant accounts, billing, quotas, public gateway exposure, streaming transport, Mesh administration and Arena campaign mutation APIs require dedicated authorization and audit contracts.
