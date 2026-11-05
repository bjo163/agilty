# ROCKSOUL Stage 3 — Production Evidence Integration

## Goal

Complete the missing operator and packaging path around the already recovered execution, Mesh, and Arena foundations. Stage 3 makes production benchmark metadata auditable and difficult to register incorrectly without performing unapproved live work.

## Implemented scope

1. Harden the production Arena validation boundary:
   - require a real Arena suite object and run the canonical suite validator;
   - validate provenance field types, exact target identity, observed environment shape, and finite JSON requirement objects;
   - reject booleans/floats where an integer repeat count is required;
   - reject non-finite and negative score-variance thresholds.
2. Add persisted readback:
   - list immutable production packs with their decoded manifest;
   - list campaigns, optionally filtered by pack digest;
   - retain exact target/environment/run/score evidence when reading a campaign.
3. Add the offline `rocksoul-arena-production` operator CLI:
   - versioned strict JSON manifest parser;
   - reject duplicate JSON keys, non-finite values, unknown or missing fields, and unsupported schema versions;
   - stream dataset artifacts in bounded 1 MiB chunks for SHA-256 verification;
   - require a matching local dataset file before registration;
   - expose status, validate, register, list, show, and synthetic fixture commands.
4. Add contract tests for correct hash, mismatched hash with no persisted write, strict schema, immutable registration/readback, and synthetic campaign persistence.
5. Register the console script in the current `setup.py` packaging authority.
6. Extend Arena CI and ROCKSOUL package CI to test module/CLI and built-wheel-installed entrypoints from outside the checkout.
7. Synchronize README, product backlog, production guide, release gate, and recovery manifest.

## Non-goals and safety boundary

- No live provider calls, external network probes, remote Mesh traffic, or production model campaign are executed.
- The built-in campaign is synthetic and explicitly marked offline; it is not benchmark evidence about a real model.
- Registering a manifest proves that its selected local artifact matches a declared SHA-256 and that its structure passes validation. It does not independently audit dataset licensing, contamination, or scientific quality.
- No GitHub release, version tag, PyPI publication, or production activation is created.
- No branch or pull request is created; the target is `main` only.

## Acceptance checklist

- [x] Production manifest contract and strict schema v1 are documented.
- [x] Hash calculation is streaming and memory-bounded.
- [x] Hash mismatch fails before pack registration.
- [x] Pack/campaign persisted readback exists.
- [x] Offline fixture covers register/run/persist/readback behavior.
- [x] No provider/network side effect is present in the operator CLI.
- [x] Source and package entrypoints are registered and CI-smoke-tested.
- [x] Updated Arena CI, ROCKSOUL CI, general Unittest, and wheel smoke pass on the exact Stage 3 implementation commit.
- [x] Live production packs explicitly remain deferred until a real artifact, audit, and authorized repeated campaign exist.

## Status

Stage 3 implementation is committed directly to `main` at `56d9bc11813572cca343f3b556b6042ebc214edd`. Stage 3 implementation commit `56d9bc11813572cca343f3b556b6042ebc214edd` passed Arena CI [#42030958020](https://github.com/bjo163/agilty/actions/runs/42030958020), ROCKSOUL CI plus package/wheel smoke [#42030958117](https://github.com/bjo163/agilty/actions/runs/42030958117), general Unittest on Python 3.10 and 3.15 [#42030958126](https://github.com/bjo163/agilty/actions/runs/42030958126), and CodeQL Advanced [#42030958006](https://github.com/bjo163/agilty/actions/runs/42030958006). The dedicated Mesh CI remained green from Stage 2 [#42026291726](https://github.com/bjo163/agilty/actions/runs/42026291726); Stage 3 changed no Mesh implementation, and the broad ROCKSOUL suite re-ran offline Mesh contracts across all four OS/Python lanes. The dedicated Mesh gate remained green from Stage 2; no Mesh implementation changed in Stage 3. The two skipped checks were distribution-publication gates, intentionally not invoked. No real provider probe, live campaign, PyPI upload, or release was run.
