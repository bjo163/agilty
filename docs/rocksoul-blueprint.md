# ROCKSOUL — Strategic Blueprint

> **From model routing to verified intelligence operations.**

## 1. Executive direction

ROCKSOUL evolves from its current routing/execution foundation into an **Evidence-Driven Intelligence & Execution Control Plane**.

The product is not a model marketplace and not another agent framework. It is the control layer that governs how heterogeneous intelligence resources are selected, composed, executed, verified, observed, and improved.

The core unit is not a completion. It is a **work item with intent, constraints, evidence, and an outcome contract**.

### North-star metric

**Verified Useful Outcome Rate (VUOR)**: the proportion of eligible work items that satisfy their declared acceptance criteria, with evidence, within configured cost, time, and risk budgets.

VUOR must be segmented by task class and verifier confidence. It must never be presented as a universal intelligence score.

Supporting measures:
- verified outcome rate by task family;
- cost and latency per verified outcome;
- rework and regression rate;
- unsupported-claim rate;
- abstention precision and unnecessary-abstention rate;
- recovery success rate;
- policy improvement validated on held-out workloads;
- safety/policy violations and near misses.

## 2. Strategic design principles

1. **Outcome over tokens** — optimize completed work, not generated volume.
2. **Evidence over confidence** — model confidence is metadata, not proof.
3. **Capability over brand** — route to verified task capabilities, not model hype.
4. **Diversity over redundant consensus** — correlated models do not create independent evidence.
5. **Bounded autonomy** — every action has a budget, permission, deadline, and stop condition.
6. **Reversible learning** — learned policies are proposed, evaluated, versioned, and rolled back.
7. **Fail closed, degrade gracefully** — unsafe or unverified paths are excluded; safe alternatives remain.
8. **Runtime neutrality** — reuse g4f and other adapters; do not fork provider behavior.
9. **Human authority** — approval gates remain for irreversible, high-impact, or ambiguous actions.
10. **Honest product claims** — distinguish shipped, experimental, planned, and research-only capabilities.

## 3. The architecture: an intelligence operating loop

```text
USER INTENT
   │
   ▼
INTENT CONTRACT ── goal, constraints, acceptance criteria, authority
   │
   ▼
WORK GRAPH ─────── tasks, dependencies, risk, checkpoints
   │
   ▼
CAPABILITY PLANNER ── model/tool/agent/node capability passports
   │
   ▼
POLICY & ROUTER ── quality, evidence, cost, latency, risk, diversity
   │
   ▼
BOUNDED EXECUTION ── runtime adapters, tools, sandbox, Mesh leases
   │
   ▼
EVIDENCE LEDGER ── inputs, versions, decisions, actions, outputs, provenance
   │
   ▼
VERIFY & RED-TEAM ── deterministic checks + independent evaluators
   │
   ├── PASS → ACCEPTED OUTCOME → DELIVERY
   ├── REPAIR → bounded repair plan → re-execute
   ├── UNCERTAIN → seek evidence / alternate verifier / human review
   └── FAIL → isolate, explain, recover, or stop
                    │
                    ▼
             LEARNING LAB
      offline analysis → candidate policy
      replay → held-out evaluation → approval
      staged rollout → monitor → rollback
```

This is a target architecture. Existing components map into parts of this loop; the complete loop is not yet implemented.

## 4. Core planes and responsibilities

### A. Intent & Work Contract
Normalize a request into a durable contract:
- objective and expected deliverable;
- acceptance criteria and verification method;
- allowed tools/data and permission scope;
- budget, deadline, retry and escalation limits;
- sensitivity and risk classification;
- explicit unknowns and assumptions.

Never silently invent missing acceptance criteria for consequential work. Low-risk tasks may use transparent defaults.

### B. Capability Intelligence
Maintain versioned capability passports for models, tools, agents, and Mesh nodes:
- supported task families and modalities;
- context/window and structured-output constraints;
- tool-use and computer-use abilities;
- known failure modes;
- verified benchmark evidence and its age;
- latency/cost distributions;
- policy and data handling constraints;
- runtime/model revision and provenance.

