# ROCKSOUL F5 Arena — Production Benchmark Contract

The deterministic F5 Arena foundation is not enough to support production quality claims by itself. A production benchmark campaign must carry enough immutable evidence to reconstruct what was measured, against which exact target, under which environment, and how stable the result was across repeats.

## Authority boundary

`g4f/rocksoul_arena.py` remains the deterministic scoring and persistence foundation. `g4f/rocksoul_arena_production.py` adds production evidence on top of it without mutating F3 provider lifecycle state or F4 Mesh lifecycle state.

A campaign is not authoritative merely because it has a score. It must be backed by a registered production pack and exact target/environment evidence.

## Production pack evidence

Every production pack must provide:

- immutable pack name + version;
- immutable Arena suite digest;
- dataset source and dataset revision;
- SHA-256 dataset identity;
- explicit public/held-out split policy;
- contamination/leakage review statement;
- evaluator revision;
- repeat-run policy with a bounded variance threshold;
- explicit environment requirements;
- explicit network requirements.

The same `(pack name, pack version)` cannot be reused for different content. Changed content requires a version bump.

## Exact target identity

Every production campaign records all of:

- provider;
- model;
- model/provider revision;
- ROCKSOUL/runtime revision.

The target identity is content-addressed and persisted with the campaign. A human-friendly target label is not considered sufficient production evidence.

## Execution environment evidence

Every campaign records:

- runtime identity;
- operating system;
- Python/runtime version;
- network mode (`offline`, `restricted`, or `online`);
- region;
- optional additional environment evidence.

This evidence is stored with the campaign and copied into each constituent Arena run.

## Repeat-run variance

Production campaigns must run at least twice. The contract computes the population standard deviation across repeated Arena scores.

A campaign has `variance_accepted=true` only when its score standard deviation is within the pack's declared `max_score_stddev`. A high-variance campaign remains persisted as evidence but must not be presented as a stable production result.

## Persistence

Production evidence uses two additional SQLite tables:

- `arena_production_packs` — immutable production pack manifests;
- `arena_campaigns` — exact target/environment evidence, constituent run IDs, repeated scores, mean, standard deviation, and variance decision.

The underlying case results remain in the existing Arena tables.

## What this contract does not certify

This contract makes production benchmark evidence structurally enforceable. It does **not** magically create an authoritative live dataset or certify a live provider/model benchmark pack.

Before a real benchmark pack is promoted, the repository still needs an actual versioned dataset/source, its provenance and review record, explicit provider/model revisions, and real repeated execution evidence satisfying this contract.


## Operator workflow

Use the separate production evidence CLI for manifest validation and immutable pack registration. The CLI is offline-only; it never probes a provider or starts a campaign against a remote model.

- `validate-pack` checks the schema and the production contract. Without a dataset file it reports the manifest as structurally valid but not ready to register.
- `validate-pack --dataset-file PATH` streams the local artifact through SHA-256 and compares the exact digest with the manifest.
- `register-pack --dataset-file PATH` refuses to write any pack unless the artifact digest matches.
- `list-packs`, `list-campaigns`, and `show-campaign` return persisted evidence.
- `fixture-campaign` exercises the repeat-run store with an embedded synthetic fixture and an explicitly offline environment.

See [ROCKSOUL Arena production CLI](rocksoul-arena-production-cli.md) for the versioned JSON manifest schema and command contract. A registered manifest proves provenance metadata and artifact identity; it does not independently prove that the dataset's contamination review is correct or that a provider campaign was actually performed.
