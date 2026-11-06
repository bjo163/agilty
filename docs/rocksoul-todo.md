# ROCKSOUL UI Product Backlog

> Canonical backlog for replacing the built-in g4f HTML/web interface with ROCKSOUL. The existing g4f Python runtime, API, provider implementations, model registry, routing and execution remain authoritative.

## Product identity

ROCKSOUL is the user interface and visual identity for g4f. It is not a second gateway, router, provider registry, model catalog, execution engine or control plane.

## Backlog scope note

The historical F3–F10 engineering workstreams below describe optional ROCKSOUL operator/experimental modules implemented before the product-boundary correction. They are not required for ordinary chat and must not be treated as the primary product roadmap. The authoritative UI replacement tasks and completion gate are in the Product scope reset section near the end of this file. Keep optional modules isolated and independently removable.

## Status legend

- `DONE` implemented and verified by automated tests
- `FOUNDATION` implemented and verification-gated core exists, while broader production benchmark packs remain deferred
- `VERIFYING` implemented; awaiting current CI certification
- `BLOCKED` intentionally waiting on another phase gate
- `DEFERRED` outside the current release and moved to its own future gate

## F3 execution intelligence

### RS-F3-001 — Explicit rate-limit cooldown
- Status: `DONE`
- Scope: explicit persisted cooldown with reason and expiry.
- Implementation: `g4f/rocksoul_control.py`, `g4f/rocksoul_execution.py`, `g4f/rocksoul_db.py` routing integration.
- Acceptance: rate-limit immediately places the provider in bounded `DEGRADED` cooldown; routing excludes it until expiry.
- Tests: `test_rate_limit_applies_explicit_control_cooldown`, `test_rate_limit_cooldown_blocks_until_expiry`.

### RS-F3-002 — Same-provider retry budget
- Status: `DONE`
- Scope: per-provider retry counter independent from total-attempt budget.
- Implementation: `ExecutionRequest.max_same_provider_attempts` and execution provider counters.
- Acceptance: no provider exceeds its configured retry budget; fallback continues when that budget is exhausted.
- Tests: `test_same_provider_retry_is_bounded`.

### RS-F3-003 — Explicit quarantine state
- Status: `DONE`
- Scope: persisted lifecycle state and operator command.
- Implementation: `ProviderControlStore`, `rocksoul quarantine`, route filtering, health/status output, failure-streak convergence.
- Acceptance: manual quarantine requires no fake failures and quarantined providers are never selected; a three-failure legacy streak converges to explicit `QUARANTINED`.
- Tests: control state machine + `test_provider_enters_legacy_health_cooldown_after_failure_streak`.

### RS-F3-004 — Recovery and re-admission lifecycle
- Status: `DONE`
- Scope: `QUARANTINED → PROBING → RE_ADMITTED|QUARANTINED`.
- Implementation: `RecoveryManager` + provider control event history.
- Acceptance: failed recovery stays quarantined; successful recovery is traceable.
- Tests: control state-machine coverage; live recovery remains operator-only.

### RS-F3-005 — Single canonical route explanation
- Status: `DONE`
- Scope: `ExplainableRouter` is the canonical explanation source.
- Implementation: execution candidate selection and CLI route-explain both consume it; capability failures remain visible as rejection reasons.
- Acceptance: route explanation exposes state, capability, verification, health, latency, and reasons without a second product scoring path.
- Tests: intelligence and CLI route-explain contract tests.

### RS-F3-006 — Streaming fallback safety
- Status: `DONE`
- Scope: conservative stream lifecycle with no automatic replay after stream exposure.
- Implementation: stream wrapper records active, success, abandonment, or failure terminal state.
- Acceptance: partial output is never silently duplicated by fallback.
- Tests: streaming failure/success lifecycle coverage.

### RS-F3-007 — Whole-request execution time budget
- Status: `DONE`
- Scope: `max_total_time` bounds routing plus all attempts/backoff, including the pre-attempt lifecycle.
- Acceptance: a request whose total budget is exhausted before the first provider call produces zero attempts and an explicit `budget_exhausted` outcome.
- Tests: `test_total_time_budget_covers_entire_request_lifecycle`.

### RS-F3-008 — In-flight total-budget enforcement
- Status: `DONE`
- Scope: cap each provider-call timeout by the remaining whole-request budget.
- Acceptance: an attempt cannot overrun `max_total_time` merely because its provider timeout is larger.
- Tests: `test_total_time_budget_caps_inflight_provider_timeout`.

### RS-F3-009 — Recovery probing isolation
- Status: `DONE`
- Scope: keep `PROBING` providers outside normal request routing.
- Acceptance: provider remains unroutable until explicit `RE_ADMITTED` transition.
- Tests: control lifecycle routing assertions in `test_quarantine_and_recovery_state_machine`.

### RS-F3-010 — Single-counted streaming health evidence
- Status: `DONE`
- Scope: do not record stream success before the stream has actually completed.
- Acceptance: one stream attempt contributes at most one terminal execution health signal; failed streams are not counted as both success and failure.
- Tests: `test_stream_failure_after_partial_output_is_terminal_and_single_counted`, `test_successful_stream_records_success_only_after_consumption`.

## F4 Mesh coordination

### RS-F4-001 — Persistent Mesh coordination foundation
- Status: `DONE`
- Scope: production Mesh state is stored in the existing ROCKSOUL SQLite control-plane database without replacing F1–F3 execution/provider state.
- Implementation: `g4f/rocksoul_mesh.py` tables `mesh_nodes`, `mesh_leases`, `mesh_events`, and `mesh_auth_nonces`.
- Acceptance: node state, lease history, audit events, and replay evidence survive process boundaries and remain separate from provider lifecycle tables.
- Tests: deterministic Mesh core suite.

### RS-F4-002 — Authenticated node identity and replay protection
- Status: `DONE`
- Scope: remote node self-service operations use HMAC-SHA256 with action, node ID, timestamp, nonce, and canonical payload.
- Acceptance: invalid signatures, wrong per-node keys, stale timestamps, and replayed `(node_id, nonce)` values are rejected; secrets are not persisted in audit rows.
- Tests: `test_authenticated_registration_rejects_invalid_signature_and_replay`, `test_per_node_keys_isolate_node_identity`.

### RS-F4-003 — Secure endpoint boundary
- Status: `DONE`
- Scope: production endpoints require HTTPS; plaintext HTTP is allowed only by explicit local/private development policy.
- Acceptance: malformed endpoints, embedded credentials/fragments, and non-local plaintext endpoints fail closed.
- Tests: `test_endpoint_security_requires_https_unless_local_policy_is_explicit`.

### RS-F4-004 — Explicit node lifecycle and stale-node isolation
- Status: `DONE`
- Scope: `REGISTERED`, `ACTIVE`, `DEGRADED`, `DRAINING`, `QUARANTINED`, `OFFLINE`.
- Acceptance: authenticated heartbeat activates normal nodes, heartbeat expiry marks stale nodes offline, and heartbeat cannot silently make draining/quarantined nodes routable.
- Tests: heartbeat/offline lifecycle and state-routing assertions in `tests/test_rocksoul_mesh.py`.

