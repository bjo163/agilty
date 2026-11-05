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
- [ ] Updated Arena CI, ROCKSOUL CI, general Unittest, and wheel smoke pass on the exact final Stage 3 main commit.
- [ ] Live production packs remain deferred until a real artifact, audit and authorized repeated campaign exist.

## Status

Implementation is committed only after the Stage 3 changes land on `main`. The final certification state must be updated from `VERIFYING` to `DONE` only after the exact final commit passes the listed current-main CI gates.
