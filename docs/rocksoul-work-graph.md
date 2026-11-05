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

The current integration adds a read-only authoritative readiness resolver: every referenced WorkItem must exist and pass its own event/evidence-chain verification. Only an `accepted` dependency with a valid chain satisfies downstream dependencies. Missing or terminal-failed dependencies block descendants; pending dependencies leave descendants waiting; corrupt graph/WorkItem evidence fails closed. This resolver does not mutate WorkItems or dispatch work.

Authenticated API endpoints now support graph create/list/read and readiness readback. The offline `rocksoul-work-graph` CLI supports create/list/get/verify/readiness. These are control-plane inspection and registration surfaces, not a worker scheduler. The implementation still does not create child WorkItems, reserve aggregate budgets, dispatch execution, or propagate cancellation.

## Scheduling semantics

The pure `WorkGraph.ready_nodes(completed)` helper remains structural and trusts only the explicit caller-supplied node set; it must not be used as execution authorization. The store-level `resolve_readiness(graph_id, work_items)` is the authoritative read model: it queries each referenced WorkItem, verifies its event/evidence chain, and requires accepted status for every dependency. Readiness is a snapshot, not a reservation or lock; a future dispatcher must re-check state atomically immediately before a child transition or execution.

The initial graph model intentionally avoids implicit fan-out and dynamic graph mutation. A future schema revision may add typed edges (artifact, control, ordering), but must not overload a generic dependency with different semantics.

## Trust and safety invariants

1. A graph digest identifies canonical graph structure, not the truth or integrity of referenced WorkItems.
2. A completed node ID is caller-provided planning input, not an acceptance receipt.
3. No node inherits permissions, secrets, budgets, or approval from another node.
4. Cycles, missing dependencies, duplicate WorkItem references, and over-limit graphs fail closed.
5. Ordering within a parallel layer is stable by node ID for reproducibility; it does not imply execution order.
6. Graph execution must use per-WorkItem state transitions and acceptance gates. A parent graph must never mark children accepted by aggregation alone.
7. `required` is descriptive metadata only; graph completion/optional-node aggregation policy is not implemented.
8. Readiness is a read-only snapshot and does not reserve the child, budget, or dependency state. A future scheduler must close the check/use race with an atomic claim or expected-state transition.
9. A graph registry hash chain is tamper-evident within the database but is not WORM storage or an external signature.

## Next integration gates

- [x] persistent graph registry with immutable graph IDs, idempotent registration, bounded listing, and hash-chained creation events;
- [x] authenticated API create/list/read/readiness endpoints and offline CLI create/list/get/verify/readiness;
- [x] authoritative readiness calculation from actual WorkItem statuses and valid WorkItem event/evidence chains;
- graph-level budget reservation that cannot exceed child WorkItem budgets;
- cancellation, deadline propagation, and bounded retry semantics;
- failure/uncertain propagation and explicit optional-node policy;
- artifact handoff using content digests rather than mutable paths;
- Console graph visualization with blocked/ready/running/accepted states;
- integration tests proving no child can bypass its own approval and verification gates.

Until those gates pass, WorkGraph is **FOUNDATION**, not an execution orchestrator.
