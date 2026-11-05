from __future__ import annotations

"""Offline-safe operator CLI for ROCKSOUL F5 production benchmark evidence."""

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from .rocksoul_arena import ArenaCase, ArenaError, ArenaStore, ArenaSuite
from .rocksoul_arena_production import (
    ArenaDatasetProvenance,
    ArenaEnvironmentEvidence,
    ArenaProductionPack,
    ArenaProductionStore,
    ArenaRepeatPolicy,
    ArenaTargetIdentity,
    campaign_to_dict,
)
from .rocksoul_db import DB_PATH, RocksoulDB

MAX_MANIFEST_BYTES = 5 * 1024 * 1024
HASH_CHUNK_BYTES = 1024 * 1024


class ManifestError(ValueError):
    """A production-pack manifest is incomplete or invalid."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ManifestError(f"manifest contains duplicate JSON key: {key}")
        value[key] = item
    return value


def _json_value(value: Any, label: str) -> Any:
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ManifestError(f"{label} must contain only finite JSON values: {exc}") from exc
    return value


def _emit(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True, default=str))


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestError(f"{label} must be a JSON object")
    return value


def _keys(
    value: Mapping[str, Any],
    *,
    required: set[str],
    allowed: set[str],
    label: str,
) -> None:
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - allowed)
    if missing:
        raise ManifestError(f"{label} missing required fields: {', '.join(missing)}")
    if unknown:
        raise ManifestError(f"{label} has unknown fields: {', '.join(unknown)}")


def _text(value: Mapping[str, Any], key: str, label: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ManifestError(f"{label}.{key} must be a non-empty string")
    return item.strip()


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ManifestError(f"{label} must be a finite number")
    try:
        number = float(value)
    except (OverflowError, ValueError):
        raise ManifestError(f"{label} must be a finite number") from None
    if not math.isfinite(number):
        raise ManifestError(f"{label} must be a finite number")
    return number


def _json_object(value: Any, label: str) -> dict[str, Any]:
    result = _object(value, label)
    try:
        json.dumps(result, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ManifestError(f"{label} must contain only finite JSON values: {exc}") from exc
    return result


def load_pack_manifest(path: str | Path) -> ArenaProductionPack:
    manifest_path = Path(path)
    try:
        with manifest_path.open("rb") as handle:
            raw_bytes = handle.read(MAX_MANIFEST_BYTES + 1)
    except OSError as exc:
        raise ManifestError(f"cannot read manifest {manifest_path}: {exc}") from exc
    if not raw_bytes or len(raw_bytes) > MAX_MANIFEST_BYTES:
        raise ManifestError(f"manifest size must be between 1 and {MAX_MANIFEST_BYTES} bytes")
    try:
        raw = json.loads(raw_bytes.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot parse manifest {manifest_path}: {exc}") from exc
    root = _object(raw, "manifest")
    _keys(
        root,
        required={"schema_version", "pack"},
        allowed={"schema_version", "pack"},
        label="manifest",
    )
    if type(root["schema_version"]) is not int or root["schema_version"] != 1:
        raise ManifestError("manifest.schema_version must be integer 1")

    pack_value = _object(root["pack"], "pack")
    pack_fields = {
        "name", "version", "suite", "dataset", "evaluator_revision",
        "repeat_policy", "environment_requirements", "network_requirements",
    }
    _keys(
        pack_value,
        required=pack_fields,
        allowed=pack_fields,
        label="pack",
    )

    suite_value = _object(pack_value["suite"], "pack.suite")
    suite_fields = {"name", "version", "evaluator", "provenance", "cases"}
    _keys(suite_value, required=suite_fields, allowed=suite_fields, label="pack.suite")
    cases_value = suite_value["cases"]
    if not isinstance(cases_value, list):
        raise ManifestError("pack.suite.cases must be an array")
    cases: list[ArenaCase] = []
    for index, raw_case in enumerate(cases_value):
        label = f"pack.suite.cases[{index}]"
        case = _object(raw_case, label)
        _keys(
            case,
            required={"case_id", "input", "expected"},
            allowed={"case_id", "input", "expected", "weight", "tags"},
            label=label,
        )
        _json_value(case["input"], f"{label}.input")
        _json_value(case["expected"], f"{label}.expected")
        weight = _number(case.get("weight", 1.0), f"{label}.weight")
        tags_value = case.get("tags", [])
        if not isinstance(tags_value, list) or any(not isinstance(tag, str) for tag in tags_value):
            raise ManifestError(f"{label}.tags must be an array of strings")
        cases.append(
            ArenaCase(
                case_id=_text(case, "case_id", label),
                input=case["input"],
                expected=case["expected"],
                weight=weight,
                tags=tuple(tags_value),
            )
        )
    provenance = _json_object(suite_value["provenance"], "pack.suite.provenance")
    suite = ArenaSuite(
        name=_text(suite_value, "name", "pack.suite"),
        version=_text(suite_value, "version", "pack.suite"),
        evaluator=_text(suite_value, "evaluator", "pack.suite"),
        provenance=provenance,
        cases=tuple(cases),
    )

    dataset_value = _object(pack_value["dataset"], "pack.dataset")
    dataset_fields = {
        "source", "revision", "sha256", "split_policy", "contamination_review", "license"
    }
    _keys(
        dataset_value,
        required=dataset_fields - {"license"},
        allowed=dataset_fields,
        label="pack.dataset",
    )
    license_value = dataset_value.get("license")
    if license_value is not None and not isinstance(license_value, str):
        raise ManifestError("pack.dataset.license must be a string when supplied")
    dataset = ArenaDatasetProvenance(
        source=_text(dataset_value, "source", "pack.dataset"),
        revision=_text(dataset_value, "revision", "pack.dataset"),
        sha256=_text(dataset_value, "sha256", "pack.dataset").lower(),
        split_policy=_text(dataset_value, "split_policy", "pack.dataset"),
        contamination_review=_text(dataset_value, "contamination_review", "pack.dataset"),
        license=license_value,
    )

    repeat_value = _object(pack_value["repeat_policy"], "pack.repeat_policy")
    _keys(
        repeat_value,
        required={"runs", "max_score_stddev"},
        allowed={"runs", "max_score_stddev"},
        label="pack.repeat_policy",
    )
    runs = repeat_value["runs"]
    if type(runs) is not int:
        raise ManifestError("pack.repeat_policy.runs must be an integer")
    repeat_policy = ArenaRepeatPolicy(
        runs=runs,
        max_score_stddev=_number(
            repeat_value["max_score_stddev"], "pack.repeat_policy.max_score_stddev"
        ),
    )

    environment_requirements = _json_object(
        pack_value["environment_requirements"], "pack.environment_requirements"
    )
    network_requirements = _json_object(
        pack_value["network_requirements"], "pack.network_requirements"
    )
    return ArenaProductionPack(
        name=_text(pack_value, "name", "pack"),
        version=_text(pack_value, "version", "pack"),
        suite=suite,
        dataset=dataset,
        evaluator_revision=_text(pack_value, "evaluator_revision", "pack"),
        repeat_policy=repeat_policy,
        environment_requirements=environment_requirements,
        network_requirements=network_requirements,
    )


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as handle:
            while True:
                chunk = handle.read(HASH_CHUNK_BYTES)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError as exc:
        raise ManifestError(f"cannot read dataset artifact {path}: {exc}") from exc
    return digest.hexdigest()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ROCKSOUL F5 production evidence registry (offline by default)"
    )
    parser.add_argument("--db", default=str(DB_PATH), help="ROCKSOUL SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="show production evidence registry status")
    status.set_defaults(action="status")

    validate = sub.add_parser("validate-pack", help="validate a pack manifest without changing state")
    validate.add_argument("manifest")
    validate.add_argument("--dataset-file", help="optional local dataset artifact to hash-check")
    validate.set_defaults(action="validate-pack")

    register = sub.add_parser("register-pack", help="register only after exact dataset hash verification")
    register.add_argument("manifest")
    register.add_argument("--dataset-file", required=True, help="local dataset artifact matching manifest SHA-256")
    register.set_defaults(action="register-pack")

    packs = sub.add_parser("list-packs", help="list registered immutable production packs")
    packs.add_argument("--limit", type=int, default=100)
    packs.set_defaults(action="list-packs")

    campaigns = sub.add_parser("list-campaigns", help="list persisted production campaigns")
    campaigns.add_argument("--pack-digest")
    campaigns.add_argument("--limit", type=int, default=100)
    campaigns.set_defaults(action="list-campaigns")

    show = sub.add_parser("show-campaign", help="show one campaign and its evidence")
    show.add_argument("campaign_id")
    show.set_defaults(action="show-campaign")

    fixture = sub.add_parser("fixture-campaign", help="run a synthetic offline end-to-end contract fixture")
    fixture.set_defaults(action="fixture-campaign")
    return parser


def _fixture_pack() -> tuple[ArenaProductionPack, bytes]:
    artifact = b"ROCKSOUL F5 deterministic production-contract fixture v1\n"
    suite = ArenaSuite(
        name="rocksoul-production-cli-fixture",
        version="1",
        evaluator="json_exact",
        provenance={
            "source": "embedded-repository-fixture",
            "revision": "1",
            "network": False,
            "purpose": "offline production-contract integration test",
        },
        cases=(
            ArenaCase("addition", {"left": 2, "right": 3}, {"value": 5}),
            ArenaCase("sorting", [3, 1, 2], [1, 2, 3]),
        ),
    )
    pack = ArenaProductionPack(
        name="rocksoul-production-cli-fixture",
        version="1",
        suite=suite,
        dataset=ArenaDatasetProvenance(
            source="embedded:rocksoul-production-cli-fixture",
            revision="1",
            sha256=hashlib.sha256(artifact).hexdigest(),
            split_policy="not_applicable",
            contamination_review="synthetic deterministic fixture; no external model content",
            license="repository test fixture",
        ),
        evaluator_revision="json-exact-v1",
        repeat_policy=ArenaRepeatPolicy(runs=3, max_score_stddev=0.0),
        environment_requirements={"network": "offline", "runtime": "python"},
        network_requirements={"required": False, "mode": "offline"},
    )
    return pack, artifact


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        arena = ArenaStore(RocksoulDB(Path(args.db)))
        store = ArenaProductionStore(arena)

        if args.action == "status":
            _emit(store.status())
            return 0

        if args.action == "validate-pack":
            pack = load_pack_manifest(args.manifest)
            store.validate_pack(pack)
            verified = False
            actual_digest = None
            if args.dataset_file:
                actual_digest = sha256_file(args.dataset_file)
                if actual_digest != pack.dataset.sha256:
                    raise ManifestError(
                        f"dataset SHA-256 mismatch: expected {pack.dataset.sha256}, got {actual_digest}"
                    )
                verified = True
            _emit(
                {
                    "valid": True,
                    "pack_digest": pack.digest,
                    "dataset_expected_sha256": pack.dataset.sha256,
                    "dataset_actual_sha256": actual_digest,
                    "artifact_verified": verified,
                    "ready_to_register": verified,
                    "network_calls": False,
                }
            )
            return 0

        if args.action == "register-pack":
            pack = load_pack_manifest(args.manifest)
            store.validate_pack(pack)
            actual_digest = sha256_file(args.dataset_file)
            if actual_digest != pack.dataset.sha256:
                raise ManifestError(
                    f"dataset SHA-256 mismatch: expected {pack.dataset.sha256}, got {actual_digest}"
                )
            pack_digest = store.register_pack(pack)
            _emit(
                {
                    "registered": True,
                    "pack_digest": pack_digest,
                    "artifact_verified": True,
                    "dataset_sha256": actual_digest,
                    "network_calls": False,
                }
            )
            return 0

        if args.action == "list-packs":
            _emit(store.list_packs(limit=args.limit))
            return 0

        if args.action == "list-campaigns":
            _emit(store.list_campaigns(args.pack_digest, limit=args.limit))
            return 0

        if args.action == "show-campaign":
            campaign = store.get_campaign(args.campaign_id)
            if campaign is None:
                _emit({"found": False, "campaign_id": args.campaign_id})
                return 3
            _emit(campaign)
            return 0

        if args.action == "fixture-campaign":
            pack, _artifact = _fixture_pack()
            campaign = store.run_campaign(
                pack,
                ArenaTargetIdentity(
                    provider="synthetic-fixture",
                    model="rocksoul-offline-fixture",
                    revision="fixture-v1",
                    runtime_revision="local-test-runtime",
                ),
                ArenaEnvironmentEvidence(
                    runtime="python",
                    os="portable",
                    python="current",
                    network_mode="offline",
                    region="local",
                ),
                lambda case: (
                    {"value": case.input["left"] + case.input["right"]}
                    if case.case_id == "addition"
                    else sorted(case.input)
                ),
            )
            _emit(campaign_to_dict(campaign))
            return 0

        parser.error(f"unsupported command: {args.action}")
    except (ArenaError, ManifestError, OSError, TypeError, ValueError) as exc:
        _emit({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
