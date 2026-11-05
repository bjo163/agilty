# ROCKSOUL Stage 6 — Product API & Integration

## Goal
Expose a stable, versioned product interface over existing ROCKSOUL capabilities without duplicating the g4f provider runtime.

## Delivered API surface
- `GET /healthz` process liveness.
- `GET /api/v1/status` aggregate inventory.
- `GET /api/v1/providers` provider lifecycle and health.
- `GET /api/v1/routes/{model}/explain` canonical route explanation.
- `GET /api/v1/traces/{request_id}` persisted execution evidence.
- `POST /api/v1/execute` bounded non-streaming execution protected by an operator API key.
- OpenAPI docs at `/api/docs`.

## Safety and compatibility
- API is optional via `g4f[rocksoul-api]`.
- No new provider adapter implementations.
- Strict request models reject unknown fields.
- Request count, retries, timeout and total time are bounded.
- Execution is always authenticated; remote bind requires an API key.
- Streaming is intentionally not exposed over this initial JSON endpoint.
- Legacy GUI and g4f HTTP endpoints remain untouched.

## Not included in this slice
Multi-tenant user auth, billing, tenant quotas, public internet exposure, streaming transport, Mesh administration and Arena campaign mutation APIs. These require dedicated authorization and audit contracts before exposure.
