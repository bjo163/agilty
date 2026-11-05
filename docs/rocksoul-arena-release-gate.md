# ROCKSOUL F5 Arena Release Gate

F5 Arena is certified independently from the execution and Mesh control planes. The existence of legacy benchmark helpers or an offline fixture does not make a real provider/model benchmark pack production-authoritative.

## Mandatory architecture gate

- [x] Canonical implementation is separate from `rocksoul_platform.Arena`.
- [x] F5 cannot mutate F3 provider lifecycle or F4 Mesh lifecycle.
- [x] Suite identity is content-addressed with SHA-256.
- [x] Suite name/version is immutable once registered.
- [x] Result evidence is persisted in the ROCKSOUL SQLite control plane.

## Mandatory methodology gate

- [x] Deterministic case ordering.
- [x] Explicit positive bounded weights.
- [x] Deterministic correctness scoring.
- [x] Execution errors remain visible as zero-score evidence.
- [x] Latency is evidence-only in the default score.
- [x] Leaderboard uses the latest run per target rather than historical best-run selection.
- [x] Offline repository fixture has explicit provenance and no network dependency.

## Mandatory foundation verification gate

- [x] `ROCKSOUL Arena CI` passes on Ubuntu / Python 3.13.
- [x] `ROCKSOUL Arena CI` passes on Windows / Python 3.13.
- [x] Arena core unit tests pass.
- [x] Arena CLI contract tests pass.
- [x] `rocksoul-arena` smoke fixture passes.
- [x] package wheel + source distribution build succeeds.
- [x] existing `ROCKSOUL CI` remains green on the final candidate.
- [x] existing `ROCKSOUL Mesh CI` remains green on the final candidate.
- [x] general repository `Unittest` remains green on the final candidate.

### Foundation certification evidence

- PR #17 exact head: `10d16d58b6257396acd7dad00d614f3ac31e46a3`.
- Exact PR head passed `ROCKSOUL Arena CI`, `ROCKSOUL Mesh CI`, `ROCKSOUL CI`, and general `Unittest` before merge.
- Merge commit on `main`: `d3123a9ff8d00828d0043cd0bb3937cbc16dab8a`.
- Post-merge `main` passed `ROCKSOUL Arena CI`, `ROCKSOUL Mesh CI`, `ROCKSOUL CI`, and general `Unittest` again.

## Production evidence-contract gate
The versioned manifest parser rejects duplicate keys at all depths, non-finite values, unknown fields, and unsupported schema versions before any pack is registered.


`g4f/rocksoul_arena_production.py` makes the evidence needed for a production benchmark structurally enforceable. A production pack/campaign must provide:

- [x] versioned dataset source and revision;
- [x] SHA-256 dataset identity;
- [x] evaluator revision;
- [x] explicit public/held-out split policy;
- [x] contamination/leakage review statement;
- [x] bounded repeat-run policy and score-variance threshold;
- [x] explicit environment requirements;
- [x] explicit network requirements;
- [x] exact provider/model/revision/runtime identity;
- [x] persisted campaign evidence linking repeated Arena run IDs, scores, mean, standard deviation, and variance decision.

The same production pack `(name, version)` is immutable. Changed evidence requires a version bump. A high-variance campaign remains persisted but is not accepted as stable production evidence.

## Live production benchmark-pack activation gate

The contract being implemented does **not** by itself certify a live provider/model benchmark pack. Before any live benchmark is advertised as authoritative, all of the following must be satisfied with real evidence:

- [ ] actual benchmark dataset/source selected and versioned;
- [ ] dataset digest verified from the exact evaluation artifact;
- [ ] split policy applied to the real dataset where applicable;
- [ ] contamination/leakage review completed for that dataset and evaluator;
- [ ] exact live provider/model/revision/runtime identity captured;
- [ ] environment and network evidence captured from the real execution environment;
- [ ] repeated live campaign completed with variance inside the declared threshold;
- [ ] final production-pack candidate passes Arena CI, ROCKSOUL CI, Mesh CI, general Unittest, and package build.

## Release decision

The **F5 Arena deterministic foundation and offline production-evidence operator integration are GREEN** on Stage 3 implementation commit `56d9bc11813572cca343f3b556b6042ebc214edd`. Manifest validation, exact artifact hash registration, persisted evidence readback, duplicate-key/non-finite JSON rejection, and installed-wheel command paths passed current-main gates. This does not certify real provider/model quality; live benchmark-pack activation remains deferred until real data, independent review, exact target revision, and repeated authorized campaign evidence exist.

No broad live-provider/model quality claim is certified until the live activation gate is fully satisfied. A production-contract implementation may merge to `main` without creating a new production release or changing the published live benchmark scope.

## Current-main recovery verification status

The checked boxes and commit/workflow references above are historical evidence for the original release candidate. ROCKSOUL has since been selectively recovered onto the evolving g4f `main` branch. They do not, by themselves, certify the recovered modules against the current runtime revision.

The Stage 2 recovery commit `5b818f839c33150a48818b8f352161fc3ecf7c94` passed dedicated Mesh CI [#42026291726](https://github.com/bjo163/agilty/actions/runs/42026291726). Stage 3 implementation commit `56d9bc11813572cca343f3b556b6042ebc214edd` passed Arena CI [#42030958020](https://github.com/bjo163/agilty/actions/runs/42030958020), ROCKSOUL CI plus package/wheel smoke [#42030958117](https://github.com/bjo163/agilty/actions/runs/42030958117), general Unittest on Python 3.10 and 3.15 [#42030958126](https://github.com/bjo163/agilty/actions/runs/42030958126), and CodeQL Advanced [#42030958006](https://github.com/bjo163/agilty/actions/runs/42030958006). The dedicated Mesh CI remained green from Stage 2 [#42026291726](https://github.com/bjo163/agilty/actions/runs/42026291726); Stage 3 changed no Mesh implementation, and the broad ROCKSOUL suite re-ran offline Mesh contracts across all four OS/Python lanes. No live provider campaign or production release was run.

Keep live remote Mesh activation and authoritative live Arena claims disabled until their separate deployment/evidence gates are satisfied.
