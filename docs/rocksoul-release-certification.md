# ROCKSOUL Release Certification

## Release scope

This certification covers the F0–F4 product foundation, F6 product CLI, F7 deterministic verification matrix, and F8 product documentation for ROCKSOUL v0.2.0. F5 Arena remains deliberately outside this release and requires its own benchmark/reproducibility/provenance/security release gate before production activation.

## Certified gates

- **F0 guardrails:** unique request identity, explicit compatibility boundary, hermetic default tests, and no provider implementation duplication.
- **F1 execution:** normalized request, deterministic candidate ordering, bounded provider fallback through the existing client, per-attempt timeout, and whole-request budget enforcement including in-flight calls.
- **F2 trace:** execution runs and provider attempts are persisted; terminal execution outcomes become health evidence; streaming evidence is not double-counted.
- **F3 reliability:** deterministic error taxonomy, bounded global and per-provider attempts, explicit rate-limit cooldown, quarantine, recovery probing, probing isolation, re-admission, canonical route explanation, and safe streaming lifecycle behavior.
- **F4 Mesh:** authenticated node identity, timestamp/nonce replay defense, secure endpoint policy, explicit node lifecycle, deterministic capability/capacity selection, bounded idempotent leases, per-node failure isolation, persistent audit events, and a separate `rocksoul-mesh` operator surface.
- **F6 CLI:** JSON-oriented execution-control commands preserve routing/capability constraints; F4 adds its own JSON-oriented Mesh operator CLI rather than overloading provider commands.
- **F7 tests:** offline tests cover the execution baseline plus Mesh authentication, lifecycle, routing, leases, failure isolation, observability, and CLI contracts on required CI gates.
- **F8 productization:** ROCKSOUL remains the product/control-plane identity; g4f remains the compatibility/runtime substrate with truthful attribution, explicit legacy boundaries, F4 architecture docs, and migration/release documentation.

## F4 trust and compatibility boundary

The production Mesh implementation is `g4f/rocksoul_mesh.py`. The older `MeshRegistry` inside `g4f/rocksoul_platform.py` remains compatibility-only and is not a canonical routing authority.

F3 provider lifecycle and F4 node lifecycle are intentionally independent. Mesh node failure cannot silently quarantine unrelated providers, and provider re-admission does not implicitly re-admit a Mesh node.

Remote Mesh node operations use HMAC-SHA256 authentication over canonical action/node/timestamp/nonce/payload data. Production deployments should use distinct per-node secrets and HTTPS endpoints. Shared secrets and plaintext local/private endpoints are development compatibility paths only and require explicit configuration.

## Verification requirements

The final v0.2.0 candidate may merge to `main` only when all of these are green on the final candidate head:

1. existing ROCKSOUL CI on Ubuntu / Python 3.13;
2. existing ROCKSOUL CI on Windows / Python 3.13;
3. dedicated ROCKSOUL Mesh CI on Ubuntu / Python 3.13;
4. dedicated ROCKSOUL Mesh CI on Windows / Python 3.13;
5. execution and Mesh CLI/core deterministic tests;
6. wheel and source-distribution build gates;
7. general repository Unittest compatibility workflow.

The production release workflow reruns deterministic repository regression tests and package build before creating `v0.2.0` and publishing its GitHub Release artifacts.

## Non-goals

This certification does not claim that every upstream provider works, that credentials/cookies are always available, that external networks are reliable, or that arbitrary distributed transports are certified. It certifies ROCKSOUL's execution-control contracts plus the transport-neutral F4 coordination/security/lifecycle/lease contract around trusted ROCKSOUL nodes.

F4 does not certify arbitrary remote-code execution, generic service discovery across untrusted networks, or F5 Arena benchmark methodology.

## Certification checklist

```text
[x] F0 guardrails proven
[x] F1 execution contracts and fallback
[x] F2 persistence and trace reconstruction
[x] F3 retry/cooldown/quarantine/probing/recovery controls
[x] F4 Mesh implementation/security/lifecycle/coordination/failure-boundary contract
[x] F4 deterministic core + operator CLI test coverage
[x] F4 independent Mesh CI/release gate configured
[x] F6 execution CLI contract
[x] F7 required execution + Mesh final-head CI gates before merge
[x] F8 product/Mesh docs and compatibility boundary
[ ] F5 Arena — deferred to separate gate
```

## Final evidence rule

The code and deterministic tests define the candidate. Documentation does not override CI. This certification becomes release truth on `main` only after the exact candidate head is green on all mandatory execution, Mesh, and general compatibility gates and is merged without further code changes.

## Recovery status on current `main`

The certification above is historical evidence for the original v0.2.0 candidate. ROCKSOUL was later recovered selectively from the archived `f4/mesh-core-doc` snapshot into the evolving g4f `main` line. Historical green runs do not certify the recovered code against the current runtime revision.

The Stage 2 current-main recovery commit `5b818f839c33150a48818b8f352161fc3ecf7c94` passed the ROCKSOUL CI matrix, Mesh CI, Arena CI, CodeQL Advanced, and general repository Unittest. This confirms that the recovered execution, Mesh, and Arena foundation is compatible with the current g4f runtime at that exact commit.

Stage 3 extends the Arena production evidence contract with offline manifest validation, exact local dataset SHA-256 verification before registration, registry/campaign readback, duplicate-key/non-finite JSON rejection, and installed-wheel entrypoint checks. Stage 3 implementation commit `56d9bc11813572cca343f3b556b6042ebc214edd` passed Arena CI [#42030958020](https://github.com/bjo163/agilty/actions/runs/42030958020), ROCKSOUL CI plus package/wheel smoke [#42030958117](https://github.com/bjo163/agilty/actions/runs/42030958117), general Unittest on Python 3.10 and 3.15 [#42030958126](https://github.com/bjo163/agilty/actions/runs/42030958126), and CodeQL Advanced [#42030958006](https://github.com/bjo163/agilty/actions/runs/42030958006). The dedicated Mesh CI remained green from Stage 2 [#42026291726](https://github.com/bjo163/agilty/actions/runs/42026291726); Stage 3 changed no Mesh implementation, and the broad ROCKSOUL suite re-ran offline Mesh contracts across all four OS/Python lanes. Do not activate remote Mesh traffic, run live provider campaigns, or publish a new release solely on the basis of deterministic offline verification.
