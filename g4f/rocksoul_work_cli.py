from __future__ import annotations

"""Operator CLI for inspecting and governing persisted ROCKSOUL WorkItems."""

import argparse
import json
from pathlib import Path

from .rocksoul_verifier_engine import VerificationEngine
from .rocksoul_verification import VerificationProfile
from typing import Any

from .rocksoul_contracts import WorkItem, WorkStatus
from .rocksoul_db import RocksoulDB
from .rocksoul_work_store import WorkItemStore


def _print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="ROCKSOUL WorkItem operator")
    commands = parser.add_subparsers(dest="command", required=True)

    profile_register = commands.add_parser("profile-register", help="Register an immutable verification profile version")
    profile_register.add_argument("profile", type=Path)

    profile_list = commands.add_parser("profile-list", help="List registered verification profiles")
    profile_list.add_argument("--limit", type=int, default=100)

    profile_get = commands.add_parser("profile-get", help="Read a registered verification profile")
    profile_get.add_argument("profile_id")
    profile_get.add_argument("version", type=int)

    create = commands.add_parser("create", help="Create a WorkItem from a JSON contract file")
    create.add_argument("contract", type=Path)

    show = commands.add_parser("get", help="Read a WorkItem and its lifecycle events")
    show.add_argument("work_id")

    listing = commands.add_parser("list", help="List persisted WorkItems")
    listing.add_argument("--limit", type=int, default=50)
    listing.add_argument("--offset", type=int, default=0)

    transition = commands.add_parser("transition", help="Apply a guarded lifecycle transition")
    transition.add_argument("work_id")
    transition.add_argument("expected_status", choices=[x.value for x in WorkStatus])
    transition.add_argument("target_status", choices=[x.value for x in WorkStatus])
    transition.add_argument("--payload", default="{}", help="JSON event payload")

    run_verify = commands.add_parser("verify", help="Execute a registered deterministic verifier against a local artifact")
    run_verify.add_argument("work_id")
    run_verify.add_argument("criterion_id")
    run_verify.add_argument("profile_id")
    run_verify.add_argument("profile_version", type=int)
    run_verify.add_argument("artifact", type=Path)
    run_verify.add_argument("--source", required=True, help="Stable artifact provenance reference")
    run_verify.add_argument("--expected-sha256")
    run_verify.add_argument("--schema", type=Path, help="JSON schema file for json_schema profiles")

    verify = commands.add_parser("verify-chain", help="Verify append-only event hash chain")
    verify.add_argument("work_id")

    args = parser.parse_args()
    store = WorkItemStore(RocksoulDB())

    if args.command == "profile-register":
        raw = json.loads(args.profile.read_text(encoding="utf-8"))
        _print(store.profiles.register(VerificationProfile.from_dict(raw)))
    elif args.command == "profile-list":
        _print(store.profiles.list(args.limit))
    elif args.command == "profile-get":
        result = store.profiles.get(args.profile_id, args.version)
        if result is None:
            raise SystemExit("Verification profile not found")
        _print(result)
    elif args.command == "create":
        raw = json.loads(args.contract.read_text(encoding="utf-8"))
        _print(store.create(WorkItem.from_dict(raw)))
    elif args.command == "get":
        result = store.get(args.work_id)
        if result is None:
            raise SystemExit("WorkItem not found")
        _print(result)
    elif args.command == "list":
        _print(store.list(args.limit, args.offset))
    elif args.command == "transition":
        payload = json.loads(args.payload)
        if not isinstance(payload, dict):
            raise SystemExit("--payload must be a JSON object")
        _print(store.transition(args.work_id, args.target_status,
                                expected_status=args.expected_status, payload=payload))
    elif args.command == "verify":
        profile = store.profiles.resolve(args.profile_id, args.profile_version)
        schema = json.loads(args.schema.read_text(encoding="utf-8")) if args.schema else None
        execution = VerificationEngine().verify(
            profile, args.artifact.read_bytes(), source=args.source,
            expected_sha256=args.expected_sha256, schema=schema,
        )
        _print(store.record_verification(args.work_id, args.criterion_id, execution))
    elif args.command == "verify-chain":
        _print(store.verify_event_chain(args.work_id))


if __name__ == "__main__":
    main()
