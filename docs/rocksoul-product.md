# ROCKSOUL Product

## Product identity

**ROCKSOUL is an Evidence-Driven Intelligence & Execution Control Plane.**

It governs how models, tools, agents, and execution nodes are selected, composed, executed, verified, observed, and improved. It is built around the existing g4f runtime substrate and does not duplicate or replace provider implementations.

## Product thesis

The next AI infrastructure advantage is not the number of providers connected or tokens generated. It is the ability to turn uncertain model behavior into dependable, bounded, verifiable user outcomes.

**Product promise:** Every decision is explainable. Every execution is traceable. Every outcome is verifiable. Every policy change is reversible.

## What ROCKSOUL does today

The current implementation provides a meaningful control-plane foundation:
- provider discovery and capability-aware route explanation;
- bounded execution, retry classification, health evidence, quarantine and recovery;
- persistent traces and execution history;
- authenticated Mesh node coordination, leases and failure isolation;
- deterministic Arena benchmark foundation and immutable campaign-integrity verification;
- product CLI, versioned FastAPI adapter, and Next.js operator console.

These capabilities are not equivalent to a complete autonomous agent platform. The current Arena production reports explicitly remain `quality_certification=NOT_CERTIFIED`.

## Work Contract Foundation — implemented

The current P0 foundation includes:

- Canonical WorkItem, bounded budgets, exact permissions, risk/approval policy, strict schema parsing, and lifecycle validation.
- Immutable SQLite WorkItem contracts, idempotent creation, atomic expected-state transitions, append-only hash-chained events, and tamper readback.
- Immutable versioned verification profiles with allowlisted adapter identifiers and evidence requirements.
- Built-in deterministic `artifact_digest` and bounded `json_schema` verifier adapters. Other declared adapter IDs fail with `ERROR`.
- Persisted verifier results and evidence receipts linked to lifecycle events; acceptance requires the latest persisted PASS for every required criterion.
- Authenticated API and `rocksoul-work` CLI for contracts, profiles, verification, transitions, and event-chain checks.
- Optional API-level WorkItem-to-execution trace linkage with exact `model.execute` permission, deadline/approval gates, and wall-time/attempt budget caps; provider transport success remains separate from task outcome.

**Scope boundary:** the engine verifies the exact bytes supplied by the caller; it does not prove the truth of the source URI or authenticate a remote artifact. `pytest`, `http_contract`, and `source_provenance` adapters remain unimplemented. Native execution_runs foreign-key correlation and Console workflow remain future work. See [Work Contracts & Verification Profiles](rocksoul-work-contracts.md).

## What ROCKSOUL is becoming

The strategic direction expands the control plane from request routing to a full **intent-to-outcome loop**:

```text
intent → work contract → plan → capability selection → bounded execution
       → evidence ledger → task-specific verification → outcome
       → offline learning → controlled policy promotion
```

The core unit becomes a WorkItem with a goal, constraints, acceptance criteria, permissions, budgets, and evidence requirements—not simply a prompt or completion.

## Product pillars

### Route
Select eligible models/tools/nodes using verified capabilities, health, historical outcomes, cost, latency, risk, and diversity. Hard policy constraints always precede ranking.

### Execute
Coordinate work through existing runtime adapters. Enforce total budgets, bounded retries, scoped permissions, idempotency, checkpoints, and safe cancellation.

### Verify
Judge the delivered artifact or postcondition against task-specific acceptance criteria. Use deterministic checks where possible and independent evaluators where necessary. Model confidence and consensus are not proof.

### Explain
Preserve candidate eligibility, rejected alternatives, policy revision, evidence, and counterfactual route rationale.

### Recover
Classify failures, isolate unhealthy resources, retry only with a justified changed hypothesis, and stop or escalate when uncertainty exceeds policy.

### Learn
Use verified outcomes to propose offline policy improvements. Replay, evaluate on held-out workloads, stage rollout, monitor, and roll back. No silent production self-modification.

### Coordinate
Use Mesh for authenticated node identity, bounded leases, capability/capacity selection, and failure isolation. Online status alone does not imply trust.

### Observe
Expose health, decisions, traces, evidence, campaign results, policy changes, and operator actions through CLI/API/Console.

## Architecture boundary

ROCKSOUL owns policy, coordination, evidence, verification contracts, and product interfaces. The underlying runtime owns provider-specific transports and integrations.

