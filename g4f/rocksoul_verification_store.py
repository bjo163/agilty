from __future__ import annotations

"""SQLite persistence for immutable verification profile versions."""

import json
from typing import Any

from .rocksoul_db import RocksoulDB
from .rocksoul_verification import VerificationProfile, VerificationProfileError, VerificationProfileRegistry


PROFILE_SCHEMA = """
CREATE TABLE IF NOT EXISTS rocksoul_verification_profiles (
    profile_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    profile_json TEXT NOT NULL,
    profile_digest TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(profile_id, version)
);
"""


class VerificationProfileStore:
    def __init__(self, db: RocksoulDB) -> None:
        self.db = db
        with db.connect() as conn:
            conn.executescript(PROFILE_SCHEMA)

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)

    def register(self, profile: VerificationProfile) -> dict[str, Any]:
        if not isinstance(profile, VerificationProfile):
            raise VerificationProfileError("register requires a validated VerificationProfile")
        encoded = self._json(profile.to_dict())
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT profile_digest FROM rocksoul_verification_profiles WHERE profile_id=? AND version=?",
                (profile.profile_id, profile.version),
            ).fetchone()
            if existing:
                if existing["profile_digest"] != profile.digest:
                    raise VerificationProfileError("profile version is immutable and already registered differently")
                return self.get(profile.profile_id, profile.version, connection=conn)
            conn.execute(
                "INSERT INTO rocksoul_verification_profiles(profile_id,version,profile_json,profile_digest) VALUES(?,?,?,?)",
                (profile.profile_id, profile.version, encoded, profile.digest),
            )
            return self.get(profile.profile_id, profile.version, connection=conn)

    def get(self, profile_id: str, version: int, *, connection=None) -> dict[str, Any] | None:
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise VerificationProfileError("profile_id must be a non-empty string")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise VerificationProfileError("profile version must be a positive integer")
        if connection is None:
            with self.db.connect() as conn:
                return self.get(profile_id, version, connection=conn)
        row = connection.execute(
            "SELECT profile_json,profile_digest,created_at FROM rocksoul_verification_profiles WHERE profile_id=? AND version=?",
            (profile_id.lower(), version),
        ).fetchone()
        if row is None:
            return None
        return {"profile": json.loads(row["profile_json"]), "digest": row["profile_digest"], "created_at": row["created_at"]}

    def resolve(self, profile_id: str, version: int) -> VerificationProfile:
        record = self.get(profile_id, version)
        if record is None:
            raise VerificationProfileError("unknown verification profile or version mismatch")
        profile = VerificationProfile.from_dict(record["profile"])
        if profile.digest != record["digest"]:
            raise VerificationProfileError("stored verification profile digest mismatch")
        return profile

    def list(self, limit: int = 100) -> dict[str, Any]:
        limit = max(1, min(int(limit), 500))
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT profile_id,version,profile_json,profile_digest,created_at FROM rocksoul_verification_profiles ORDER BY profile_id,version DESC LIMIT ?",
                (limit,),
            ).fetchall()
            total = int(conn.execute("SELECT COUNT(*) FROM rocksoul_verification_profiles").fetchone()[0])
        items = [{"profile": json.loads(row["profile_json"]), "digest": row["profile_digest"], "created_at": row["created_at"]} for row in rows]
        return {"items": items, "total": total}

    def registry(self) -> VerificationProfileRegistry:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT profile_json FROM rocksoul_verification_profiles ORDER BY profile_id,version").fetchall()
        profiles = tuple(VerificationProfile.from_dict(json.loads(row["profile_json"])) for row in rows)
        return VerificationProfileRegistry(profiles)
