# ROCKSOUL Arena Production CLI

The `rocksoul-arena-production` command manages production benchmark evidence metadata. It is intentionally offline: it does not discover providers, invoke model endpoints, perform live verification, or execute remote campaigns.

## Commands

```text
rocksoul-arena-production status
rocksoul-arena-production validate-pack <manifest.json> [--dataset-file <path>]
rocksoul-arena-production register-pack <manifest.json> --dataset-file <path>
rocksoul-arena-production list-packs [--limit <n>]
rocksoul-arena-production list-campaigns [--pack-digest <digest>] [--limit <n>]
rocksoul-arena-production show-campaign <campaign-id>
rocksoul-arena-production fixture-campaign
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

Unknown fields are rejected so a misspelled evidence field cannot silently disappear. Suite and production pack identities are immutable by their respective name/version pairs. Any content change requires a version bump.

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

## Security and claim boundary

- No network client is imported or called by this CLI.
- Registering a pack proves only that its manifest is structurally valid and the selected local artifact matches its declared SHA-256.
- A contamination-review string is traceable metadata, not an independent audit of the dataset.
- Registering a pack does not mean a production campaign has run.
- An authoritative live claim still requires a real source/dataset review, exact provider/model/runtime revision, observed environment evidence, repeated live campaigns inside the declared variance bound, and all current-main release gates.
- Do not put API keys, cookies, personal data, or private held-out evaluation contents in the manifest.

