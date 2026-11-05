from __future__ import annotations

"""Offline-safe operator CLI for ROCKSOUL F5 production benchmark evidence."""

import argparse
import hashlib
import json
import math
import os
import platform
import sys
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

    campaign = sub.add_parser("run-campaign", help="run an explicitly authorized campaign against one exact provider/model")
    campaign.add_argument("manifest", help="the exact registered pack manifest")
    campaign.add_argument("--dataset-file", required=True, help="local dataset artifact matching the registered SHA-256")
    campaign.add_argument("--provider", required=True, help="one exact g4f provider name; provider chains are rejected")
    campaign.add_argument("--model", required=True)
    campaign.add_argument("--provider-revision", required=True, help="exact provider/model revision identifier")
    campaign.add_argument("--runtime-revision", required=True, help="exact g4f/ROCKSOUL runtime commit or build identifier")
    campaign.add_argument("--network-mode", choices=["offline", "restricted", "online"], required=True)
    campaign.add_argument("--region", required=True)
    campaign.add_argument("--timeout", type=float, default=30.0, help="provider timeout hint in seconds")
    campaign.add_argument("--max-tokens", type=int, default=256)
    campaign.add_argument("--max-requests", type=int, default=100, help="hard cap across cases multiplied by repeat runs (maximum 1000)")
    campaign.add_argument("--confirm-live", action="store_true", help="explicitly confirm that this command may invoke the configured provider")
    campaign.add_argument("--confirm-pack-digest", required=True, help="must exactly match the registered immutable pack digest")
    campaign.set_defaults(action="run-campaign")

    verify_campaign = sub.add_parser("verify-campaign", help="audit one campaign against its immutable pack and Arena run records")
    verify_campaign.add_argument("campaign_id")
    verify_campaign.set_defaults(action="verify-campaign")

    report = sub.add_parser("campaign-report", help="build a deterministic per-pack/per-target evidence report")
    report.add_argument("--pack-digest", required=True)
    report.add_argument("--target-digest")
    report.add_argument("--limit", type=int, default=1000)
    report.set_defaults(action="campaign-report")

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


def _live_case_messages(value: Any, label: str) -> list[dict[str, str]]:
    """Validate a deliberately small, text-only live Arena input contract."""
    if isinstance(value, str):
        messages = [{"role": "user", "content": value}]
    elif isinstance(value, dict) and set(value).issubset({"prompt", "system"}) and "prompt" in value:
        if not isinstance(value["prompt"], str):
            raise ManifestError(f"{label}.input.prompt must be a string")
        messages = []
        system = value.get("system")
        if system is not None:
            if not isinstance(system, str):
                raise ManifestError(f"{label}.input.system must be a string")
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": value["prompt"]})
    elif isinstance(value, dict) and set(value) == {"messages"} and isinstance(value["messages"], list):
        messages = []
        for index, item in enumerate(value["messages"]):
            if not isinstance(item, dict) or set(item) != {"role", "content"}:
                raise ManifestError(f"{label}.input.messages[{index}] must contain only role and content")
            role, text_value = item["role"], item["content"]
            if role not in {"system", "user", "assistant"} or not isinstance(text_value, str):
                raise ManifestError(f"{label}.input.messages[{index}] has an unsupported role or non-text content")
            messages.append({"role": role, "content": text_value})
    else:
        raise ManifestError(f"{label}.input must be text or a prompt/messages object")
    if not messages or not any(item["role"] == "user" for item in messages):
        raise ManifestError(f"{label}.input must contain at least one user message")
    if any(len(item["content"]) > 65536 for item in messages):
        raise ManifestError(f"{label}.input message exceeds the 65536-character live safety limit")
    return messages


def _resolve_live_provider(provider_name: str) -> Any:
    """Resolve one exact provider through the existing g4f provider registry."""
    try:
        from .client.service import convert_to_provider
        from .providers.retry_provider import IterListProvider
        provider = convert_to_provider(provider_name)
    except Exception as exc:
        raise ManifestError(f"cannot resolve provider {provider_name!r}: {type(exc).__name__}: {exc}") from exc
    if isinstance(provider, IterListProvider) or isinstance(provider, str):
        raise ManifestError("run-campaign requires one exact provider; provider chains are not allowed")
    return provider


def _provider_label(provider: Any) -> str:
    return str(getattr(provider, "__name__", type(provider).__name__))


def _live_executor(provider: Any, model: str, timeout: float, max_tokens: int):
    """Build a lazy g4f Client executor; creating it does not send a request."""
    from .client import Client
    client = Client()

    def execute(case: ArenaCase) -> Any:
        messages = _live_case_messages(case.input, f"case {case.case_id}")
        response = client.chat.completions.create(
            messages=messages,
            model=model,
            provider=provider,
            stream=False,
            timeout=timeout,
            max_tokens=max_tokens,
        )
        if isinstance(response, str):
            output = response
        else:
            choices = response.get("choices") if isinstance(response, dict) else getattr(response, "choices", None)
            if not choices:
                raise ValueError("provider returned no completion choices")
            first = choices[0]
            message = first.get("message") if isinstance(first, dict) else getattr(first, "message", None)
            output = message.get("content") if isinstance(message, dict) else getattr(message, "content", None)
        if not isinstance(output, str):
            raise ValueError("provider completion content must be text")
        if isinstance(case.expected, str):
            return output
        try:
            return json.loads(output)
        except json.JSONDecodeError as exc:
            raise ValueError("case expects JSON output but provider returned invalid JSON") from exc

    return execute


