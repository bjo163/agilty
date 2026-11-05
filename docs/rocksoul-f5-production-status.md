# ROCKSOUL F5 Production Benchmark Status

This file tracks the production-benchmark transition without overstating live-provider certification.

## Contract layer

- `ArenaProductionPack` — immutable pack identity and manifest.
- `ArenaDatasetProvenance` — source, revision, SHA-256, split policy, contamination review.
- `ArenaRepeatPolicy` — bounded repeated runs and maximum accepted score standard deviation.
- `ArenaTargetIdentity` — exact provider, model, revision, and runtime revision.
- `ArenaEnvironmentEvidence` — runtime, OS, Python version, network mode, region, and extra evidence.
- `ArenaProductionStore` — persistent production-pack and campaign evidence linked to underlying Arena runs.

## Verification status

The structural production-evidence contract is `CERTIFIED` for merge. PR #20 candidate `c778e811cdf44c3400262e4736555df386e6b869` passed `ROCKSOUL Arena CI`, `ROCKSOUL CI`, and general `Unittest`.

This certification covers the evidence contract, persistence model, deterministic tests, cross-platform Arena CI, and regression compatibility. It does not certify a specific live benchmark pack.

## Stage 4 operator capability

The local `run-campaign` command can execute an already registered pack against one exact provider/model after dual opt-in, digest confirmation, dataset re-hash, Python/OS/network-mode preflight, and provider-request budgeting. It persists declared provider/model/runtime revisions and environment metadata. CI verifies the route using a fake provider only; no real campaign is part of certification.

The network mode and provider/model/runtime revision strings are operator-supplied attestations, not independently verified measurements. The command's presence does not certify a real dataset or model result.

## Stage 5 evidence audit/report capability

The `verify-campaign` command reconciles campaign data with the immutable pack and canonical suite records, including every repeat run, case result, score aggregate, target, environment, and variance decision. The `campaign-report` command aggregates by exact target digest, emits a deterministic report digest, and surfaces integrity rejection. Both paths are offline and are covered by synthetic regression tests.

This verifies persistence integrity; it does not independently audit source licensing or contamination, and it never sets model quality to certified.

## Live activation status

Live production benchmark packs remain `DEFERRED` until a real dataset and real campaign satisfy every live activation item in `docs/rocksoul-arena-release-gate.md`.