Separate **declared**, **observed**, and **verified** capabilities. Expire stale evidence and re-verify after material version changes.

### C. Routing & Composition
Move beyond one-shot model choice:
- candidate recall before ranking;
- hard eligibility filters before soft scoring;
- task-specific quality/cost/latency/risk trade-offs;
- historical contextual retrieval;
- model/tool diversity where independent evidence matters;
- cascade and escalation strategies;
- step-level routing across a work graph;
- explicit route explanations and counterfactuals.

Do not let a single opaque score override hard policy constraints.

### D. Execution & Autonomy Guard
Every execution receives:
- a scoped identity and correlation ID;
- finite wall-clock, token, request, and monetary budgets;
- permission-scoped tool capabilities;
- idempotency and replay rules;
- checkpoint and cancellation semantics;
- sandbox/resource limits where code or untrusted input is involved;
- explicit side-effect classification;
- safe recovery and compensation strategy.

Treat read-only, reversible, and irreversible actions differently. Human approval is required where policy says the action is consequential.

### E. Evidence Ledger & Provenance Graph
Capture append-only, tamper-evident evidence for:
- intent and acceptance criteria;
- route candidates, rejected candidates, and policy revision;
- model/tool/provider versions;
- prompts and input references under retention policy;
- execution attempts, tool actions, outputs and artifact digests;
- verifier identity, checks, findings and confidence;
- human approvals, overrides, and final outcome.

Use content hashes and linked event identities to detect mutation. Keep secrets out of logs. Support privacy-aware redaction, retention, and deletion policies; append-only must not become an excuse to retain personal data forever.

### F. Verification & Anti-Slop Engine
Verification is task-specific and layered:
1. deterministic validators (schema, types, tests, constraints);
2. source/evidence checks (citations, provenance, freshness);
3. semantic evaluators (rubrics, entailment, completeness);
4. independent adversarial review;
5. artifact-level checks (build, run, diff, integration);
6. human acceptance for high-impact or subjective outcomes.

Use diverse evaluators and track judge agreement and known blind spots. A model judging its own output is not an independent verifier. Consensus is not proof.

### G. Recovery & Resilience
Classify failures and choose a bounded response:
- retry only for retryable faults and with a changed hypothesis;
- route around unhealthy resources;
- repair artifacts in isolated workspaces;
- checkpoint and resume only when state is safe;
- compensate reversible side effects;
- quarantine failing models/tools/nodes;
- stop and explain when uncertainty or risk exceeds policy.

### H. Learning & Policy Evolution
Turn verified outcomes into training/evaluation evidence:
- store outcome labels and context features;
- detect drift and provider regressions;
- evaluate contextual retrieval and bandit candidates offline;
- run shadow/canary policies;
- require held-out evaluation and rollback criteria;
- keep policy versions immutable and attributable.

No online self-modification of production policy without an explicit promotion gate.

### I. Mesh & Resource Fabric
Coordinate local and remote workers as untrusted, capability-bearing resources:
- authenticated node identity;
- workload isolation and leases;
- attested runtime/environment where feasible;
- capability and capacity matching;
- data locality and privacy constraints;
- node health and failure isolation;
- auditable scheduling and revocation.

A Mesh node is not trusted merely because it is online.

### J. Operator Console
Provide an operational cockpit for:
- current health and verified capability inventory;
- route decisions and counterfactual explanations;
- traces, evidence, and outcome status;
- budgets, policy versions, approvals, and incidents;
- Arena comparisons and drift;
- controlled rollout, quarantine, and rollback.

## 5. Anti-slop: quality contract

Every work item should declare a verification profile. Examples:

