# ROCKSOUL Stage 4 — Operator-Authorized Campaign Execution

## Goal

Close the operational gap between Stage 3's offline evidence registry and an intentionally authorized live benchmark run. Stage 4 adds a controlled local operator path; it does not invent a dataset, trigger a live provider, or certify model quality.

## Implemented scope

1. Add `run-campaign` to `rocksoul-arena-production`.
2. Require two independent opt-ins: `--confirm-live` and `ROCKSOUL_ALLOW_LIVE_ARENA=1`.
3. Require a previously registered immutable pack and an exact `--confirm-pack-digest` match.
4. Re-hash the exact local dataset artifact immediately before any provider request.
5. Pin execution to one exact provider and model; reject provider chains and do not use adaptive fallback/retries.
6. Require explicit provider/model revision, runtime revision, region, and observed network mode.
7. Check the pack's network, Python, and OS requirements before the first provider call.
8. Validate every text-only prompt before starting; cap prompt length, max tokens, timeout hint, and total provider request count.
9. Persist every repeated Arena run and campaign with exact target and observed environment evidence.
10. Return a non-zero exit code for campaigns whose variance threshold is not accepted.
11. Add fake-provider tests; no external provider or credentials are used by CI.

## Safety boundary

- No live provider call was executed as part of Stage 4 implementation or CI.
- The command never auto-registers a pack, performs provider fallback, or retries requests.
- Credentials are read only through the provider's existing supported configuration path; they must not be stored in manifests or command-line arguments.
- A request-count cap is not a guarantee of monetary cost; providers may price tokens differently or enforce their own quotas.
- Provider timeout is passed as a provider hint; providers that ignore it may have different transport behavior.
- A green Stage 4 gate certifies the operator workflow, not dataset licensing, contamination, scientific methodology, or real provider quality.

## Acceptance checklist

- [x] Live execution requires CLI and environment opt-in.
- [x] Exact pack digest and prior registration are mandatory.
- [x] Dataset hash is re-verified before execution.
- [x] Provider/model/runtime/environment identity is explicit.
- [x] Provider chain/fallback and automatic retries are disallowed.
- [x] Request count, max tokens, prompt size, and timeout hint are bounded.
- [x] All prompts are preflighted before first provider invocation.
- [x] Campaign/run evidence persists and can be read back.
- [x] Fake-provider tests cover the operator flow and refusal paths.
- [x] No live external provider was called by the implementation or CI.

## Remaining separate production activation requirements

A real pack still needs an authentic dataset and source revision, explicit license/use basis, independent contamination/leakage review, independent evaluator review, exact model/provider/runtime revisions, real environment evidence, repeated authorized campaigns, and a final release-gate review. Stage 4 does not bypass these requirements.