### RS-F4-005 — Deterministic capability/capacity routing
- Status: `DONE`
- Scope: only active nodes satisfying every requested capability and remaining under authoritative capacity are eligible.
- Acceptance: ranking is deterministic from health, weight, latency, load, failure penalty, and stable node-ID tie breaking; no eligible node returns no selection rather than bypassing policy.
- Tests: `test_selection_respects_capabilities_score_capacity_and_idempotency`.

### RS-F4-006 — Bounded idempotent work leases
- Status: `DONE`
- Scope: request IDs map idempotently to bounded leases and reserve control-plane-owned in-flight capacity.
- Acceptance: lease TTL is finite, expiry returns capacity, and node heartbeat claims cannot overwrite authoritative in-flight counts.
- Tests: lease selection, idempotency, capacity, expiry, and release coverage in the Mesh core/CLI suites.

### RS-F4-007 — Per-node failure isolation
- Status: `DONE`
- Scope: failures degrade/quarantine only the owning node while preserving unrelated nodes and the independent F3 provider lifecycle.
- Acceptance: failed leases cannot fan out quarantine state to other nodes/providers; draining/quarantined/offline/degraded nodes remain excluded from normal Mesh work.
- Tests: `test_failure_isolation_quarantines_only_failing_node`, draining/lease-expiry assertions.

### RS-F4-008 — Mesh observability and operator CLI
- Status: `DONE`
- Scope: auditable node/lease events plus JSON-oriented `rocksoul-mesh` operator surface.
- Commands: `status`, `list`, `register`, `heartbeat`, `state`, `select`, `lease`, `release`, `events`.
- Acceptance: operator state and audit evidence are inspectable without exposing configured secrets; missing key material fails clearly.
- Tests: `tests/test_rocksoul_mesh_cli.py` plus Mesh status/event assertions.

### RS-F4-009 — Independent Mesh release gate
- Status: `DONE`
- Scope: dedicated F4 CI/release contract independent of legacy Mesh/Arena scaffolding.
- Acceptance: Mesh CI must pass Ubuntu/Windows Python 3.13 deterministic core+CLI tests and package build; final `main` candidate must also pass existing ROCKSOUL CI and general Unittest.
- Workflow: `.github/workflows/rocksoul-mesh-ci.yml`.
- Evidence: F4 shipped in `v0.2.0` from final candidate `f0db58677386c0e5a661d9816d696d91cced2b9f`; Mesh CI, ROCKSOUL CI, general Unittest, and production release workflow passed.

## F6 product CLI

### RS-F6-001 — CLI contract suite
- Status: `DONE`
- Scope: stable JSON command surface with offline contract tests.
- Commands: `status`, `discover`, `health`, `provider`, `probe`, `verify`, `route`, `route-explain`, `execute`, `trace`, `quarantine`, `recover`.
- Tests: `tests/test_rocksoul_cli.py` plus ROCKSOUL CLI smoke workflow.

### RS-F6-002 — Preserve verified-only capability routing
- Status: `DONE`
- Scope: `route --verified-only` must retain the verification constraint when capability flags are supplied.
- Acceptance: capability-aware selection cannot silently reintroduce unverified model bindings.
- Tests: `test_route_verified_only_is_preserved_with_capability_filter`.

## F7 verification

### RS-F7-001 — Execution release matrix
- Status: `DONE`
- Coverage: fallback ordering, taxonomy, bounded retries, cooldown, quarantine, recovery state machine, trace reconstruction, stream safety/evidence, lifecycle budget, CLI contracts, verified-only capability routing.
- Release requirement: required Ubuntu and Windows ROCKSOUL CI must be green on the final release candidate.

### RS-F7-002 — Mesh release matrix
- Status: `DONE`
- Coverage: Mesh auth/replay, node identity, endpoint security, lifecycle, capability/capacity routing, lease idempotency/expiry, failure isolation, audit events, and operator CLI.
- Release requirement: dedicated Mesh CI plus existing ROCKSOUL CI and general Unittest must be green on the final release candidate.
- Evidence: satisfied by the published `v0.2.0` production candidate and revalidated after F5 foundation merge.

## F8 documentation and productization

### RS-F8-001 — Product README
- Status: `DONE`

### RS-F8-002 — Product architecture docs
- Status: `DONE`

### RS-F8-003 — Contributing and compatibility boundary
- Status: `DONE`

### RS-F8-004 — F4 Mesh architecture and release gate
- Status: `DONE`
- Docs: `docs/rocksoul-mesh.md`, `docs/rocksoul-mesh-release-gate.md`.

## F5 Arena benchmark plane

### RS-F5-001 — Canonical Arena foundation
- Status: `FOUNDATION`
- Scope: canonical F5 benchmark authority independent from legacy `rocksoul_platform.Arena`, F3 provider lifecycle, and F4 Mesh lifecycle.
- Implementation: `g4f/rocksoul_arena.py`.
- Acceptance: benchmark execution cannot mutate production provider routing/health or Mesh node/lease state.
- Tests: `tests/test_rocksoul_arena.py`.

### RS-F5-002 — Immutable suite provenance
- Status: `FOUNDATION`
- Scope: canonical suite manifests, explicit versioning, SHA-256 identity, deterministic case ordering, and immutable `(name, version)` content.
- Acceptance: changed benchmark content under the same name/version fails closed and requires a version bump.
- Tests: stable digest and immutable-version regressions in `tests/test_rocksoul_arena.py`.

### RS-F5-003 — Deterministic scoring and persistent evidence
- Status: `FOUNDATION`
- Scope: weighted deterministic correctness, explicit execution-error evidence, output digests, latency evidence, and SQLite persistence for suites/runs/results.
- Acceptance: correctness ranking is deterministic; latency is evidence-only and does not silently alter the default score.
- Tests: scoring, persistence, execution-failure, and leaderboard coverage.

### RS-F5-004 — Arena operator CLI
- Status: `FOUNDATION`
- Scope: JSON-oriented `rocksoul-arena` operator surface.
- Commands: `status`, `fixture`, `fixture-manifest`, `runs`, `show`, `leaderboard`.
- Acceptance: offline fixture targets can verify perfect, mixed, and explicit failing behavior without live provider/network dependencies.
- Tests: `tests/test_rocksoul_arena_cli.py`.

### RS-F5-005 — Independent Arena CI and methodology gate
- Status: `FOUNDATION`
- Scope: independent Arena methodology, release gate, Ubuntu/Windows CI, CLI smoke, and package build validation.
- Docs: `docs/rocksoul-arena.md`, `docs/rocksoul-arena-release-gate.md`.
- Workflow: `.github/workflows/rocksoul-arena-ci.yml`.
- Evidence: PR #17 exact head `10d16d58b6257396acd7dad00d614f3ac31e46a3` passed Arena CI, Mesh CI, ROCKSOUL CI, and general Unittest; merged as `d3123a9ff8d00828d0043cd0bb3937cbc16dab8a`, whose post-merge Arena/Mesh/ROCKSOUL/Unittest workflows also passed.

