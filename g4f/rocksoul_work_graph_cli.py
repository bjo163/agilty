from __future__ import annotations

"""Offline operator CLI for the ROCKSOUL WorkGraph registry."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .rocksoul_db import DB_PATH, RocksoulDB
from .rocksoul_work_graph import WorkGraph, WorkGraphValidationError
from .rocksoul_work_graph_store import WorkGraphStore, WorkGraphStoreError
from .rocksoul_work_store import WorkItemStore


def _emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect and manage local ROCKSOUL WorkGraphs.")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Register an immutable graph from a JSON file")
    create.add_argument("file", type=Path)

    listing = sub.add_parser("list", help="List registered graphs")
    listing.add_argument("--limit", type=int, default=50)
    listing.add_argument("--offset", type=int, default=0)

    get = sub.add_parser("get", help="Read a graph and its event history")
    get.add_argument("graph_id")

    verify = sub.add_parser("verify", help="Verify the graph contract and audit event chain")
    verify.add_argument("graph_id")

    readiness = sub.add_parser("readiness", help="Resolve readiness from authoritative WorkItem states")
    readiness.add_argument("graph_id")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        db = RocksoulDB(args.db)
        graphs = WorkGraphStore(db)
        if args.command == "create":
            raw = json.loads(args.file.read_text(encoding="utf-8"))
            graph = WorkGraph.from_dict(raw)
            _emit(graphs.create(graph))
        elif args.command == "list":
            _emit(graphs.list(limit=args.limit, offset=args.offset))
        elif args.command == "get":
            _emit(graphs.get(args.graph_id))
        elif args.command == "verify":
            result = graphs.verify_event_chain(args.graph_id)
            _emit(result)
            return 0 if result.get("ok") else 2
        elif args.command == "readiness":
            _emit(graphs.resolve_readiness(args.graph_id, WorkItemStore(db)))
        return 0
    except (OSError, json.JSONDecodeError, WorkGraphValidationError, WorkGraphStoreError, ValueError) as exc:
        print(f"rocksoul-work-graph: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
