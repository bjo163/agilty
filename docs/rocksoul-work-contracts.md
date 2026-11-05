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

The current allowlisted identifiers are `json_schema`, `artifact_digest`, `pytest`, `http_contract`, and `source_provenance`. The registry never dynamically imports or executes an adapter. The bounded built-in engine currently implements `artifact_digest` and a strict JSON Schema subset; the other identifiers remain declarations and return `ERROR` until an adapter is implemented.

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

## Executed verification and acceptance

Use `POST /api/v1/work-items/{work_id}/criteria/{criterion_id}/verify` or the CLI `rocksoul-work verify` while the WorkItem is in `VERIFYING`. The operator supplies the exact artifact bytes (base64 over API or a local file in CLI), a provenance reference, and the profile-specific input. The engine computes SHA-256 from the actual bytes and runs only a built-in deterministic adapter.

Implemented adapters:
- `source_provenance`: requires the supplied source reference to equal `sha256:<digest>` for the exact supplied bytes. This proves content-address binding only, not remote ownership or acquisition authenticity.
- `http_contract`: validates a supplied HTTPS response receipt, exact expected status, and response body against the bounded JSON Schema subset. It does not make a network request or authenticate the capture source.
- `pytest`: validates bounded JUnit XML receipts; failures produce FAIL, skipped cases produce INCONCLUSIVE, and DTD/entity declarations are rejected.
- `artifact_digest`: compares the computed SHA-256 with the operator's expected digest.
- `json_schema`: validates JSON against a bounded schema subset (types, enum, required fields, properties, additional-properties policy, item/length/numeric bounds).

Other allowlisted adapter IDs return `ERROR`; they do not silently pass. No dynamic import, arbitrary Python callable, or shell execution is permitted. Artifact input is capped at 1 MiB; JSON schema is capped at 64 KiB and 2,000 validation nodes.

The verifier result and evidence records are persisted immutably and linked into the WorkItem event hash chain. Acceptance no longer accepts caller-supplied PASS strings: every required criterion must have a latest persisted `PASS` from a matching registered profile, and the evidence chain must verify. A later FAIL/ERROR supersedes an earlier PASS for that criterion until a new PASS is recorded.

This proves the bytes supplied to the verifier matched the submitted artifact source/digest contract. It does not prove the source URI is truthful, establish external verifier identity through signatures, or independently inspect a remote artifact. Keep artifact acquisition and source authenticity in the trust boundary.

## API

All WorkItem and verification-profile endpoints require `X-ROCKSOUL-API-Key`:

- `GET /api/v1/verification-profiles`
- `POST /api/v1/verification-profiles`
- `GET /api/v1/verification-profiles/{profile_id}/{version}`
- `GET /api/v1/work-items`
- `POST /api/v1/work-items`
- `GET /api/v1/work-items/{work_id}`
- `POST /api/v1/work-items/{work_id}/transitions`
- `POST /api/v1/work-items/{work_id}/criteria/{criterion_id}/verify` (bounded base64 artifact input; requires a registered profile)
- `GET /api/v1/work-items/{work_id}/verify-chain`

Create requests contain the complete WorkItem JSON contract. Transition requests require `expected_status` and `target_status`; optional event payloads must be finite JSON objects. See `docs/rocksoul-api.md` for API startup and deployment.

## Operator CLI

```bash
rocksoul-work profile-register artifact-profile.json
rocksoul-work profile-list
rocksoul-work profile-get artifact.integrity 1
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
- Verifier result/evidence rows are cross-linked from lifecycle events by a canonical receipt digest; chain verification detects altered or missing receipt rows.
- SQLite `BEGIN IMMEDIATE` protects concurrent transitions.
- Event-chain verification detects changed, missing, reordered, or disconnected events.
- Hash chaining is tamper-evident, not a WORM store or external digital signature.
- Do not put API keys, provider secrets, credentials, or private tokens in goals, evidence sources, or event payloads.

## Explicit non-goals of this stage

WorkItem execution correlation is available through the optional `work_id` field on `POST /api/v1/execute`; it records the trace link but never auto-accepts the task. The verifier engine executes five bounded built-in adapters: artifact digest, JSON Schema, pytest JUnit receipt, captured HTTPS contract, and content-addressed source binding. The Console supports immutable profile registration and bounded artifact upload/verification. WorkGraph, checkpoint/resume, policy learning, independent remote artifact acquisition, external source authenticity, signed verifier identity, and cryptographically attributable human approval remain future work. Provider transport success remains separate from task acceptance.