| Task class | Minimum verification |
|---|---|
| Factual research | source provenance, claim-to-source mapping, freshness, contradiction scan |
| Code change | diff review, tests, lint/type checks, build or explicit limitation |
| Data transformation | schema validation, row/count invariants, sample checks, reproducibility |
| Planning | constraint coverage, dependency checks, assumptions and uncertainty |
| Tool/action workflow | permission check, action receipt, postcondition verification |
| Creative work | user brief coverage, originality/constraint review; no false factual certification |

Quality dimensions should remain separate rather than collapsed prematurely:
- correctness;
- completeness;
- evidence quality;
- instruction adherence;
- usefulness;
- originality where relevant;
- safety;
- robustness;
- cost and latency.

A result may be useful but unverified; verified on a narrow scope but not generalizable; or correct but unsafe to execute. The system must preserve these distinctions.

### Anti-gaming requirements
- hidden/held-out test cases where appropriate;
- evaluator versioning and evaluator disagreement reporting;
- contamination and benchmark leakage review;
- adversarial and metamorphic tests;
- output length and confidence are never quality proxies;
- repeated identical retries do not count as new evidence;
- benchmark success does not imply general intelligence;
- no single judge model can certify itself.

## 6. AGI-ready direction without AGI theater

ROCKSOUL should prepare for increasingly general systems through stable interfaces and governance, not by claiming AGI.

Future capabilities to support:
- persistent goals with explicit expiry and revocation;
- hierarchical planning and dynamic work graphs;
- multimodal perception and action;
- tool discovery and capability negotiation;
- long-running tasks with checkpoints and recovery;
- multi-agent collaboration with role separation;
- memory with provenance, confidence, decay, and correction;
- self-evaluation and experiment proposals;
- simulation and counterfactual planning;
- resource-aware scheduling across local and remote compute.

Critical boundary: these are architectural research directions. They require measurable tests, permission controls, sandboxing, and human governance before deployment.

## 7. Data and learning flywheel

```text
Work contract
  → execution trace
  → verifier findings
  → accepted/rejected outcome
  → normalized feedback
  → offline policy experiment
  → held-out Arena evaluation
  → staged rollout
  → monitored production evidence
```

The flywheel must not learn from unverified outputs as if they were ground truth. Feedback quality, label provenance, and selection bias must be recorded.

## 8. Relationship to current implementation

| Domain | Current evidence | Strategic evolution |
|---|---|---|
| Runtime substrate | Existing g4f provider/runtime layer | Keep provider execution adapters reusable |
| Routing | Explainable, capability-aware route foundation | Candidate recall, contextual and step-level routing |
| Execution | Bounded attempts/time, retry taxonomy, traces; canonical WorkItem schema, SQLite persistence, append-only lifecycle events, API and operator CLI | WorkItem-to-ExecutionEngine correlation, checkpoints, scoped action capabilities |
| Health/recovery | Provider lifecycle and quarantine/recovery | Drift detection and verified capability expiry |
| Mesh | Authenticated nodes, leases, isolation | Attestation, sandbox scheduling, data locality |
| Arena | Deterministic foundation and campaign integrity verifier | Provenance-rich suites, adversarial tests, held-out evaluations |
| API | Authenticated WorkItem lifecycle, verifier registry/execution, signed approval gate, evidence diff and metadata bundle endpoints | Signed external verifier identity, remote artifact acquisition, policy lifecycle APIs |
| Console | WorkItem cockpit, immutable profile registration, bounded artifact upload/verification, signed admin approval, evidence diff and metadata-only bundle export | Per-person SSO, separation-of-duties approval, rich artifact payload diff, policy lab |
| Verification | Five bounded deterministic adapters with persisted evidence receipts | Independent artifact acquisition, signed external evidence/verifier identity, independent evaluators |
| Learning | Evidence exists; adaptive policy is not yet certified | Offline learning, shadow tests, controlled promotion |

Do not represent planned capabilities as shipped. Current Arena reports remain `quality_certification=NOT_CERTIFIED` until production dataset and methodology gates are satisfied.


