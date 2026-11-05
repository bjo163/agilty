# ROCKSOUL Future Roadmap — Research to Verified Delivery

This roadmap converts the strategic blueprint into staged, small work packages. It is intentionally not a claim that these capabilities exist today. Implementation must be decomposed into small issues with independent acceptance tests.

## Priority model

- **P0 — Trust & truth:** prevent false success, improve evidence integrity, make product claims precise.
- **P1 — Outcome intelligence:** verify completed work and learn from verified outcomes.
- **P2 — Agentic control:** govern multi-step workflows, tools, checkpoints, and repair.
- **P3 — Frontier readiness:** multimodal, persistent, distributed, increasingly autonomous systems.

## P0 — Trust & truth

- [x] Define canonical WorkItem contract schema: intent, acceptance criteria, risk, bounded budgets, deadline, exact permissions, and human-approval requirement. Implemented in `g4f/rocksoul_contracts.py`; persistence/API integration remains open.
- [x] Define WorkItem lifecycle and terminal outcomes: accepted, unverified, rejected, uncertain, blocked, cancelled, expired. `ACCEPTED` requires the `VERIFYING` state.
- [ ] Define a versioned verification-profile schema and bind each criterion to a registered verifier implementation.
- [ ] Add explicit provenance references to route, attempt, trace, and Arena evidence.
- [ ] Define capability passport schema with declared/observed/verified trust states and expiry.
- [ ] Add candidate-recall metrics before route ranking.
- [ ] Add route counterfactual explanation contract.
- [ ] Add structured uncertainty and abstention reasons.
- [ ] Document correlation risks in multi-model judging.
- [ ] Add evaluator version and evaluator identity to benchmark metadata.
- [ ] Add anti-slop acceptance criteria to product/API/console contracts.
- [ ] Add privacy, retention, redaction, and deletion policy for evidence data.

## P1 — Outcome intelligence

- [ ] Build a normalized outcome evidence record linked to request and trace IDs.
- [ ] Define task families and outcome labels with provenance.
- [ ] Implement deterministic verification adapters for JSON/schema outputs.
- [ ] Implement code verification adapter: tests, lint, type checks, build receipts.
- [ ] Implement factual research verifier: source-to-claim mapping and freshness metadata.
- [ ] Add verifier findings and severity to trace readback.
- [ ] Add accepted/unverified/rejected outcome states to API.
- [ ] Add outcome-focused metrics to Console.
- [ ] Add historical outcome query interface for routing.
- [ ] Prototype contextual retrieval router in shadow mode.
- [ ] Add cost/latency/quality cascade experiments.
- [ ] Add held-out evaluation and policy rollback gates.

## P2 — Agentic workflow control

- [ ] Define WorkGraph nodes, dependencies, and state transitions.
- [ ] Define step-level capability requirements and routing.
- [ ] Define scoped tool capability tokens and expiry.
- [ ] Add idempotency keys and postcondition checks for side-effecting tools.
- [ ] Add checkpoint format and safe-resume rules.
- [ ] Add cancellation propagation and deadline enforcement.
- [ ] Add bounded repair loops with changed-hypothesis requirement.
- [ ] Add isolated execution workspace contract.
- [ ] Add approval gates for irreversible/high-impact actions.
- [ ] Add artifact diff and evidence bundle generation.
- [ ] Add multi-agent role separation and independent review protocol.

## P3 — Frontier readiness

- [ ] Add provenance-aware memory schema with confidence, scope, expiry, and correction.
- [ ] Add memory retrieval evaluation and stale-memory invalidation.
- [ ] Add multimodal capability passports and task-specific evaluators.
- [ ] Add simulation/counterfactual planning interface.
- [ ] Add Mesh worker attestation and workload isolation research prototype.
- [ ] Add resource-aware scheduling across local and remote compute.
- [ ] Add long-running goal lifecycle with expiry, revocation, and human oversight.
- [ ] Add controlled experiment proposals from execution evidence.
- [ ] Add multi-agent collaboration evaluation with correlated-failure analysis.
- [ ] Publish an autonomy readiness report before enabling broader autonomy.

## Research hypotheses (not commitments)

1. **Verifier portfolio routing:** select not only the executor but also a verifier whose failure modes are sufficiently independent.
2. **Evidence debt:** track unsupported assumptions and missing proof as a measurable debt that blocks high-confidence completion.
3. **Capability half-life:** capability evidence decays with time, model revision, provider drift, and environment changes.
4. **Counterfactual route replay:** replay the same work contract against alternative policies to estimate regret without changing production behavior.
5. **Uncertainty budget:** allocate additional calls only when expected information gain justifies cost and risk.
6. **Cognitive diversity score:** measure whether candidate models/evaluators fail in correlated ways rather than counting model votes.
7. **Proof-carrying artifacts:** deliver outputs with machine-checkable receipts, provenance, test results, and known limitations.
8. **Self-healing with a brake:** permit bounded repair proposals, but require independent postcondition checks and explicit stop conditions.
9. **Memory with expiration:** memories have scope, provenance, confidence, and a reason to expire; retrieval is not equivalent to truth.
10. **Outcome economy:** compare systems by verified useful outcomes per unit of cost/time/risk, not token price alone.

## Release gates

A roadmap item cannot be marked complete because code exists. It needs:
- contract and threat-model notes;
- deterministic tests and negative tests;
- observability and audit evidence;
- budget/permission boundaries;
- documentation and operator instructions;
- regression and packaging checks;
- explicit known limitations;
- a final-main CI record.

## Current constraints

- Existing g4f provider implementations remain the runtime substrate.
- Existing F1–F7 foundations must remain backward compatible unless a migration is explicitly planned.
- Arena production quality certification remains `NOT_CERTIFIED` until dataset provenance, licensing, contamination, evaluator, variance, and environment gates are met.
- Adaptive routing, outcome verification engine, WorkGraph autonomy, and provenance-aware memory are future work until implemented and independently tested.
