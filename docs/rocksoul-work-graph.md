# ROCKSOUL WorkGraph — Deterministic Composition Contract

## Purpose

WorkGraph is the bounded DAG layer for composing multiple existing WorkItems into one coordinated outcome. A graph describes dependencies; it does not replace WorkItem contracts, create implicit permissions, schedule workers, or certify outputs.

The WorkItem remains the authority boundary:
- each node points to exactly one existing WorkItem ID;
- each WorkItem appears at most once in a graph;
- each node has explicit dependency node IDs;
- dependency completion is a scheduling prerequisite, never proof that the upstream artifact is correct;
- every node still needs its own execution permissions, budget, approval, and verifier receipts.

## Implemented foundation

`g4f/rocksoul_work_graph.py` currently provides:
- strict version-1 graph and node contracts;
- stable identifier validation and unknown-field rejection;
- unique node IDs and unique WorkItem references;
- dependency existence and self-dependency checks;
- cycle detection with deterministic Kahn topological layering;
- deterministic ready-node selection from an explicit completed-node set;
- transitive descendant lookup;
- canonical serialization and SHA-256 graph digest;
- hard limits: 256 nodes, 2,048 edges, 64 dependencies per node, and 64 topological layers.

The graph contract is persisted by `g4f/rocksoul_work_graph_store.py` in the existing SQLite control-plane database. Registration is idempotent for the same immutable graph digest and rejects reuse of a graph ID with changed content. Graph creation is recorded in a hash-chained event table; the verifier checks canonical graph integrity, sequence continuity, previous hashes, event hashes, and the creation event. Listing is bounded to 100 records per page.

The implementation still does not create WorkItems, inspect WorkItem status, reserve budgets, dispatch execution, or propagate cancellation. Persistence makes graph definitions durable; it does not make them executable. Do not describe those capabilities as shipped.

## Scheduling semantics

A node is structurally ready only when every dependency ID is in the caller-supplied completed set. This method deliberately does not query the WorkItem store. The future scheduler must resolve each dependency against authoritative WorkItem state and require an accepted upstream outcome when the edge is declared as outcome-dependent.

The initial graph model intentionally avoids implicit fan-out and dynamic graph mutation. A future schema revision may add typed edges (artifact, control, ordering), but must not overload a generic dependency with different semantics.

## Trust and safety invariants

1. A graph digest identifies canonical graph structure, not the truth or integrity of referenced WorkItems.
2. A completed node ID is caller-provided planning input, not an acceptance receipt.
3. No node inherits permissions, secrets, budgets, or approval from another node.
4. Cycles, missing dependencies, duplicate WorkItem references, and over-limit graphs fail closed.
5. Ordering within a parallel layer is stable by node ID for reproducibility; it does not imply execution order.
6. Graph execution must use per-WorkItem state transitions and acceptance gates. A parent graph must never mark children accepted by aggregation alone.
7. Required/optional node semantics are descriptive only in this foundation; aggregation policy is not yet implemented.

## Next integration gates

- [x] persistent graph registry with immutable graph IDs, idempotent registration, bounded listing, and hash-chained creation events;
- API/CLI read and write endpoints with idempotent create and expected-version updates;
- authoritative readiness calculation from WorkItem statuses and dependency outputs;
- graph-level budget reservation that cannot exceed child WorkItem budgets;
- cancellation, deadline propagation, and bounded retry semantics;
- failure/uncertain propagation and explicit optional-node policy;
- artifact handoff using content digests rather than mutable paths;
- Console graph visualization with blocked/ready/running/accepted states;
- integration tests proving no child can bypass its own approval and verification gates.

Until those gates pass, WorkGraph is **FOUNDATION**, not an execution orchestrator.
