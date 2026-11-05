# ROCKSOUL Stage 7 — Operator Console

## Delivered
- [x] Next.js App Router, TypeScript, React 19 and standalone output.
- [x] Signed HTTP-only SameSite=Strict sessions with 12-hour expiry.
- [x] Operator and Administrator roles. Operators run bounded executions; administrators manage provider and Mesh node states.
- [x] Server-side API proxy; API key never reaches browser JavaScript.
- [x] Overview, provider fleet, route explanation, Mesh nodes/leases, Arena pack/campaign evidence, trace explorer and bounded execution screens.
- [x] Provider activate/quarantine/probe and Mesh activate/drain/quarantine controls.
- [x] Arena campaign verification and NOT_CERTIFIED claim boundary.
- [x] Persisted dark/light preference and English/Indonesian toggle.
- [x] Playwright browser smoke tests, responsive console and Docker Compose deployment topology.
- [x] Legacy HTML routes retained as compatibility surface; no duplicate provider runtime.

## API additions
GET /api/v1/traces?limit=&offset=; GET /api/v1/mesh; POST /api/v1/mesh/nodes/{node_id}/state; GET /api/v1/arena; GET /api/v1/arena/campaigns/{campaign_id}/verify; GET /api/v1/arena/packs/{pack_digest}/report; POST /api/v1/providers/{provider}/control.

Mutations require X-ROCKSOUL-API-Key. Next.js server injects the key; provider and Mesh mutations require Administrator role.

## Local setup
Install `pip install -e '.[rocksoul-api]'`, set ROCKSOUL_API_HOST and ROCKSOUL_API_KEY, then run `python -m g4f.rocksoul_api`. In frontend/rocksoul-console run `npm install && npm run dev`. Configure ROCKSOUL_API_INTERNAL_URL, ROCKSOUL_API_KEY, ROCKSOUL_CONSOLE_ADMIN_PASSWORD, ROCKSOUL_CONSOLE_OPERATOR_PASSWORD and ROCKSOUL_CONSOLE_SESSION_SECRET (32+ characters) on the server.

## Docker Compose / Coolify
Configure ROCKSOUL_API_KEY, ROCKSOUL_CONSOLE_ADMIN_PASSWORD, ROCKSOUL_CONSOLE_OPERATOR_PASSWORD and ROCKSOUL_CONSOLE_SESSION_SECRET as deployment secrets. Deploy `docker-compose.rocksoul.yml`. Route the public domain to console port 3000; keep API port 8765 private. Persist and back up rocksoul-data.

## Security and limitations
Single-tenant environment-configured roles, not enterprise SSO or multi-tenant identity. Keep API private and terminate TLS at reverse proxy. Arena integrity is not dataset licensing, contamination, methodology or model-quality certification; reports remain NOT_CERTIFIED. Execution UI exposes bounded single text messages, not streaming or every multimodal runtime option. Legacy HTML screens remain available while route-by-route parity continues separately.

## Verification
CI runs Next.js lint/build, Playwright browser smoke tests and Docker Compose configuration validation. Existing ROCKSOUL CI continues to run Python API contract tests.