ROCKSOUL must not become a second provider registry or fork provider behavior merely to gain execution control.

## Anti-slop contract

ROCKSOUL must not declare success from HTTP 200, non-empty text, a model's self-evaluation, or majority vote alone. Quality is evaluated against the task's acceptance criteria.

A work item can finish as:
- `ACCEPTED` — required checks passed with sufficient evidence;
- `UNVERIFIED` — output exists but proof is incomplete;
- `REJECTED` — acceptance criteria failed;
- `UNCERTAIN` — evidence conflicts or is insufficient;
- `BLOCKED` — policy, permission, or dependency prevents safe execution;
- `CANCELLED` / `EXPIRED` — execution stopped by lifecycle rules.

Verification must be task-specific: code requires test/build evidence; factual research requires source-to-claim provenance; data work requires schema and invariant checks; tool workflows require permission and postcondition receipts.

## AGI-ready, not AGI-claiming

ROCKSOUL is designed to remain relevant as models become more general, multimodal, persistent, tool-using, and autonomous. This means stable work contracts, capability passports, provenance-aware memory, work graphs, scoped action permissions, long-running checkpoints, multi-agent role separation, and controlled learning.

These are future architectural targets. ROCKSOUL does not claim AGI, consciousness, or general competence. Any increase in autonomy must be earned through independent evaluation, explicit authority, bounded budgets, sandboxing, auditability, and rollback.

## North-star metric

**Verified Useful Outcome Rate (VUOR):** eligible work items that satisfy their declared acceptance criteria with evidence, within configured cost/time/risk budgets.

Report by task family and verifier confidence. Do not collapse correctness, safety, usefulness, evidence quality, and efficiency into one opaque score.

## Current implementation vs future direction

| Area | Current state | Future direction |
|---|---|---|
| Runtime | Existing g4f substrate | Reusable multi-runtime adapters |
| Routing | Explainable capability-aware foundation | Historical, contextual, step-level routing |
| Execution | Bounded attempts/time, traceability, persisted WorkItems, verifier receipts, hash-chained lifecycle and API-level execution trace linkage | Native execution_runs correlation, checkpoints, scoped tools |
| Reliability | Health, quarantine, recovery | Drift-aware capability re-verification |
| Mesh | Authenticated nodes and leases | Attestation, isolation, data locality |
| Arena | Deterministic foundation and integrity audit | Adversarial, held-out, provenance-rich evaluation |
| API/Console | Authenticated WorkItem lifecycle, verifier execution, profile registry, and API-level trace linkage; Console remains a foundation | Native execution correlation, outcome cockpit and policy lifecycle |
| Anti-slop | Artifact SHA-256 and bounded JSON Schema adapters with persisted evidence receipts | Code/test, HTTP-contract, source-provenance and independent evaluators |
| Learning | Evidence capture foundation | Offline learning and controlled policy promotion |
| Memory/autonomy | Not yet a complete product capability | Provenance-aware memory and bounded long-running workflows |


## Product roadmap

- **Horizon 0 — Trust:** evidence contracts, capability passports, privacy and anti-slop semantics.
- **Horizon 1 — Outcomes:** task-specific verification and outcome records.
- **Horizon 2 — Adaptive intelligence:** historical outcome routing, candidate recall, contextual retrieval, cost/quality cascades.
- **Horizon 3 — Agentic control:** WorkGraph, step-level routing, checkpoints, scoped tool permissions, verified repair.
- **Horizon 4 — Controlled autonomy:** provenance-aware memory, Mesh attestation, multimodal and multi-agent governance.
- **Horizon 5 — General intelligence operations:** only capabilities proven reliable and safe on independent evaluations.

See:
- [Product narrative and manifesto](rocksoul-narrative.md)
- [Strategic blueprint](rocksoul-blueprint.md)
- [Future roadmap and research hypotheses](rocksoul-future-roadmap.md)
- [Current implementation backlog](rocksoul-todo.md)
- [API contract](rocksoul-api.md)
- [Mesh contract](rocksoul-mesh.md)
- [Arena contract](rocksoul-arena.md)

## Product decision filter

Every proposed feature must identify its user outcome, evidence of improvement, failure modes, permission and budget boundaries, reproducibility, rollback path, and overlap with the existing runtime. Otherwise it remains research—not production scope.
