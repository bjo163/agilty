# ROCKSOUL Arena Production CLI

The `rocksoul-arena-production` command manages production benchmark evidence metadata. All read-only registry commands and the synthetic fixture are offline. The separately gated `run-campaign` subcommand is the only path that can invoke one real provider, and it requires an explicit operator opt-in.

## Commands

```text
rocksoul-arena-production status
rocksoul-arena-production validate-pack <manifest.json> [--dataset-file <path>]
rocksoul-arena-production register-pack <manifest.json> --dataset-file <path>
rocksoul-arena-production list-packs [--limit <n>]
rocksoul-arena-production list-campaigns [--pack-digest <digest>] [--limit <n>]
rocksoul-arena-production show-campaign <campaign-id>
rocksoul-arena-production fixture-campaign
rocksoul-arena-production run-campaign <manifest.json> --dataset-file <path> --provider <name> --model <model> --provider-revision <revision> --runtime-revision <revision> --network-mode <mode> --region <region> --confirm-live --confirm-pack-digest <digest>
```

The same commands are available from a source checkout through `python -m g4f.rocksoul_arena_production_cli`.

## Manifest schema v1

A manifest is UTF-8 JSON, at most 5 MiB, with exactly these top-level keys:

```json
{
  "schema_version": 1,
  "pack": {
    "name": "provider-quality",
    "version": "1",
    "suite": {
      "name": "provider-quality-cases",
      "version": "1",
      "evaluator": "json_exact",
      "provenance": {
        "source": "https://example.invalid/dataset",
        "revision": "immutable-revision-or-commit",
        "network": false
      },
      "cases": [
        {
          "case_id": "case-001",
          "input": {"prompt": "example"},
          "expected": {"answer": "example"},
          "weight": 1.0,
          "tags": ["smoke"]
        }
      ]
    },
    "dataset": {
      "source": "dataset publisher or immutable URI",
      "revision": "dataset revision",
      "sha256": "64-character SHA-256 digest",
      "split_policy": "public_only",
      "contamination_review": "review record and reviewer/method",
      "license": "dataset license or usage basis"
    },
    "evaluator_revision": "evaluator commit or version",
    "repeat_policy": {
      "runs": 3,
      "max_score_stddev": 1.0
    },
    "environment_requirements": {
      "python": "3.13",
      "operating_system": "declared"
    },
    "network_requirements": {
      "required": false,
      "mode": "offline"
    }
  }
}
```

Allowed split policies are `public_only`, `public_and_held_out`, `held_out_only`, and `not_applicable`. Allowed network modes for a campaign's observed environment are `offline`, `restricted`, and `online`. Repeat count must be an integer from 2 through 100; score standard deviation must be finite and non-negative.

Duplicate JSON keys are rejected at every nesting level; non-finite numbers and unknown fields are rejected so ambiguous or misspelled evidence cannot silently disappear. Suite and production pack identities are immutable by their respective name/version pairs. Any content change requires a version bump.

## Safe registration workflow

1. Create the manifest from the exact versioned benchmark artifact.
2. Run `validate-pack manifest.json` to check schema and structural constraints. This does **not** verify that the declared artifact exists.
3. Run `validate-pack manifest.json --dataset-file ./dataset.json` to stream the file and verify the declared SHA-256. A successful response sets `artifact_verified=true`.
4. Only then run `register-pack manifest.json --dataset-file ./dataset.json`. Registration repeats the digest check; a mismatch fails before the registry is written.
5. Inspect the persisted record with `list-packs`.

Example:

```bash
python -m g4f.rocksoul_arena_production_cli validate-pack pack.json --dataset-file ./dataset.json
python -m g4f.rocksoul_arena_production_cli register-pack pack.json --dataset-file ./dataset.json
python -m g4f.rocksoul_arena_production_cli list-packs
```

The artifact is hashed in 1 MiB chunks; the file is not loaded wholly into memory. The CLI stores the pack manifest and digest rather than silently copying an arbitrary dataset into the control-plane database.

## Campaign evidence readback

`list-campaigns` may be filtered by pack digest. `show-campaign` returns the exact target identity, observed runtime/OS/Python/network environment, repeated scores, variance decision, and underlying Arena run IDs.

`fixture-campaign` creates an end-to-end synthetic campaign using an embedded deterministic dataset fixture, a synthetic target, and `network_mode=offline`. It exists for installation and persistence verification only; it is not a real provider benchmark.

## Explicitly authorized campaign execution (Stage 4)

`run-campaign` is the only command that invokes a real provider. It pins the campaign to one exact provider/model; the adaptive router, fallback chain, and automatic retries are not used.

Before the first provider request it verifies all of the following:

1. `--confirm-live` is present **and** the operator process has `ROCKSOUL_ALLOW_LIVE_ARENA=1`.
2. The manifest is structurally valid and its digest exactly matches `--confirm-pack-digest`.
3. The exact pack digest is already registered; registration is never performed by `run-campaign`.
4. The supplied local dataset file still matches the registered manifest SHA-256.
5. The operator-declared network mode matches the pack requirement; Python and OS requirements are checked where specified. The network path itself is not independently inspected—the operator attests to that part of the execution environment.
6. Every test input is valid text-only chat input before any provider call is made.
7. `case_count × repeat_runs` is within `--max-requests` (1–1000). Each request also has a caller-set `--max-tokens` cap and a provider timeout hint.

Example (only in an intentionally configured operator environment):

```bash
ROCKSOUL_ALLOW_LIVE_ARENA=1 python -m g4f.rocksoul_arena_production_cli run-campaign pack.json \\
  --dataset-file ./dataset.json --provider Openai --model gpt-4o-mini \\
  --provider-revision <provider-or-model-revision> --runtime-revision <git-commit> \\
  --network-mode online --region <region> --max-tokens 256 --max-requests 30 \\
  --confirm-live --confirm-pack-digest <registered-pack-sha256>
```

Provider credentials must be configured through the provider's existing supported configuration path; never put credentials in manifests or command-line arguments. Repeats run sequentially without automatic fallback or retries. A campaign outside the variance threshold is persisted but returns exit code 4 and `ok=false`. CI exercises this path with a fake provider only. A request-count cap does not guarantee monetary cost, and the provider timeout is a hint that some providers may interpret differently.

The command is not wired into GitHub Actions, cron, startup, or the default test suite. No live campaign is started automatically.

## Security and claim boundary

- No network client is imported or called by this CLI.
- Registering a pack proves only that its manifest is structurally valid and the selected local artifact matches its declared SHA-256.
- A contamination-review string is traceable metadata, not an independent audit of the dataset.
- Registering a pack does not mean a production campaign has run.
- An authoritative live claim still requires a real source/dataset review, exact provider/model/runtime revision, observed environment evidence, repeated live campaigns inside the declared variance bound, and all current-main release gates.
- Do not put API keys, cookies, personal data, or private held-out evaluation contents in the manifest.

