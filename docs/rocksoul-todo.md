# ROCKSOUL Product Backlog

> Canonical detailed execution backlog for the ROCKSOUL product layer. GitHub Issues are enabled in this repository; this file remains the technical source of truth until a later governance pass synchronizes individual tasks with GitHub Issues.

## Product identity

ROCKSOUL is the product/control-plane layer built on top of the existing g4f runtime. The runtime remains the provider execution substrate. ROCKSOUL owns routing intelligence, execution policy, health evidence, traceability, recovery, Mesh coordination, Arena benchmarking, and product-facing interfaces. ROCKSOUL does not duplicate provider implementations.

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
- Status: `FOUNDATION` — WorkItem cockpit plus immutable verifier profile and bounded artifact verification workflows delivered; awaiting current CI certification.
- Scope: authenticated Console navigation, administrator-only WorkItem creation with deny-all default permissions and optional exact `model.execute` grant, risk/approval selection, guarded expected-state lifecycle transitions, WorkItem list/outcome counters/digest/detail/event-chain readback, profile registration/listing, bounded artifact upload (1 MiB), browser-side SHA-256, and per-criterion verifier execution.
- Implementation: `frontend/rocksoul-console/src/app/page.tsx`, authenticated API proxy, `/api/v1/verification-profiles`, and `/api/v1/work-items/{work_id}/criteria/{criterion_id}/verify`.
- Security: proxy forwards API key for protected GET and POST routes; API keys remain server-side; writes remain administrator-only; profile versions are immutable; artifact size is bounded; no arbitrary verifier code or network fetch is introduced.
- Tests: Playwright operator navigation assertion plus API profile registry authentication, immutable-version, and allowlist tests. Current final-main CI is the release gate.
- Remaining: cryptographically attributable human approval, signed external evidence/verifier identity, independent remote artifact acquisition, rich evidence diff, and artifact bundle export.

### Stage 8 verification boundary
- WorkItem contracts, immutable profile definitions/persistence, lifecycle storage, authenticated API, operator CLI, execution trace linkage, native execution correlation, Console WorkItem cockpit, profile registration, bounded artifact upload/verification UI, and five deterministic verifier adapters are implemented.
- All five allowlisted adapter identifiers execute through bounded built-in code. HTTP receipts and pytest reports are caller-supplied captures; source provenance proves digest binding only. None establishes remote source authenticity or cryptographically authenticated verifier identity.
- Acceptance requires a latest persisted built-in verifier PASS for every required criterion and a valid event/receipt hash chain; caller-supplied PASS payloads are rejected.
- The verifier hashes the exact bytes supplied by the caller; it does not prove the truth of the source URI or authenticate a remote artifact.
- Console WorkItem creation/readback, profile registration, and bounded artifact verification UI are implemented. A cryptographically attributable human-approval workflow, independent artifact acquisition, signed external evidence, and authenticated external verifier identity remain open. High/critical WorkItems still require approval, and execution remains fail-closed while a trustworthy approval identity/recording path is not available.
- Existing F1–F7 execution, Mesh, Arena, API, and Console contracts remain compatibility requirements.