### RS-F5-006 — Production benchmark packs
- Status: `DEFERRED`
- Scope: authoritative live provider/model benchmark packs beyond the deterministic repository fixture.
- Required before activation: versioned source/dataset provenance, evaluator revision, public/held-out policy where applicable, contamination/leakage review, repeat-run variance policy, environment/network requirements, and exact target/provider/model revision metadata.
- Rule: the F5 foundation being green does not by itself certify broad live-model quality claims or create a new production release.

## Definition of Product-Ready v0.2 Baseline

- F1 execution works through existing runtime provider implementations.
- F2 persists every attempt and final outcome.
- F3 has deterministic taxonomy, bounded retries, explicit cooldown, quarantine, probing isolation, recovery, safe streaming semantics, single-counted stream evidence, and whole-request time budgeting including in-flight calls.
- F4 has authenticated node identity, replay protection, explicit lifecycle, deterministic capability/capacity routing, bounded leases, failure isolation, auditable events, and a separate operator CLI.
- F6 execution CLI and F4 Mesh CLI are documented and contract-tested.
- F7 tests are offline by default and CI-certified on required platforms before merge.
- F8 docs use ROCKSOUL product terminology consistently.
- No duplicate provider implementation exists.
- Legacy `MeshRegistry` remains compatibility-only; it is not the canonical F4 path.
- F5 Arena foundation may exist on `main` without changing the published `v0.2.0` release scope.
- Legacy `rocksoul_platform.Arena` remains compatibility-only; canonical F5 authority is `g4f/rocksoul_arena.py`.


## Stage 3 — Production evidence integration

### RS-F5-007 — Strict production-pack validation
- Status: `DONE`
- Scope: validate the nested Arena suite, typed provenance, finite JSON requirement objects, bounded integer repeat count, exact target identity, and observed environment before persistence.
- Acceptance: malformed dataclass inputs and invalid nested suites fail with `ArenaValidationError`; no invalid pack reaches storage.
- Implementation: `g4f/rocksoul_arena_production.py`.

### RS-F5-008 — Offline production evidence operator CLI
- Status: `DONE`
- Scope: versioned strict JSON manifests, dataset SHA-256 verification, immutable registration, pack/campaign listing, campaign readback, and an end-to-end synthetic fixture.
- Acceptance: duplicate JSON keys, non-finite values, and unknown fields fail closed; `register-pack` must hash the exact local artifact and reject a mismatch before database writes; all commands emit machine-readable JSON; no provider/network call is performed.
- Implementation: `g4f/rocksoul_arena_production_cli.py`.
- Tests: `tests/test_rocksoul_arena_production_cli.py`.

### RS-F5-009 — Installed package entrypoint verification
- Status: `DONE`
- Scope: expose `rocksoul-arena-production` from the active `setup.py` configuration and smoke-test installed console scripts from outside the repository checkout.
- Acceptance: built wheel installs without dependency resolution and all ROCKSOUL entrypoints start or return help/status successfully.
- Workflow: `.github/workflows/rocksoul-ci.yml` and `.github/workflows/rocksoul-arena-ci.yml`.

## Stage 4 — Operator-authorized campaign execution

### RS-F5-010 — Explicit live campaign operator command
- Status: `DONE`
- Scope: execute one exact registered production pack against one exact g4f provider/model without adaptive fallback or hidden target changes.
- Acceptance: live execution is denied unless both `--confirm-live` and `ROCKSOUL_ALLOW_LIVE_ARENA=1` are present; the exact pack digest is reconfirmed; the pack must already be registered; the local dataset artifact is SHA-256 verified again; provider/model/runtime revisions, region, and network mode are explicit.
- Implementation: `g4f/rocksoul_arena_production_cli.py`.

### RS-F5-011 — Preflight and cost-safety envelope
- Status: `DONE`
- Scope: validate every text-only test prompt before provider calls, match the declared OS/Python/network environment, enforce max tokens, provider timeout hint, and total request count.
- Acceptance: malformed prompts, environment mismatch, artifact mismatch, unregistered pack, missing confirmation, or request-budget overflow fail before provider invocation. No automatic retries or provider fallback are used.
- Tests: `tests/test_rocksoul_arena_production_cli.py` uses a fake provider; no real provider is contacted by CI.

### RS-F5-012 — Persist and classify campaign evidence
- Status: `DONE`
- Scope: persist exact target/runtime/network/region evidence and all repeated Arena run IDs; report high-variance campaigns as unaccepted with a non-zero exit status.
- Acceptance: readback contains the exact provider/model/revisions and observed environment; campaign evidence does not independently certify dataset licensing or contamination.

## Stage 5 — Campaign evidence audit and certification reporting

### RS-F5-013 — Immutable campaign integrity verifier
- Status: `DONE`
- Scope: reconcile each persisted campaign with the immutable pack manifest, canonical Arena suite, all constituent Arena runs, exact target/environment metadata, repeat ordering, case-level results, weighted scores, and timestamps.
- Acceptance: a valid campaign verifies reproducibly; deleted runs, altered metadata, changed case weights/results, score drift, malformed repeats, or altered variance fields fail closed. The auditor never repairs stored evidence.
- Implementation: `g4f/rocksoul_arena_production.py` (`ArenaProductionStore.verify_campaign`).

### RS-F5-014 — Deterministic per-pack/per-target campaign reports
- Status: `DONE`
- Scope: aggregate campaign evidence per exact target without mixing different provider/model revisions; include integrity and variance acceptance counts and a deterministic report digest.
- Acceptance: no-pack/no-evidence, verified, and rejected states have stable machine-readable status and exit codes. Reports always state `quality_certification=NOT_CERTIFIED`.
- Implementation: `ArenaProductionStore.campaign_report` and production CLI commands.

### RS-F5-015 — Offline regression and release gate
- Status: `DONE`
- Scope: test verifier acceptance and tamper rejection, report grouping/filtering/determinism, unknown campaign behavior, and CLI exit codes without external requests.
- Acceptance: default Arena/ROCKSOUL CI and general Unittest exercise evidence audit; CodeQL and wheel/entrypoint gates remain green.
- Tests: `tests/test_rocksoul_arena_production.py`, `tests/test_rocksoul_arena_production_cli.py`.

## Current-main recovery note

