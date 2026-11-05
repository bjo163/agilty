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
- `GET|POST /api/v1/verification-profiles` — authenticated immutable profile registry list/register.
- `GET /api/v1/verification-profiles/{profile_id}/{version}` — authenticated immutable profile readback.
- `GET|POST /api/v1/work-items` — authenticated WorkItem list/create.
- `GET /api/v1/work-items/{work_id}` — authenticated contract and lifecycle readback.
- `POST /api/v1/work-items/{work_id}/transitions` — authenticated expected-state lifecycle transition.
- `POST /api/v1/work-items/{work_id}/criteria/{criterion_id}/verify` — execute a bounded built-in verifier against supplied artifact bytes.
- `POST /api/v1/work-items/{work_id}/approval` — record a signed administrator decision; requires `X-ROCKSOUL-Approval-Signature` in addition to the API key.
- `GET /api/v1/work-items/{work_id}/evidence-diff` — compare the latest and previous verifier receipts per criterion.
- `GET /api/v1/work-items/{work_id}/evidence-bundle` — export contract, events, approvals, execution links, verifier receipts, and chain result as metadata-only JSON.
- `GET /api/v1/work-items/{work_id}/verify-chain` — authenticated event hash-chain verification.

OpenAPI docs: `/api/docs`.

## Safety
WorkItem and verification-profile endpoints require the operator API key for both reads and writes. Unknown request fields are rejected. Message count, attempt count, timeout and total duration are bounded. Arbitrary provider objects are never accepted. Streaming is rejected by this JSON endpoint to avoid partial-response replay ambiguity. API keys are compared in constant time and never returned. Do not expose execution publicly without user/session and tenant authorization.

## Deployment
Keep the API on a private network. The Next.js console proxies browser requests through same-origin server routes to `ROCKSOUL_API_INTERNAL_URL`; the API key and approval HMAC secret must remain server-side and must never use a `NEXT_PUBLIC_*` variable. Set the same `ROCKSOUL_APPROVAL_SIGNING_SECRET` (minimum 32 characters) in the API and Console, plus a stable `ROCKSOUL_CONSOLE_ADMIN_ID`; existing sessions must sign in again after principal configuration changes.

## Work Contract boundary

See [Work Contracts & Verification Profiles](rocksoul-work-contracts.md) for schemas, lifecycle semantics, CLI usage, and evidence requirements. The registry never dynamically loads adapters. The built-in verifier executes five bounded deterministic adapters: `artifact_digest`, `json_schema`, pytest JUnit XML, captured HTTPS contract receipts, and content-addressed source binding. The verification endpoint computes SHA-256 over supplied artifact bytes, persists the result/evidence, and acceptance requires a latest persisted PASS for every required criterion. Optional `work_id` on `/api/v1/execute` requires a RUNNING WorkItem and the exact `model.execute` permission; it refuses pending human-approval gates and expired deadlines, caps attempts/wall-time to the WorkItem budget, and blocks when token/cost limits cannot be enforced. It links the resulting request ID and provider transport outcome into event history and returns `task_outcome=unverified`; it never auto-accepts the task. The verification endpoint accepts base64 artifact bytes (decoded maximum 1 MiB), a source reference, and profile-specific inputs. The Console provides immutable profile registration/listing, bounded artifact upload, browser-side SHA-256, and per-criterion verifier execution. The supplied source reference is operator metadata; artifact source authenticity and external verifier signatures are not established. High/critical WorkItems require a Console-server HMAC approval bound to the contract digest, configured administrator principal ID, decision, timestamp, and one-time nonce. The API enforces a five-minute timestamp window and replay protection, persists approval events in the hash chain, and blocks transition to `RUNNING` and execution unless the latest decision is `approved`. This proves use of the configured administrator credential/principal, not the natural-person identity of the operator; deployments remain single-instance and are not SSO or legal non-repudiation.

## Not included
Multi-tenant accounts, billing, quotas, public gateway exposure, streaming transport, Mesh administration and Arena campaign mutation APIs require dedicated authorization and audit contracts.
