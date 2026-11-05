# ROCKSOUL Stage 5 — Campaign Evidence Audit & Certification Reporting

## Goal

Make persisted production campaign evidence independently inspectable after Stage 4 execution. Stage 5 verifies that campaign rows, the immutable production pack, the canonical Arena suite, constituent Arena runs, case results, and calculated statistics still agree. It adds deterministic reports without making model-quality claims.

## Implemented scope

1. Add `ArenaProductionStore.verify_campaign(campaign_id)`.
2. Verify the production-pack manifest digest and its registered suite digest.
3. Load the canonical immutable suite manifest from `arena_suites` and verify its own digest, name, version, evaluator, and case list against the production pack.
4. Reconcile campaign target identity digest and typed environment evidence.
5. Verify declared repeat count, unique run IDs, ordered repeat index, pack digest/name/version, dataset provenance, evaluator revision, target identity, and environment metadata in each run.
6. Verify run suite/target string, case IDs, positive case weights, output digests, finite scores/latencies, pass/fail counts, and weighted score aggregates.
7. Verify run timestamps are contained within the campaign window.
8. Recompute campaign score list, mean, population standard deviation, and variance acceptance from stored Arena runs.
9. Add `verify-campaign` CLI with stable exit codes: 0 verified, 3 missing, 4 rejected.
10. Add `campaign-report --pack-digest` with optional target filter, bounded pagination, per-target aggregation, and deterministic report digest.
11. Ensure reports always state `quality_certification=NOT_CERTIFIED`.
12. Add offline tests for valid evidence, tampered run metadata/score/weights, missing run, unknown records, report filtering, deterministic digest, and CLI exit codes.

## Integrity outcomes

- `VERIFIED`: all stored campaign/pack/suite/run evidence reconciles.
- `REJECTED`: at least one required record is missing, malformed, tampered, or inconsistent.
- `NO_PACK` / `NO_EVIDENCE`: no registered pack or no campaign was found for the query.

The auditor is read-only. It never edits or repairs historical evidence. A rejected campaign remains visible for investigation.

## Claim boundary

- Integrity verification proves internal record consistency, not that operator-supplied revisions/network metadata are true.
- A stable score across repeats does not prove statistical significance or general model quality.
- A valid contamination-review field is metadata, not an independent contamination audit.
- Reports group by exact target digest and must not rank unlike providers/models as though they were one target.
- Every report leaves `quality_certification=NOT_CERTIFIED` until the separate real-dataset, licensing, evaluator, contamination, and production release gates are independently satisfied.
- No live provider is invoked by audit/report commands or their CI tests.

## Acceptance checklist

- [x] Pack manifest and canonical suite digests verified.
- [x] Target and environment evidence verified.
- [x] Repeat index, run IDs, run metadata, and timestamps verified.
- [x] Case list, weights, outputs, scores, pass counts, and weighted totals verified.
- [x] Campaign score list/mean/standard deviation/variance decision recomputed.
- [x] Tampered and missing evidence fails closed.
- [x] Reports keep target populations separate and have deterministic digests.
- [x] Report status and CLI exit codes are stable.
- [x] Quality certification is never inferred from internal integrity alone.
- [x] Default tests remain offline.

## Remaining separate production certification requirements

A real benchmark pack still needs an authentic versioned dataset, license/use review, independent contamination/leakage review, evaluator review, exact live target revisions, actual execution-environment evidence, repeated authorized campaigns, and final CI/release-gate review. Stage 5 does not bypass these requirements.