def _run_authorized_campaign(args: Any, store: ArenaProductionStore) -> dict[str, Any]:
    """Perform all local checks before the first provider call."""
    if not args.confirm_live:
        raise ManifestError("live campaign refused: pass --confirm-live explicitly")
    if os.environ.get("ROCKSOUL_ALLOW_LIVE_ARENA") != "1":
        raise ManifestError("live campaign refused: set ROCKSOUL_ALLOW_LIVE_ARENA=1 in the operator environment")
    for field_name in ("provider", "model", "provider_revision", "runtime_revision", "region"):
        if not isinstance(getattr(args, field_name), str) or not getattr(args, field_name).strip():
            raise ManifestError(f"{field_name.replace('_', '-')} must be a non-empty exact identifier")
    if not math.isfinite(args.timeout) or args.timeout <= 0 or args.timeout > 300:
        raise ManifestError("timeout must be finite and between 0 and 300 seconds")
    if args.max_tokens < 1 or args.max_tokens > 4096:
        raise ManifestError("max-tokens must be between 1 and 4096")
    if args.max_requests < 1 or args.max_requests > 1000:
        raise ManifestError("max-requests must be between 1 and 1000")

    pack = load_pack_manifest(args.manifest)
    store.validate_pack(pack)
    if args.confirm_pack_digest != pack.digest:
        raise ManifestError("confirmed pack digest does not match the manifest")
    if not store.has_pack(pack.digest):
        raise ManifestError("production pack is not registered; verify and register it before running a campaign")
    actual_digest = sha256_file(args.dataset_file)
    if actual_digest != pack.dataset.sha256:
        raise ManifestError(f"dataset SHA-256 mismatch: expected {pack.dataset.sha256}, got {actual_digest}")

    network = dict(pack.network_requirements)
    declared_mode = network.get("mode")
    required_network = network.get("required")
    if type(required_network) is not bool or declared_mode not in {"offline", "restricted", "online"}:
        raise ManifestError("pack.network_requirements must declare boolean required and a supported mode")
    if declared_mode != args.network_mode:
        raise ManifestError(f"observed network mode {args.network_mode!r} does not match pack requirement {declared_mode!r}")
    if required_network and args.network_mode == "offline":
        raise ManifestError("pack requires network access but campaign was declared offline")

    env_requirements = dict(pack.environment_requirements)
    python_requirement = env_requirements.get("python")
    current_python = f"{sys.version_info.major}.{sys.version_info.minor}"
    if python_requirement not in (None, "any", "declared") and str(python_requirement) != current_python:
        raise ManifestError(f"current Python {current_python} does not match pack requirement {python_requirement!r}")
    os_requirement = env_requirements.get("operating_system", env_requirements.get("os"))
    current_os = platform.system().lower()
    if os_requirement not in (None, "any", "declared") and str(os_requirement).lower() not in {current_os, platform.platform().lower()}:
        raise ManifestError(f"current OS {platform.system()} does not match pack requirement {os_requirement!r}")

    request_count = len(pack.suite.cases) * pack.repeat_policy.runs
    if request_count > args.max_requests:
        raise ManifestError(f"campaign requires {request_count} provider requests, above max-requests={args.max_requests}")
    for case in pack.suite.cases:
        _live_case_messages(case.input, f"case {case.case_id}")
        if not isinstance(case.expected, (str, dict, list, int, float, bool)) and case.expected is not None:
            raise ManifestError(f"case {case.case_id} expected value is not JSON-compatible")

    provider = _resolve_live_provider(args.provider)
    provider_name = _provider_label(provider)
    executor = _live_executor(provider, args.model, args.timeout, args.max_tokens)
    campaign = store.run_campaign(
        pack,
        ArenaTargetIdentity(
            provider=provider_name,
            model=args.model,
            revision=args.provider_revision,
            runtime_revision=args.runtime_revision,
        ),
        ArenaEnvironmentEvidence(
            runtime="g4f.client.Client",
            os=platform.platform(),
            python=sys.version.split()[0],
            network_mode=args.network_mode,
            region=args.region,
            extra={"timeout_hint_seconds": args.timeout, "max_tokens": args.max_tokens, "max_provider_requests": args.max_requests},
        ),
        executor,
    )
    return {
        **campaign_to_dict(campaign),
        "ok": campaign.variance_accepted,
        "campaign_kind": "operator-authorized-live",
        "artifact_verified": True,
        "dataset_sha256": actual_digest,
        "provider_requests": request_count,
        "network_calls": True,
        "note": "Campaign evidence is not an independent dataset license, contamination, or scientific-quality audit.",
    }



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

        if args.action == "verify-campaign":
            audit = store.verify_campaign(args.campaign_id)
            if audit is None:
                _emit({"found": False, "campaign_id": args.campaign_id})
                return 3
            _emit(audit)
            return 0 if audit["integrity_verified"] else 4

        if args.action == "campaign-report":
            if args.limit < 1 or args.limit > 1000:
                raise ManifestError("limit must be between 1 and 1000")
            report = store.campaign_report(args.pack_digest, args.target_digest, limit=args.limit)
            _emit(report)
            return 0 if report["report_status"] == "EVIDENCE_VERIFIED" else 4 if report["report_status"] == "EVIDENCE_REJECTED" else 3

        if args.action == "run-campaign":
            payload = _run_authorized_campaign(args, store)
            _emit(payload)
            return 0 if payload["variance_accepted"] else 4

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
    except (ArenaError, ManifestError, OSError, TypeError, ValueError, ImportError) as exc:
        _emit({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
