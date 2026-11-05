# ROCKSOUL Stage 2 — Recovery Manifest

## Scope

This document records the selective recovery of ROCKSOUL onto the evolving `main` branch of `bjo163/agilty`.

- Source snapshot: `f4/mesh-core-doc`
- Source snapshot commit: `73cc04f371f690730ee3cb9d4e90ded5aba9cacc`
- Target branch: `main`
- Target parent before recovery: `6d49e0c5882f1ee17a6ee4cc515175843fd5e250`
- Strategy: restore selected blob objects; do not merge or reset the divergent branch.

## Restored inventory

- 14 ROCKSOUL Python modules under `g4f/rocksoul_*.py`.
- 12 deterministic/offline test modules under `tests/test_rocksoul_*.py`.
- 21 ROCKSOUL architecture, product, migration, backlog, governance, and release-gate documents.
- A default `.github/CODEOWNERS` file.
- Current-main compatible ROCKSOUL CI, Mesh CI, and Arena CI workflows.
- A manual-only live intelligence workflow requiring an explicit boolean opt-in.

## Integration choices

1. Existing g4f provider implementations and the current `g4f.client` API remain the runtime substrate.
2. `setup.py` remains the active packaging authority. ROCKSOUL console scripts are added there.
3. The old `pyproject.toml`/uv-build configuration is intentionally not restored because it changes the Python compatibility floor and packaging backend for the whole repository.
4. The historical release workflow is intentionally not restored. This recovery does not create tags, GitHub Releases, or PyPI publications.
5. The prior six-hour scheduled live-probe workflow is replaced with manual-only execution and explicit live-probe confirmation. Default CI remains offline.
6. The evolving `main` history is preserved. No force-push, branch reset, or broad branch merge is performed.

## Verification contract

The new workflows verify:
- the full offline ROCKSOUL contract suite on Ubuntu and Windows with Python 3.10 and 3.13;
- independent Mesh security/lifecycle/lease/CLI tests on Ubuntu and Windows;
- independent Arena scoring/provenance/persistence/CLI tests on Ubuntu and Windows;
- package wheel/sdist build and metadata validation through the current `setup.py` packaging configuration.

The Stage 2 recovery commit `5b818f839c33150a48818b8f352161fc3ecf7c94` is now current-main verified: ROCKSOUL CI (Ubuntu/Windows, Python 3.10/3.13 plus wheel/sdist build), Mesh CI, Arena CI, CodeQL Advanced, and general Unittest all completed successfully. Stage 3 adds the production-evidence CLI, strict dataset artifact verification, persisted evidence readback, and installed-wheel entrypoint verification.

Stage 3 implementation commit `56d9bc11813572cca343f3b556b6042ebc214edd` passed Arena CI [#42030958020](https://github.com/bjo163/agilty/actions/runs/42030958020), ROCKSOUL CI plus package/wheel smoke [#42030958117](https://github.com/bjo163/agilty/actions/runs/42030958117), general Unittest on Python 3.10 and 3.15 [#42030958126](https://github.com/bjo163/agilty/actions/runs/42030958126), and CodeQL Advanced [#42030958006](https://github.com/bjo163/agilty/actions/runs/42030958006). The dedicated Mesh CI remained green from Stage 2 [#42026291726](https://github.com/bjo163/agilty/actions/runs/42026291726); Stage 3 changed no Mesh implementation, and the broad ROCKSOUL suite re-ran offline Mesh contracts across all four OS/Python lanes. The final Stage 3 implementation outcome was 13 successful checks, 2 intentionally skipped publication checks, and zero failures or pending checks. Historical release records remain immutable; live provider campaigns and release publication stay separately gated.

## Stage 4 operator extension

- A dual-opt-in `run-campaign` command is added for one exact provider/model and one previously registered pack.
- The command requires environment opt-in plus CLI confirmation, reconfirms the pack digest, rehashes the exact local artifact, checks observed environment requirements, and enforces a request-count cap.
- Its tests use a fake g4f client/provider. No live provider campaign was executed and no production-quality claim is certified.

## Explicitly out of scope

- Rebranding or changing the repository/package identity.
- Replacing or migrating the current g4f provider system.
- Activating remote Mesh traffic or provisioning production node secrets.
- Running live provider probes or authoritative live Arena campaigns automatically.
- Publishing a new package or release.
- Rewriting the repository history or merging the divergent snapshot branch.


## Stage 3 additions

- `g4f/rocksoul_arena_production_cli.py` — offline-only production manifest validation, artifact verification, immutable pack registration, and campaign readback.
- `tests/test_rocksoul_arena_production_cli.py` — manifest, hash mismatch, registration, fixture campaign, and readback contracts.
- `docs/rocksoul-arena-production-cli.md` and `docs/rocksoul-stage-3.md` — Stage 3 operator schema and acceptance record.
- `docs/rocksoul-stage-4.md` — dual-opt-in campaign execution and preflight acceptance.
- Built-wheel entrypoint smoke checks prevent source-tree imports from masking packaging errors.