### Implemented trust foundation and hard boundary

The current Work Contract slice persists immutable WorkItem contract digests, hash-chained lifecycle events, immutable versioned verification profiles, verifier execution/evidence receipts, approval decisions, and native execution trace correlation in SQLite. State changes use atomic expected-status transitions. The authenticated API and `rocksoul-work` CLI expose contract management, profile registration, bounded artifact verification, execution trace linkage, and event-chain readback. The Console provides WorkItem creation/readback, lifecycle controls, profile registration, bounded artifact upload, browser-side SHA-256, per-criterion verifier execution, signed administrator approve/reject controls, evidence diff, and metadata-only JSON bundle export.

The built-in verifier executes five deterministic adapters against exact caller-supplied bytes: `artifact_digest`, bounded `json_schema`, pytest JUnit XML receipts, captured HTTPS contract receipts, and content-addressed source binding. Acceptance is possible only from `VERIFYING`, after the latest persisted verifier result for every required criterion is PASS and the receipt/event chain validates. Caller-supplied PASS strings are rejected. Optional WorkItem execution linkage requires exact `model.execute` permission, respects available deadline/approval gates, caps wall-time/attempt budgets, records provider transport outcome separately, and never auto-accepts the task.

Hard boundary: verifier receipts are locally generated from caller-supplied bytes; they do not prove that a source URI is truthful, independently acquire a remote artifact, or authenticate a remote verifier identity. High/critical WorkItems require a Console-server HMAC approval bound to the immutable contract digest, configured administrator principal, decision, timestamp, and one-time nonce. The API enforces signature freshness/replay protection, persists approval events in the hash chain, and blocks `RUNNING`/execution until the latest decision is approved. This is attribution to a configured administrator credential/principal, not proof of a natural person's identity or legal non-repudiation; per-person SSO and separation-of-duties remain open. Evidence bundles export metadata and receipts, not original artifact bytes. Arena production quality certification remains `NOT_CERTIFIED`.

## 9. Delivery strategy

### Horizon 0 — Trustworthy foundation
Protect existing functionality. Consolidate contracts, docs, observability semantics, and capability evidence. No broad rewrite.

### Horizon 1 — Outcome verification
Introduce work-item contracts and a minimal verification profile system. Start with deterministic task classes: code checks, structured data, API contracts, and factual source mapping.

### Horizon 2 — Evidence-driven adaptive routing
Add historical outcome store, candidate recall metrics, contextual retrieval, cost/quality cascades, and route counterfactuals. Begin in shadow mode.

### Horizon 3 — Agentic workflow control
Add work graphs, step-level routing, checkpointing, scoped tool capabilities, sandbox execution, and verified repair loops.

### Horizon 4 — Controlled autonomy & Mesh
Add long-running tasks, node attestation, policy-governed delegation, privacy-aware memory, and multi-agent collaboration.

### Horizon 5 — General intelligence operations
Support multimodal, persistent, self-improving workflows only when independent evaluations demonstrate reliability, safety, and useful generalization.

## 10. Explicit non-goals

- Training a foundation model as the primary product.
- Reimplementing every provider or agent framework.
- Maximizing model/provider count as the primary differentiator.
- Unbounded autonomous shell, browser, or account access.
- Self-modifying production policies without promotion controls.
- Treating a leaderboard or model consensus as truth.
- Claiming AGI, consciousness, or general competence from narrow benchmarks.

## 11. Decision filter for every future feature

A proposed feature is accepted only if it answers:
1. Which user outcome does it improve?
2. Which evidence proves the improvement?
3. What new failure or attack surface does it create?
4. What is the budget and stop condition?
5. How is it observed and reproduced?
6. How is it disabled or rolled back?
7. Does it duplicate an existing runtime/framework responsibility?
8. Is it implemented, experimental, or merely a research hypothesis?

If these questions cannot be answered, keep the idea in research notes rather than production scope.