Stage 2 recovery commit `5b818f839c33150a48818b8f352161fc3ecf7c94` passed its current-main verification. Stage 3 implementation commit `56d9bc11813572cca343f3b556b6042ebc214edd` passed Arena CI [#42030958020](https://github.com/bjo163/agilty/actions/runs/42030958020), ROCKSOUL CI plus package/wheel smoke [#42030958117](https://github.com/bjo163/agilty/actions/runs/42030958117), general Unittest on Python 3.10 and 3.15 [#42030958126](https://github.com/bjo163/agilty/actions/runs/42030958126), and CodeQL Advanced [#42030958006](https://github.com/bjo163/agilty/actions/runs/42030958006). The dedicated Mesh CI remained green from Stage 2 [#42026291726](https://github.com/bjo163/agilty/actions/runs/42026291726); Stage 3 changed no Mesh implementation, and the broad ROCKSOUL suite re-ran offline Mesh contracts across all four OS/Python lanes. The final Stage 3 implementation outcome was 13 successful checks, 2 intentionally skipped distribution-publication checks, zero failures, and zero pending checks. Live production benchmark packs remain deferred. Stage 5 verifies stored campaign integrity and produces per-target reports, but does not independently certify dataset licensing, contamination, methodology, or model quality.


## Stage 5 completion record

- Stage status: `COMPLETE` for immutable campaign verification, deterministic per-target reporting, and offline regression/release-gate coverage.
- Acceptance: RS-F5-013, RS-F5-014 and RS-F5-015 are all `DONE`.
- Explicit exclusion: RS-F5-006 remains `DEFERRED`. Production benchmark quality certification is not claimed and reports must continue to state `quality_certification=NOT_CERTIFIED`.
- Evidence contract: see [Stage 5](rocksoul-stage-5.md) and [Arena production contract](rocksoul-arena-production.md).

## Stage 6 — Product API & Integration

- [x] Add versioned FastAPI product adapter over existing ROCKSOUL stores/router/execution engine.
- [x] Add health, status, provider inventory, route explanation, trace lookup and bounded execution endpoints.
- [x] Require operator API key for execution; require a key for non-loopback bind.
- [x] Reject unknown request fields and bound request size, attempts and time budgets.
- [x] Add optional `rocksoul-api` install extra and `rocksoul-api` console entrypoint.
- [x] Add API contract tests and CI dependencies.
- [x] Document API boundaries, OpenAPI, deployment safety and unsupported features.
- [x] Run current-main CI and wheel/package verification after implementation commit (ROCKSOUL CI #42059676917: four OS/Python lanes plus wheel/sdist build, metadata, wheel install and console-entrypoint smoke tests; Unittest #42059994881 and CodeQL #42059994638 passed on latest main).

## Stage 7 — Next.js Console migration

- [x] Next.js App Router, TypeScript, React 19 and responsive console.
- [x] Signed HTTP-only sessions, 12-hour expiry, Operator and Administrator roles.
- [x] Server-side API proxy; API key never enters browser bundle.
- [x] Overview, provider fleet, route explanation, Mesh nodes/leases, Arena packs/campaigns, trace explorer and bounded execution.
- [x] Administrator-only provider/Mesh controls; bounded operator execution.
- [x] Arena campaign verification and NOT_CERTIFIED claim boundary.
- [x] Persisted light/dark preference and English/Indonesian toggle.
- [x] Playwright browser smoke tests and Docker Compose health-checked deployment topology.
- [x] Legacy HTML routes remain available as compatibility surface.
- [ ] Route-by-route migration of every legacy HTML-only screen remains a separate compatibility backlog.


### Latest-main verification — 2026-11-05

- Final inspected HEAD: `eb890d385d87001657506857916394723d80e02e` on `main`.
- Work was committed directly to `main`; no feature branch or pull request was created.
- Stage 7 Console baseline: `COMPLETE` for the defined product scope. Legacy HTML routes remain available. Route-by-route migration of every legacy HTML-only screen remains a separate compatibility backlog and is not claimed as completed.
- Console CI #42072227021: `SUCCESS` on the final inspected HEAD. Lint, Next.js production build, Playwright Chromium browser tests (2/2), and Docker Compose configuration validation all passed: https://github.com/bjo163/agilty/actions/runs/42072227021
- General Unittest #42072227074: `SUCCESS` on the final inspected HEAD; Python 3.10 and Python 3.15 test lanes passed: https://github.com/bjo163/agilty/actions/runs/42072227074
- CodeQL Advanced #42072226852: `SUCCESS` on the final inspected HEAD: https://github.com/bjo163/agilty/actions/runs/42072226852
- Backend ROCKSOUL CI #42068321403: all Windows/Ubuntu Python 3.10/3.13 lanes plus wheel/sdist validation passed on the immediately preceding backend candidate. Subsequent changes were limited to Console frontend/auth/startup, workflow configuration, and documentation; no backend runtime/API source changed: https://github.com/bjo163/agilty/actions/runs/42068321403
- Security baseline: Next.js and eslint-config-next pinned to 15.5.29; React and React DOM pinned to 19.1.2.
- Console authentication smoke test covers unauthenticated redirect, Operator login, successful session creation, and authenticated landing page.
- Standalone startup now copies `.next/static` and optional `public` assets into the standalone runtime before starting, preventing unhydrated pages in production-style smoke tests.
- Docker Compose topology validates successfully. `.env.rocksoul.example` provides placeholders only; real credentials must be created and configured privately.
- PyPI distribution publication was skipped; no package release was requested.
- A live Coolify deployment was not performed because no deployment target, domain/DNS, or production secrets were supplied. The Compose topology is validated and documented, but runtime deployment must not be represented as completed.
- Arena production quality certification remains `NOT_CERTIFIED`; the separate production dataset/methodology gate remains deferred.



## Stage 8 — P0 Trust & Truth: Work Contract Foundation

### RS-F9-001 — Canonical WorkItem schema
- Status: `DONE` (schema/test scope only)
- Implementation: `g4f/rocksoul_contracts.py`.
- Contract fields: schema version, stable work ID, goal, required acceptance criteria, risk level, bounded execution budget, exact permission identifiers, timezone-aware creation/deadline timestamps, and human-approval requirement.
- Safety: empty permissions deny all tool capabilities; wildcards are rejected; high/critical risk cannot disable human approval; unknown JSON fields fail closed.
- Integrity: canonical serialization and SHA-256 contract digest.
- Tests: `tests/test_rocksoul_contracts.py`.

### RS-F9-002 — Explicit WorkItem lifecycle
- Status: `DONE` (state-transition contract only)
- Implementation: `WorkStatus` and `validate_status_transition` in `g4f/rocksoul_contracts.py`.
- Acceptance: a WorkItem cannot jump from execution directly to accepted; acceptance must pass through `VERIFYING`. Terminal states cannot silently restart. Unverified/uncertain work requires another verification pass before acceptance.
- Tests: happy path, illegal jumps, terminal-state enforcement, uncertain/unverified re-verification, blocked-work resumption.

### RS-F9-003 — Verification profile registry
- Status: `DONE` — registry contract and persistence only.
- Scope: strict versioned profiles, allowlisted adapter identifiers, evidence requirements, severity, independence group, deterministic/side-effect flags, bounded timeout, and immutable SQLite registration.
- Implementation: `g4f/rocksoul_verification.py`, `g4f/rocksoul_verification_store.py`.
- API: authenticated profile register/list/read endpoints.
- Boundary: adapter identifiers are declarations; no dynamic imports, arbitrary callables, or verifier execution are provided. An allowlisted identifier does not mean its adapter is implemented.

### RS-F9-004 — Persisted work contract and lifecycle store
- Status: `DONE` — immutable contract records and append-only lifecycle history.
- Scope: SQLite WorkItem records, immutable contract digest, idempotent creation, atomic expected-state transitions, append-only hash-chained events, readback, and event-chain verification.
- Implementation: `g4f/rocksoul_work_store.py`.
- Safety: SQLite `BEGIN IMMEDIATE` serializes transitions; secrets must not be placed in goal/evidence/event payloads. Hash chaining detects accidental or unsophisticated mutation; it is not an external signature or WORM guarantee.

### RS-F9-005 — WorkItem API integration without false transport success
- Status: `DONE` — API foundation and execution trace linkage.
- Scope implemented: authenticated WorkItem create/list/read/transition/event-chain endpoints; profile register/list/read endpoints; per-criterion verifier execution endpoint; optional `work_id` on legacy-compatible `POST /api/v1/execute`.
- Acceptance: execution trace is linked only to a RUNNING WorkItem; exact `model.execute` permission is required; approval/deadline gates are enforced; wall-time/attempt budgets are capped; unsupported token/cost budgets fail closed; response keeps transport separate and reports `task_outcome=unverified`; provider success never auto-accepts work.
- Follow-through: Console WorkItem creation/readback, profile registration, bounded artifact upload/verification, and native `execution_runs.work_id` correlation are now implemented under RS-F9-008/009.

### RS-F9-006 — WorkItem CLI and operator readback
- Status: `DONE` — operator CLI and local artifact verification.
- Implementation: `rocksoul-work` / `python -m g4f.rocksoul_work_cli` supports `profile-register`, `profile-list`, `profile-get`, `create`, `get`, `list`, `transition`, `verify`, and `verify-chain`.
- Acceptance: JSON output; verification reads exact local artifact bytes; state changes require explicit expected and target statuses.

### RS-F9-007 — Executable verifier adapters and tamper-evident evidence receipts
- Status: `FOUNDATION` — all five allowlisted deterministic built-in adapters implemented; external trust remains open.
- Implementation: `g4f/rocksoul_verifier_engine.py` implements all five allowlisted deterministic adapters: `artifact_digest`, bounded `json_schema`, pytest JUnit XML receipts, captured HTTPS contract receipts, and content-addressed `source_provenance`. It computes SHA-256 from supplied bytes, caps artifact/schema sizes and schema complexity, emits provenance-bearing evidence, and fails closed for unimplemented adapter identifiers.
- Persistence: verifier result/evidence rows are linked into the WorkItem event chain by a canonical receipt digest; acceptance checks the latest result for every required criterion.
- Remaining: external source authenticity, independent acquisition, and cryptographically authenticated verifier identity.

### RS-F9-008 — ExecutionEngine correlation and outcome separation
- Status: `DONE` — API, event ledger, and native execution row correlation.
- Scope: optional WorkItem ID is linked to the persisted execution request ID and transport outcome through an immutable WorkItem event and `execution_runs.work_id`; legacy execution requests remain unchanged.
- Acceptance: provider transport success cannot auto-transition a WorkItem to ACCEPTED; explicit verifier execution and a separate transition are required.
- Migration: existing SQLite databases receive the nullable `work_id` column and index idempotently.

### RS-F9-009 — Console WorkItem & Evidence Cockpit
- Status: `VERIFYING` — WorkItem cockpit, immutable verifier profile, bounded artifact verification, signed administrator approval workflow, evidence diff, and metadata-only evidence bundle export implemented; awaiting final CI certification.
- Scope: authenticated Console navigation, administrator-only WorkItem creation with deny-all default permissions and optional exact `model.execute` grant, risk/approval selection, signed administrator approve/reject controls, guarded expected-state lifecycle transitions, WorkItem list/outcome counters/digest/detail/event-chain readback, profile registration/listing, bounded artifact upload (1 MiB), browser-side SHA-256, per-criterion verifier execution, latest-versus-previous evidence diff, and metadata-only evidence bundle export.
- Implementation: `frontend/rocksoul-console/src/app/page.tsx`, authenticated API proxy, signed server route `frontend/rocksoul-console/src/app/api/approvals/[workId]/route.ts`, `/api/v1/verification-profiles`, `/api/v1/work-items/{work_id}/criteria/{criterion_id}/verify`, and `/api/v1/work-items/{work_id}/approval`, `/api/v1/work-items/{work_id}/evidence-diff`, and `/api/v1/work-items/{work_id}/evidence-bundle`.
- Security: API keys and approval HMAC secret remain server-side; approval payload binds contract digest, configured admin principal, decision, timestamp, and nonce; API enforces five-minute freshness and replay protection; approvals are append-only hash-chain events; high/critical WorkItems cannot enter RUNNING or execute without latest approved decision; profile versions are immutable; artifact size is bounded; no arbitrary verifier code or network fetch is introduced.
- Tests: API coverage for signed approval, invalid signatures, replay rejection, approval-gated lifecycle, and approval read models; existing Playwright role-boundary checks. Current final-main CI is the release gate.
- Remaining: individual human identity/SSO and separation-of-duties policy, signed external evidence/verifier identity, and independent remote artifact acquisition. Export is metadata-only; raw artifact payload retention is intentionally not included.

### Stage 8 verification boundary
- WorkItem contracts, immutable profile definitions/persistence, lifecycle storage, authenticated API, operator CLI, execution trace linkage, native execution correlation, Console WorkItem cockpit, profile registration, bounded artifact upload/verification UI, and five deterministic verifier adapters are implemented.
- All five allowlisted adapter identifiers execute through bounded built-in code. HTTP receipts and pytest reports are caller-supplied captures; source provenance proves digest binding only. None establishes remote source authenticity or cryptographically authenticated verifier identity.
- Acceptance requires a latest persisted built-in verifier PASS for every required criterion and a valid event/receipt hash chain; caller-supplied PASS payloads are rejected.
- The verifier hashes the exact bytes supplied by the caller; it does not prove the truth of the source URI or authenticate a remote artifact.
- Console WorkItem creation/readback, profile registration, bounded artifact verification UI, and server-signed administrator approval are implemented. Approval is bound to a configured principal and credential, not a verified natural person; SSO, individual identity proof, and separation of duties remain open. Independent artifact acquisition, signed external evidence, and authenticated external verifier identity also remain open.
- Existing F1–F7 execution, Mesh, Arena, API, and Console contracts remain compatibility requirements.


## Stage 9 — WorkGraph composition foundation

### RS-F10-001 — Strict deterministic WorkGraph DAG contract
- Status: `FOUNDATION` — pure contract and deterministic planning helpers implemented; integration is not complete.
- Implementation: `g4f/rocksoul_work_graph.py`.
- Scope: versioned graph/node schema, strict identifiers and fields, unique node/WorkItem references, dependency validation, deterministic topological layers, readiness calculation from an explicit completed-node set, transitive descendants, canonical digest.
- Safety limits: maximum 256 nodes, 2,048 edges, 64 dependencies per node, and 64 topological layers; cycles and unknown dependencies fail closed.
- Tests: `tests/test_rocksoul_work_graph.py` covers ordering, readiness, descendants, digest stability, round-trip, duplicate IDs, missing dependencies, cycles, depth/size bounds, and malformed inputs.
- Trust boundary: the pure helper readiness is structural only. Caller-supplied completed IDs are not WorkItem acceptance proof. Authoritative store-level readiness is tracked under RS-F10-003.
- Design: [WorkGraph contract and integration gates](rocksoul-work-graph.md).

### RS-F10-002 — Persistent graph registry and event ledger
- Status: `FOUNDATION` — immutable graph registration, bounded readback, and creation-event integrity checks implemented; CI certification pending.
- Implementation: `g4f/rocksoul_work_graph_store.py`.
- Acceptance implemented: idempotent registration for identical graph digest, immutable graph ID conflict rejection, bounded pagination, canonical graph digest verification, sequence/previous-hash/event-hash checks, and malformed-payload fail-closed behavior.
- Tests: `tests/test_rocksoul_work_graph_store.py` covers idempotency, immutable conflict, readback/pagination, event tampering, graph mutation, and missing graph.
- Remaining: schema migration is create-if-not-exists only; no graph update/versioning API exists. Exact-main CI must pass before this item can be marked DONE.

### RS-F10-003 — Authoritative dependency resolver
- Status: `FOUNDATION` — read-only resolver implemented; CI certification and atomic dispatch-time recheck remain pending.
- Implementation: `WorkGraphStore.resolve_readiness(graph_id, WorkItemStore)`.
- Acceptance implemented: every referenced WorkItem must exist and pass its event/evidence-chain integrity check; status and evidence are read from one SQLite snapshot; only `accepted` dependencies satisfy downstream nodes; missing/terminal-failed dependencies block descendants; pending dependencies produce waiting nodes; corrupted/malformed contracts fail closed.
- Tests: `tests/test_rocksoul_work_graph_store.py` and `tests/test_rocksoul_api.py` cover pending/waiting, missing WorkItems, malformed/tampered evidence, verified acceptance unlocking downstream nodes, API authentication, and immutable conflict.
- Boundary: read-only readiness snapshot; it does not reserve/claim a child or eliminate the check/use race. Dispatcher must re-check atomically before execution.

### RS-F10-004 — Graph budget and authority composition
- Status: `TODO`
- Acceptance: aggregate wall-time/attempt/token/cost ceilings are enforced without expanding any child WorkItem budget or permission; approval gates remain per child.

### RS-F10-005 — Graph lifecycle, cancellation, and failure propagation
- Status: `TODO`
- Acceptance: bounded retries, deadlines, cancellation, optional-node semantics, uncertain/blocked propagation, and no implicit restart of terminal WorkItems.

### RS-F10-006 — WorkGraph API, CLI, and Console
- Status: `FOUNDATION` — authenticated API registry/readiness, offline operator CLI, and read-only Console registry/readiness cockpit implemented; execution dispatch remains TODO.
- API: `GET|POST /api/v1/work-graphs`, `GET /api/v1/work-graphs/{graph_id}`, `GET /api/v1/work-graphs/{graph_id}/readiness`, and `GET /api/v1/work-graphs/{graph_id}/verify-chain`; all require operator API key.
- CLI: `rocksoul-work-graph` / `python -m g4f.rocksoul_work_graph_cli` supports create/list/get/verify/readiness.
- Packaging/CI: console entrypoint added to `setup.py`; ROCKSOUL CI smoke-tests module and installed command.
- Tests: API auth/create/idempotency/readiness/immutable conflict and CLI create/list/verify/readiness.
- Console: new WorkGraph tab lists immutable graphs, registers graph JSON for administrators, and displays readiness states, dependency blockers, and integrity errors. Playwright operator navigation smoke test added.
- Remaining: expected-version graph revisions, atomic scheduler claims, and end-to-end proof that child approval/verification gates cannot be bypassed.

### Stage 9 completion rule
- Stage 9 is not complete until RS-F10-002 through RS-F10-006 are implemented and CI-certified on the exact final `main` commit. RS-F10-001 through RS-F10-003 have foundation implementations; RS-F10-006 has API/CLI foundations only.
- The read-only Console graph visualization is shipped. No worker scheduler, aggregate budget enforcement, atomic dispatch claims, or cancellation/recovery orchestration is claimed.


## Latest-main continuation note — 2026-11-06

- WorkGraph now has a bounded DAG contract, immutable SQLite registry, hash-chain verification, snapshot-consistent authoritative readiness resolver, authenticated API, offline CLI, and read-only Console registry/readiness cockpit.
- The resolver only treats a dependency as satisfied when the referenced WorkItem is `accepted` and its event/evidence chain verifies. It does not dispatch tasks or reserve budgets.
- Added unit/API/CLI tests, including a positive path where a real built-in verifier PASS and WorkItem acceptance unlocks the downstream node.
- Added package entrypoint and ROCKSOUL CI smoke coverage for `rocksoul-work-graph`; Console Playwright navigation coverage was also extended.
- All changes were committed directly to `main`; no branch or PR was created.
- CI certification on the exact final HEAD is still pending/unconfirmed. The visible Vercel status is a build-rate-limit failure and is not a ROCKSOUL unit-test result.



## Product scope reset — 2026-11-06 (authoritative)

**ROCKSOUL is the UI replacement for g4f's built-in HTML/web interface. It is not a gateway, router, provider registry, inference runtime, or execution control plane.** The existing g4f Python runtime and API remain the sole source of truth.

### Scope correction

- [x] Reset product identity, narrative, blueprint, roadmap and README to UI-first.
- [x] Reclassify the existing Next.js operator console as optional/experimental tooling, not the primary ROCKSOUL user interface.
- [x] Clarify that Arena, Mesh, WorkItem, WorkGraph, verifier/evidence and operator APIs are optional modules and must not be required for ordinary chat.
- [x] Inventory the GUI route registry in g4f/gui/server/website.py and document route → handler → runtime/API behavior in docs/rocksoul-ui-route-inventory.md. Per-page interaction/session parity remains open.
- [x] Create the initial bundled ROCKSOUL chat-first frontend shell (HTML/CSS/JS) with desktop/mobile layout.
- [x] Mount the frontend through the existing g4f GUI serving boundary; / and /chat/ use it by default and ROCKSOUL_UI_ENABLED=0 restores legacy home/chat HTML.
- [x] Implement initial incremental SSE text streaming through the existing /v1/chat/completions API; real-provider/disconnect regression tests remain open.
- [x] Populate the model selector from the existing /v1/models endpoint; no duplicate registry.
- [x] Implement browser-local conversation history plus explicit opt-in server sharing/restoration through the existing /backend-api/v2/chat/<id> endpoint. Shared links are readable by anyone possessing the link; ordinary conversations remain local by default.
- [ ] Add desktop/mobile, dark/light, keyboard/accessibility and Indonesian/English UI verification.
- [ ] Make / and /chat/ serve ROCKSOUL by default only after parity tests pass.
- [ ] Keep a documented legacy UI rollback path until at least one certified release.
- [ ] Simplify canonical Docker/Coolify deployment to one g4f Python runtime serving API plus ROCKSOUL assets; operator stack remains optional.
- [ ] Remove legacy HTML assets only after route parity, API/SDK compatibility, UI tests and deployment checks pass.

### Important status correction

The existing frontend/rocksoul-console is an operator cockpit and is **not** the requested HTML replacement. Its successful build or E2E checks do not certify ROCKSOUL chat UI. The existing docker-compose.rocksoul.yml is an optional operator stack and is **not** the canonical deployment for the UI-only product.

### Completion rule

ROCKSOUL UI replacement is not complete until the actual frontend is mounted in g4f/gui, / and /chat/ use it, ordinary chat/streaming/history/model selection work through the existing Python runtime, and the exact final main commit passes the required CI and compatibility tests. Do not mark the unchecked tasks complete based on documentation or mockups.


### UI hardening follow-up — 2026-11-06

- Fixed stable asset URL caching: ROCKSOUL CSS/JS now revalidate instead of being cached immutable for one year, preventing stale UI assets after deployment.
- Fixed SSE EOF handling: a final event without a trailing newline is now consumed.
- Added Stop generation via AbortController; partial streamed text is retained in browser-local history. This represents client disconnect, not a guarantee of provider-side cancellation.
- CI now runs function-style ROCKSOUL tests with pytest (the previous unittest discovery command did not execute plain pytest test functions).
- CI triggers now include bundled g4f GUI assets and validate that all three ROCKSOUL files are present in the built wheel.
- Exact-main CI, real-provider streaming, full browser QA, and Docker/Coolify runtime smoke tests remain release gates.


### Browser smoke coverage — 2026-11-06

- [x] Add Playwright smoke for ROCKSOUL shell/assets, model discovery, normal mocked SSE chat completion, EOF without trailing newline, non-2xx provider errors, Stop/AbortController, browser-local history reload, and blocked-localStorage resilience.
- [x] Make browser-local history/theme storage failures non-fatal so restricted browser contexts can still use the chat UI.
- [ ] Run the browser workflow successfully on the exact final `main` commit; no successful run has been confirmed yet.
- [ ] Add live-provider streaming and upstream cancellation verification.
- [ ] Complete rich returned-media rendering, provider-specific auth polling, legacy sub-page parity, full accessibility/localization QA, and Coolify runtime certification.

### UI cutover clarification

- `/` and `/chat/` are provisionally served by ROCKSOUL and can be rolled back with `ROCKSOUL_UI_ENABLED=0`.
- Other legacy GUI routes remain on their existing handlers/pages. This is not full replacement of every built-in g4f HTML screen.
- The mocked Playwright test validates browser wiring only; it does not prove real provider availability or production deployment.
- The visible Vercel status is a build-rate-limit failure, not a ROCKSOUL test result. GitHub Actions status for the latest commit is not yet confirmed.


### Unified GUI migration — 2026-11-06

- [x] Replace the chat-only shell navigation with a single ROCKSOUL workspace navigation.
- [x] Migrate overview and chat routes.
- [x] Migrate provider catalog and provider detail routes using the existing provider/model APIs.
- [x] Migrate status and model catalog using existing runtime status/version/model APIs.
- [x] Migrate usage statistics using the existing usage ledger API.
- [x] Migrate backend logs using the existing diagnostics endpoint.
- [x] Migrate Agent and Browser pages to live WebMCP tool discovery and explicit per-invocation confirmed execution through the existing endpoint; no tools are fabricated and no second agent runtime is started.
- [x] Migrate Playground to the existing model/chat API.
- [x] Migrate Apps to the existing PA provider registry.
- [x] Migrate Private utilities to the existing JSON/HAR cookie upload endpoint; cookie contents are never exposed in the UI. Remote access requires network/reverse-proxy protection.
- [x] Preserve API, media/file, dist asset, metadata, historical versioned routes, and nested non-HTML assets under legacy GUI paths.
- [x] Add route regression coverage proving nested chat/apps/private static assets continue through their original handlers.
- [x] Add Flask route coverage for all primary GUI page handlers and verify legacy rollback behavior when `ROCKSOUL_UI_ENABLED=0`.
- [x] Extend Playwright mocks and browser checks to every migrated workspace page, including confirmed WebMCP tool invocation.
- [ ] Verify all route/browser workflows green on exact final main; the current GitHub Actions runs are queued, not certified.
- [ ] Verify live-provider chat, OAuth/device-flow behavior, and upstream cancellation semantics.
- [x] Add native image/audio/video attachment submission through existing /backend-api/v2/conversation; [ ] complete rich returned-media rendering and document extraction parity.
- [x] Expose provider login, health, and quota controls through existing g4f endpoints; [ ] verify live OAuth/device-flow behavior.
- [x] Add explicit WebMCP confirmation and metadata-only invocation outcome logging; [ ] add fine-grained permission policy and searchable audit UX if required.
- [x] Add keyboard focus-visible, reduced-motion and high-contrast affordances.
- [x] Validate wheel assets, Compose configuration, and Docker image asset inclusion in CI.
- [ ] Complete screen-reader/contrast/responsive QA, Indonesian/English localization, and live Coolify runtime smoke test.

**Migration boundary:** the primary live GUI pages now use ROCKSOUL. Historical snapshots, static assets, media delivery, APIs, and arbitrary legacy content URLs are deliberately preserved. The remaining items above are real parity and release gates; do not mark them done based only on route-shell mounting or mocked browser tests.



### Final hardening continuation — 2026-11-06

- [x] Audit exact main source for existing g4f capabilities before adding any UI-owned backend.
- [x] Persist and restore conversations only after explicit Share chat consent, using the existing /backend-api/v2/chat/<id> endpoint. Normal conversations stay browser-local. The UI warns that anyone with the link can read shared content.
- [x] Add browser test coverage for shared-link restore and the opt-in share flow.
- [x] Add media attachment picker and submit image/audio/video files as multipart uploads to existing /backend-api/v2/conversation; no upload microservice or second gateway was introduced.
- [x] Add provider login, health, and quota controls using existing /backend-api/v2/oauth/<provider>, /backend-api/v2/health/<provider>, and /backend-api/v2/quota/<provider> endpoints.
- [x] Record metadata-only WebMCP invocation outcomes via existing /backend-api/v2/log; do not persist raw tool arguments or secrets in the audit event.
- [x] Add keyboard focus-visible and prefers-contrast affordances; preserve reduced-motion support.
- [x] Expand Playwright mocks for shared conversation restoration, media attachment submission, provider health/login controls, and confirmed tool execution.
- [x] Add canonical Docker image build, bundled ROCKSOUL asset check, and persistent config-volume write smoke test to ROCKSOUL CI, alongside wheel and Compose checks.
- [x] Parse-check the current app.js and browser E2E module source.
- [ ] Await GitHub Actions execution on the final exact main HEAD. Runs observed for this continuation are queued; do not infer success from queued status.
- [ ] Verify actual provider streaming, OAuth/device-code polling, returned image/audio/video rendering, and upstream disconnect behavior with configured provider credentials.
- [ ] Perform real Coolify deployment and HTTP smoke test. This cannot be certified from repository-only access.
- [ ] Complete legacy Apps/private nested page interaction parity, full screen-reader QA, and Indonesian/English localization.

**Privacy boundary:** Share chat is opt-in because the existing g4f share endpoint stores a JSON snapshot in the server bucket and exposes it to anyone with the generated ID. Unshared conversations are not sent to that endpoint. Attachment files are uploaded only when the user sends a message containing selected media.

**Verification boundary:** source syntax checks are not a substitute for executing Playwright/Pytest. Mocked browser coverage is not live-provider validation. Docker CI configuration is not a successful Docker build until its job completes; a repository commit is not a live Coolify deployment.



### Whole-project cross-check — 2026-11-06

- [x] Re-read the current main route integration, frontend, backend API contracts, packaging, Docker, Compose, tests, and CI workflow definitions.
- [x] Fix privacy regression: successful private chats no longer write snapshots to the server; only already-shared conversations are synchronized.
- [x] Fix failed-share UX: do not copy a share URL unless the server accepted the snapshot; restore the conversation to private state on failure.
- [x] Require cryptographically strong share IDs, using getRandomValues when randomUUID is unavailable; upgrade weak legacy/local IDs before server persistence.
- [x] Add Playwright regression assertions that private chats cause zero server writes, explicit sharing creates the snapshot, weak local IDs are upgraded, and failed sharing does not copy a dead URL.
- [x] Restrict extension-card/link URL schemes to same-origin paths or HTTP(S); reject javascript: and other active schemes.
- [x] Remove the ineffective per-request API-key field from Private utilities. The existing upload handler does not validate that request key; the UI now warns operators to protect remote access at the network/reverse-proxy layer.
- [x] Remove the Google Fonts network dependency; the bundled UI uses system font stacks for offline/self-hosted deployments.
- [x] Add Flask test-client coverage for actual registered route mappings and legacy rollback, not only direct handler calls.
- [x] Fix literal escaped newline in finalization checklist.
- [x] Split ROCKSOUL UI CI from historical optional operator-module suites; run the focused Flask GUI contract suite cross-platform and keep package/Docker gates dependent on it.
- [ ] Re-run exact-main GitHub Actions after CI scope and UI test fixes; do not mark package or Docker jobs green until they complete.
- [ ] Harden or externally protect WebMCP tool invocation: browser confirmation is not server authorization, and the existing endpoint accepts direct calls.
- [ ] Harden or externally protect the existing cookie/HAR upload endpoint: it only checks whether G4F_API_KEY is configured for non-loopback access and does not validate a per-request key in this handler.
- [x] Configure G4F_CONFIG_DIR=/data/g4f and a named g4f-data Docker volume; prepare directory ownership in the image and add a Docker CI write smoke test. Compose uses pull_policy: build to avoid accidentally running a pre-existing upstream image instead of this checkout.
- [x] Bind the Selenium/VNC host port to 127.0.0.1 so the default VNC password is not exposed on every network interface.
- [ ] Verify the named volume and local-source build behavior in a real Coolify deployment.
- [ ] Verify production Coolify port exposure, reverse-proxy authentication, persistence, and real deployment behavior.
- [x] Render safe Markdown blocks and fenced code blocks with copy controls; raw HTML is never injected from model output.
- [x] Add per-message copy, edit-last-user-turn, and delete controls.
- [ ] Add regenerate, export, and richer conversation management.
- [ ] Complete real-provider, OAuth device-flow, returned-media rendering, localization, screen-reader, and responsive certification.

**Security review:** the browser confirmation and metadata log are UX conveniences, not authorization or compliance-grade audit controls. The existing chat share endpoint is an unauthenticated bearer-link API: anyone with the ID can read or replace the snapshot. Do not put secrets or credentials into a shared chat.


### UI parity continuation — 2026-11-06

- [x] Add a dependency-free DOM-based Markdown renderer for chat messages, including headings, paragraphs, lists, blockquotes, inline emphasis/code, safe links, and fenced code blocks with copy controls.
- [x] Keep model output as text nodes; raw HTML is never interpreted. Unsafe link schemes are rejected by the existing URL allowlist.
- [x] Add browser smoke coverage for Markdown emphasis, fenced code, and the copy-code action.
- [x] Scope ROCKSOUL CI to the UI route/asset contract tests rather than unrelated optional operator-module test suites; remove optional CLI smoke gates from the UI release workflow.
- [x] Fix Flask direct-passthrough test response handling for `send_file` responses.
- [x] Verified checkpoint `ac1010f4`: all four ROCKSOUL UI route/asset test matrix jobs passed, and the wheel/sdist, Compose validation, Docker build, bundled asset, and persistent-volume smoke job passed.
- [x] Fix the missing `new-chat` DOM ID and add a regression assertion so startup navigation handlers cannot silently break the shell.
- [ ] Await fresh browser smoke and full CI on the latest `main`; live provider and Coolify checks remain external release gates.

- [x] Add browser smoke coverage for assistant-message copy in addition to code-block copy.


### Latest chat parity pass

- Added text-only assistant regeneration by replaying the preceding user turn through the existing `/v1/chat/completions` endpoint; regeneration for file attachment turns is visibly disabled until g4f attachment replay semantics are confirmed.
- Added explicit Markdown (`.md`) and JSON (`.json`) conversation exports. Exports are generated client-side from the current local conversation.
- Added Markdown raster image, audio, and video rendering. Raster data URLs are limited to PNG/JPEG/GIF/WebP base64; external media links must pass HTTP(S)/same-origin URL validation. Raw HTML and SVG data URLs are not executed.
- Fixed a stale `key.value` reference in the Private utility upload success handler that could throw after a successful upload.
- Added browser and Flask regression coverage for export controls, media elements, regeneration, and Private utility script safety.

- [x] Add browser-local conversation history search, rename, pin/unpin, delete, and clear-all controls; clearly distinguish local deletion from server-shared snapshot deletion.


### Returned media rendering continuation — 2026-11-06

- [x] Consume `urls` and `alt` metadata from the existing g4f conversation SSE events without adding a new backend or media service.
- [x] Render returned image URLs as safe Markdown images and returned video/audio URLs as native browser media controls when their file extensions are recognized.
- [x] Preserve the same-origin/HTTP(S) URL allowlist; reject unsafe schemes and keep raw HTML/SVG execution disabled.
- [x] Extend Playwright attachment-flow coverage to assert returned image, video, and audio elements render from the existing conversation endpoint.
- [ ] Verify document extraction/upload parity and real-provider media behavior with configured providers.
- [ ] Verify exact-main GitHub Actions completion after this change.
- [ ] Coolify deployment testing is explicitly not required by project owner; do not spend time or block on it.
