# ROCKSOUL Work Contracts & Verification Profiles

## Purpose

A WorkItem defines one intended outcome, its acceptance criteria, risk, bounded budget, deadline, and exact capability permissions. It is not a provider request and it is not proof that the requested outcome was achieved.

The contract and lifecycle types live in `g4f/rocksoul_contracts.py`. Persistence lives in `g4f/rocksoul_work_store.py`. Versioned verification profile contracts live in `g4f/rocksoul_verification.py` and are persisted by `g4f/rocksoul_verification_store.py`.

## Lifecycle

Allowed path for a normal task:

```text
PENDING → PLANNING → READY → RUNNING → VERIFYING
                                           ├─ ACCEPTED
                                           ├─ REJECTED
                                           ├─ UNVERIFIED → VERIFYING
                                           ├─ UNCERTAIN → VERIFYING
                                           └─ BLOCKED → PENDING
```

Cancellation and expiry are bounded terminal outcomes. Terminal states cannot restart. Every transition requires the caller's expected current status; stale transitions fail rather than overwriting a newer state. `ACCEPTED` is only reachable from `VERIFYING`.

## Verification profile

A profile is an immutable versioned declaration containing:
- profile ID and integer version;
- allowlisted adapter identifier (declaration only);
- required evidence types and minimum counts;
- severity and independence group;
- deterministic and side-effect-free flags;
- bounded verifier timeout (50 ms–300 s).

The current allowlisted identifiers are `json_schema`, `artifact_digest`, `pytest`, `http_contract`, and `source_provenance`. The registry never dynamically imports or executes an adapter. Registration does not mean that adapter is implemented.

Example profile:

```json
{
  "schema_version": 1,
  "profile_id": "artifact.integrity",
  "version": 1,
  "adapter_id": "artifact_digest",
  "evidence_requirements": [
    {
      "evidence_type": "artifact_digest",
      "minimum_count": 1,
      "require_digest": true,
      "require_source": true
    }
  ],
  "severity": "error",
  "independence_group": "artifact_integrity",
  "deterministic": true,
  "side_effect_free": true,
  "timeout_seconds": 10
}
```

## Acceptance attestation

For every required criterion, the transition payload must contain a registered profile version, matching adapter/method identifier, `outcome: "pass"`, matching independence group, verifier identity/version, and evidence records. Each evidence record requires a unique ID, type, source, SHA-256 digest, timezone-aware capture timestamp, and matching verifier identity/version.

The store validates the profile and evidence metadata before accepting the lifecycle transition. This is currently a **trusted-caller attestation**, not independent verification: the API does not execute the adapter, fetch/re-hash the referenced artifact, or cryptographically authenticate the verifier. Do not treat this stage as machine-certified quality. Executable adapters and artifact-bound receipts are the next release gate.

## API

All WorkItem and verification-profile endpoints require `X-ROCKSOUL-API-Key`:

- `GET /api/v1/verification-profiles`
- `POST /api/v1/verification-profiles`
- `GET /api/v1/verification-profiles/{profile_id}/{version}`
- `GET /api/v1/work-items`
- `POST /api/v1/work-items`
- `GET /api/v1/work-items/{work_id}`
- `POST /api/v1/work-items/{work_id}/transitions`
- `GET /api/v1/work-items/{work_id}/verify-chain`

Create requests contain the complete WorkItem JSON contract. Transition requests require `expected_status` and `target_status`; optional event payloads must be finite JSON objects. See `docs/rocksoul-api.md` for API startup and deployment.

## Operator CLI

```bash
rocksoul-work create work-item.json
rocksoul-work list --limit 50
rocksoul-work get work-001
rocksoul-work transition work-001 pending planning
rocksoul-work verify-chain work-001

# Equivalent module invocation:
python -m g4f.rocksoul_work_cli --help
```

The CLI reads and writes the same ROCKSOUL SQLite database selected by the existing `RocksoulDB` path configuration. Transition commands always require explicit expected and target states.

## Persistence and integrity

- Contract JSON and SHA-256 digest are immutable for a given WorkItem ID.
- Repeating create with the same ID and digest is idempotent; reusing the ID with changed content fails.
- Lifecycle events are append-only at the application layer, ordered per WorkItem, and linked with SHA-256 previous-event hashes.
- SQLite `BEGIN IMMEDIATE` protects concurrent transitions.
- Event-chain verification detects changed, missing, reordered, or disconnected events.
- Hash chaining is tamper-evident, not a WORM store or external digital signature.
- Do not put API keys, provider secrets, credentials, or private tokens in goals, evidence sources, or event payloads.

## Explicit non-goals of this stage

No WorkItem-to-ExecutionEngine correlation, automatic verification adapter execution, WorkGraph, checkpoint/resume, policy learning, or Console workflow is claimed as shipped. Provider transport success remains separate from task acceptance.
