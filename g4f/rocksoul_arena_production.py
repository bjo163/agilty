from __future__ import annotations

"""Production benchmark contract for ROCKSOUL F5 Arena.

This module deliberately sits on top of the deterministic Arena foundation. It
adds the evidence required before benchmark results may be treated as
production-authoritative: dataset provenance, evaluator revision, split and
contamination policy, exact target identity, execution-environment evidence,
and bounded repeat-run variance.
"""

import json
import math
import re
import statistics
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping

from .rocksoul_arena import (
    ArenaCase,
    ArenaRun,
    ArenaStore,
    ArenaSuite,
    ArenaValidationError,
    canonical_json,
    digest_value,
)

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_ALLOWED_SPLIT_POLICIES = {
    "public_only",
    "public_and_held_out",
    "held_out_only",
    "not_applicable",
}
_ALLOWED_NETWORK_MODES = {"offline", "restricted", "online"}


@dataclass(frozen=True, slots=True)
class ArenaDatasetProvenance:
    source: str
    revision: str
    sha256: str
    split_policy: str
    contamination_review: str
    license: str | None = None

    def manifest(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ArenaRepeatPolicy:
    runs: int = 3
    max_score_stddev: float = 5.0

    def manifest(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ArenaProductionPack:
    name: str
    version: str
    suite: ArenaSuite
    dataset: ArenaDatasetProvenance
    evaluator_revision: str
    repeat_policy: ArenaRepeatPolicy = field(default_factory=ArenaRepeatPolicy)
    environment_requirements: Mapping[str, Any] = field(default_factory=dict)
    network_requirements: Mapping[str, Any] = field(default_factory=dict)

    def manifest(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "suite_digest": self.suite.digest,
            "suite_name": self.suite.name,
            "suite_version": self.suite.version,
            "dataset": self.dataset.manifest(),
            "evaluator": self.suite.evaluator,
            "evaluator_revision": self.evaluator_revision,
            "repeat_policy": self.repeat_policy.manifest(),
            "environment_requirements": dict(self.environment_requirements),
            "network_requirements": dict(self.network_requirements),
        }

    @property
    def digest(self) -> str:
        return digest_value(self.manifest())


@dataclass(frozen=True, slots=True)
class ArenaTargetIdentity:
    provider: str
    model: str
    revision: str
    runtime_revision: str

    def manifest(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def digest(self) -> str:
        return digest_value(self.manifest())


@dataclass(frozen=True, slots=True)
class ArenaEnvironmentEvidence:
    runtime: str
    os: str
    python: str
    network_mode: str
    region: str = "unspecified"
    extra: Mapping[str, Any] = field(default_factory=dict)

    def manifest(self) -> dict[str, Any]:
        value = asdict(self)
        value["extra"] = dict(self.extra)
        return value


@dataclass(frozen=True, slots=True)
class ArenaCampaign:
    campaign_id: str
    pack_digest: str
    target_digest: str
    target: Mapping[str, Any]
    environment: Mapping[str, Any]
    run_ids: tuple[str, ...]
    scores: tuple[float, ...]
    score_mean: float
    score_stddev: float
    variance_accepted: bool
    started_at: float
    finished_at: float


ARENA_PRODUCTION_SCHEMA = """
CREATE TABLE IF NOT EXISTS arena_production_packs (
 digest TEXT PRIMARY KEY,
 name TEXT NOT NULL,
 version TEXT NOT NULL,
 suite_digest TEXT NOT NULL,
 manifest_json TEXT NOT NULL,
 created_at REAL NOT NULL,
 UNIQUE(name, version)
);
CREATE TABLE IF NOT EXISTS arena_campaigns (
 id TEXT PRIMARY KEY,
 pack_digest TEXT NOT NULL,
 target_digest TEXT NOT NULL,
 target_json TEXT NOT NULL,
 environment_json TEXT NOT NULL,
 run_ids_json TEXT NOT NULL,
 scores_json TEXT NOT NULL,
 score_mean REAL NOT NULL,
 score_stddev REAL NOT NULL,
 variance_accepted INTEGER NOT NULL,
 started_at REAL NOT NULL,
 finished_at REAL NOT NULL,
 FOREIGN KEY(pack_digest) REFERENCES arena_production_packs(digest) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_arena_campaign_pack_time
 ON arena_campaigns(pack_digest, finished_at DESC);
CREATE INDEX IF NOT EXISTS idx_arena_campaign_target_time
 ON arena_campaigns(target_digest, finished_at DESC);
"""


class ArenaProductionStore:
    def __init__(self, arena: ArenaStore) -> None:
        self.arena = arena
        with self.arena.db.connect() as conn:
            conn.executescript(ARENA_PRODUCTION_SCHEMA)

    def validate_pack(self, pack: ArenaProductionPack) -> None:
        if not isinstance(pack, ArenaProductionPack):
            raise ArenaValidationError("pack must be an ArenaProductionPack")
        if not isinstance(pack.suite, ArenaSuite):
            raise ArenaValidationError("suite must be ArenaSuite")
        self.arena.validate_suite(pack.suite)
        if not all(isinstance(value, str) for value in (pack.name, pack.version, pack.evaluator_revision)):
            raise ArenaValidationError("pack name, version, and evaluator_revision must be strings")
        if not isinstance(pack.dataset, ArenaDatasetProvenance):
            raise ArenaValidationError("dataset must be ArenaDatasetProvenance")
        if not isinstance(pack.repeat_policy, ArenaRepeatPolicy):
            raise ArenaValidationError("repeat_policy must be ArenaRepeatPolicy")
        if not isinstance(pack.environment_requirements, Mapping) or not pack.environment_requirements:
            raise ArenaValidationError("environment_requirements must be a non-empty object")
        if not isinstance(pack.network_requirements, Mapping) or not pack.network_requirements:
            raise ArenaValidationError("network_requirements must be a non-empty object")
        try:
            json.dumps(dict(pack.environment_requirements), allow_nan=False)
            json.dumps(dict(pack.network_requirements), allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ArenaValidationError(f"production requirements must contain only finite JSON values: {exc}") from exc
        if not pack.name.strip():
            raise ArenaValidationError("production pack name must not be empty")
        if not pack.version.strip():
            raise ArenaValidationError("production pack version must not be empty")
        if not pack.evaluator_revision.strip():
            raise ArenaValidationError("evaluator_revision must not be empty")

        dataset = pack.dataset
        if not all(isinstance(value, str) for value in (dataset.source, dataset.revision, dataset.sha256, dataset.split_policy, dataset.contamination_review)):
            raise ArenaValidationError("dataset provenance fields must be strings")
        if dataset.license is not None and not isinstance(dataset.license, str):
            raise ArenaValidationError("dataset license must be a string when supplied")
        if not dataset.source.strip():
            raise ArenaValidationError("dataset source must not be empty")
        if not dataset.revision.strip():
            raise ArenaValidationError("dataset revision must not be empty")
        if not _SHA256_RE.fullmatch(dataset.sha256.strip()):
            raise ArenaValidationError("dataset sha256 must be exactly 64 hexadecimal characters")
        if dataset.split_policy not in _ALLOWED_SPLIT_POLICIES:
            raise ArenaValidationError(f"unsupported split_policy: {dataset.split_policy}")
        if not dataset.contamination_review.strip():
            raise ArenaValidationError("contamination_review must not be empty")

        repeat = pack.repeat_policy
        if type(repeat.runs) is not int or repeat.runs < 2 or repeat.runs > 100:
            raise ArenaValidationError("repeat_policy.runs must be an integer between 2 and 100")
        try:
            max_score_stddev = float(repeat.max_score_stddev)
        except (TypeError, ValueError, OverflowError):
            max_score_stddev = math.nan
        if (
            isinstance(repeat.max_score_stddev, bool)
            or not isinstance(repeat.max_score_stddev, (int, float))
            or not math.isfinite(max_score_stddev)
            or max_score_stddev < 0
        ):
            raise ArenaValidationError("repeat_policy.max_score_stddev must be a finite non-negative number")
        if not pack.environment_requirements:
            raise ArenaValidationError("environment_requirements must be explicit for a production pack")
        if not pack.network_requirements:
            raise ArenaValidationError("network_requirements must be explicit for a production pack")

    @staticmethod
    def validate_target(target: ArenaTargetIdentity) -> None:
        if not isinstance(target, ArenaTargetIdentity):
            raise ArenaValidationError("target must be ArenaTargetIdentity")
        for field_name, value in target.manifest().items():
            if not isinstance(value, str) or not value.strip():
                raise ArenaValidationError(f"target {field_name} must be a non-empty string")

    @staticmethod
    def validate_environment(environment: ArenaEnvironmentEvidence) -> None:
        if not isinstance(environment, ArenaEnvironmentEvidence):
            raise ArenaValidationError("environment must be ArenaEnvironmentEvidence")
        for field_name, value in (("runtime", environment.runtime), ("os", environment.os), ("python", environment.python)):
            if not isinstance(value, str) or not value.strip():
                raise ArenaValidationError(f"environment {field_name} must be a non-empty string")
        if not isinstance(environment.region, str) or not isinstance(environment.extra, Mapping):
            raise ArenaValidationError("environment region must be a string and extra must be an object")
        try:
            json.dumps(dict(environment.extra), allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ArenaValidationError(f"environment extra must contain only finite JSON values: {exc}") from exc
        if not isinstance(environment.network_mode, str) or environment.network_mode not in _ALLOWED_NETWORK_MODES:
            raise ArenaValidationError(f"unsupported network_mode: {environment.network_mode}")

    def register_pack(self, pack: ArenaProductionPack, *, now: float | None = None) -> str:
        self.validate_pack(pack)
        suite_digest = self.arena.register_suite(pack.suite, now=now)
        digest = pack.digest
        manifest_json = canonical_json(pack.manifest())
        created_at = time.time() if now is None else float(now)
        with self.arena.db.connect() as conn:
            existing = conn.execute(
                "SELECT digest FROM arena_production_packs WHERE name=? AND version=?",
                (pack.name, pack.version),
            ).fetchone()
            if existing is not None and str(existing["digest"]) != digest:
                raise ArenaValidationError(
                    f"production pack {pack.name!r} version {pack.version!r} already exists with different content; bump the version"
                )
            conn.execute(
                """
                INSERT INTO arena_production_packs(digest,name,version,suite_digest,manifest_json,created_at)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(digest) DO NOTHING
                """,
                (digest, pack.name, pack.version, suite_digest, manifest_json, created_at),
            )
        return digest

    def run_campaign(
        self,
        pack: ArenaProductionPack,
        target: ArenaTargetIdentity,
        environment: ArenaEnvironmentEvidence,
        executor: Callable[[ArenaCase], Any],
        *,
        now: Callable[[], float] = time.time,
    ) -> ArenaCampaign:
        self.validate_pack(pack)
        self.validate_target(target)
        self.validate_environment(environment)
        pack_digest = self.register_pack(pack, now=now())
        target_digest = target.digest
        campaign_id = uuid.uuid4().hex
        started_at = now()
        runs: list[ArenaRun] = []

        for repeat_index in range(pack.repeat_policy.runs):
            metadata = {
                "production_benchmark": True,
                "pack_digest": pack_digest,
                "pack_name": pack.name,
                "pack_version": pack.version,
                "dataset": pack.dataset.manifest(),
                "evaluator_revision": pack.evaluator_revision,
                "target_identity": target.manifest(),
                "target_digest": target_digest,
                "environment": environment.manifest(),
                "repeat_index": repeat_index + 1,
                "repeat_count": pack.repeat_policy.runs,
            }
            runs.append(
                self.arena.run(
                    pack.suite,
                    target=f"{target.provider}:{target.model}@{target.revision}",
                    executor=executor,
                    metadata=metadata,
                )
            )

        scores = tuple(float(run.score) for run in runs)
        mean = statistics.fmean(scores)
        stddev = statistics.pstdev(scores)
        variance_accepted = stddev <= pack.repeat_policy.max_score_stddev
        finished_at = now()
        campaign = ArenaCampaign(
            campaign_id=campaign_id,
            pack_digest=pack_digest,
            target_digest=target_digest,
            target=target.manifest(),
            environment=environment.manifest(),
            run_ids=tuple(run.run_id for run in runs),
            scores=scores,
            score_mean=mean,
            score_stddev=stddev,
            variance_accepted=variance_accepted,
            started_at=started_at,
            finished_at=finished_at,
        )
        self._persist_campaign(campaign)
        return campaign

    def _persist_campaign(self, campaign: ArenaCampaign) -> None:
        with self.arena.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO arena_campaigns(
                    id,pack_digest,target_digest,target_json,environment_json,
                    run_ids_json,scores_json,score_mean,score_stddev,
                    variance_accepted,started_at,finished_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    campaign.campaign_id,
                    campaign.pack_digest,
                    campaign.target_digest,
                    canonical_json(dict(campaign.target)),
                    canonical_json(dict(campaign.environment)),
                    canonical_json(list(campaign.run_ids)),
                    canonical_json(list(campaign.scores)),
                    campaign.score_mean,
                    campaign.score_stddev,
                    int(campaign.variance_accepted),
                    campaign.started_at,
                    campaign.finished_at,
                ),
            )

    def get_campaign(self, campaign_id: str) -> dict[str, Any] | None:
        with self.arena.db.connect() as conn:
            row = conn.execute("SELECT * FROM arena_campaigns WHERE id=?", (campaign_id,)).fetchone()
        if row is None:
            return None
        value = dict(row)
        value["target"] = json.loads(value.pop("target_json"))
        value["environment"] = json.loads(value.pop("environment_json"))
        value["run_ids"] = json.loads(value.pop("run_ids_json"))
        value["scores"] = json.loads(value.pop("scores_json"))
        value["variance_accepted"] = bool(value["variance_accepted"])
        return value


    @staticmethod
    def _audit_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    def verify_campaign(self, campaign_id: str) -> dict[str, Any] | None:
        """Reconcile a persisted campaign against its immutable pack and every Arena run."""
        campaign = self.get_campaign(campaign_id)
        if campaign is None:
            return None

        checks: list[dict[str, Any]] = []
        errors: list[str] = []
        pack_row = None
        with self.arena.db.connect() as conn:
            pack_row = conn.execute(
                "SELECT * FROM arena_production_packs WHERE digest=?",
                (campaign["pack_digest"],),
            ).fetchone()
        if pack_row is None:
            self._audit_check(checks, "registered_pack_exists", False, "campaign pack digest is not registered")
            pack_manifest: dict[str, Any] = {}
        else:
            pack_row = dict(pack_row)
            try:
                pack_manifest = json.loads(pack_row["manifest_json"])
                self._audit_check(
                    checks,
                    "pack_manifest_digest",
                    digest_value(pack_manifest) == campaign["pack_digest"],
                    "stored pack manifest must reproduce its content digest",
                )
                self._audit_check(
                    checks,
                    "pack_suite_digest",
                    pack_row["suite_digest"] == pack_manifest.get("suite_digest"),
                    "registered suite digest must match the immutable pack manifest",
                )
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                pack_manifest = {}
                self._audit_check(checks, "pack_manifest_digest", False, f"pack manifest cannot be decoded: {exc}")

        target = campaign.get("target")
        environment = campaign.get("environment")
        target_valid = isinstance(target, dict) and all(
            isinstance(target.get(key), str) and target[key].strip()
            for key in ("provider", "model", "revision", "runtime_revision")
        )
        computed_target_digest = digest_value(target) if isinstance(target, dict) else ""
        self._audit_check(
            checks,
            "target_identity_digest",
            target_valid and computed_target_digest == campaign["target_digest"],
            "target identity fields and content digest must agree",
        )
        environment_valid = (
            isinstance(environment, dict)
            and all(isinstance(environment.get(key), str) and environment[key].strip()
                    for key in ("runtime", "os", "python", "network_mode", "region"))
            and environment.get("network_mode") in _ALLOWED_NETWORK_MODES
            and isinstance(environment.get("extra", {}), dict)
        )
        self._audit_check(
            checks,
            "environment_evidence",
            environment_valid,
            "campaign environment must contain the required typed evidence fields",
        )

        try:
            run_ids = campaign["run_ids"]
            scores = campaign["scores"]
            policy = pack_manifest.get("repeat_policy", {})
            expected_runs = policy.get("runs")
            cases = pack_manifest.get("suite", {}).get("cases", [])
            pack_digest = campaign["pack_digest"]
            expected_target = target
            expected_environment = environment
            pack_name = pack_manifest.get("name")
            pack_version = pack_manifest.get("version")
            expected_dataset = pack_manifest.get("dataset")
            evaluator_revision = pack_manifest.get("evaluator_revision")
            suite_digest = pack_manifest.get("suite_digest")
            valid_shape = (
                isinstance(run_ids, list)
                and isinstance(scores, list)
                and type(expected_runs) is int
                and len(run_ids) == expected_runs
                and len(scores) == expected_runs
                and len(set(run_ids)) == len(run_ids)
                and bool(cases)
            )
            self._audit_check(
                checks,
                "repeat_count_and_identity",
                valid_shape,
                "campaign must contain the declared number of unique run IDs and scores",
            )
        except (TypeError, ValueError, AttributeError):
            run_ids, scores, cases = [], [], []
            valid_shape = False
            self._audit_check(checks, "repeat_count_and_identity", False, "campaign repeat evidence has an invalid shape")

        run_scores: list[float] = []
        run_ids = run_ids if isinstance(run_ids, list) else []
        scores = scores if isinstance(scores, list) else []
        expected_cases = {
            str(item.get("case_id")): item
            for item in cases
            if isinstance(item, dict) and isinstance(item.get("case_id"), str)
        }
        for index, run_id in enumerate(run_ids):
            run = self.arena.get_run(str(run_id))
            if run is None:
                self._audit_check(checks, f"run_{index + 1}_exists", False, f"Arena run {run_id!r} is missing")
                continue

            run_metadata = run.get("metadata", {})
            expected_run_target = (
                f"{target.get('provider')}:{target.get('model')}@{target.get('revision')}"
                if isinstance(target, dict) else ""
            )
            metadata_ok = (
                run_metadata.get("production_benchmark") is True
                and run_metadata.get("pack_digest") == pack_digest
                and run_metadata.get("pack_name") == pack_name
                and run_metadata.get("pack_version") == pack_version
                and run_metadata.get("dataset") == expected_dataset
                and run_metadata.get("evaluator_revision") == evaluator_revision
                and run_metadata.get("target_identity") == expected_target
                and run_metadata.get("target_digest") == campaign["target_digest"]
                and run_metadata.get("environment") == expected_environment
                and run_metadata.get("repeat_index") == index + 1
                and run_metadata.get("repeat_count") == expected_runs
            )
            self._audit_check(
                checks,
                f"run_{index + 1}_metadata",
                metadata_ok,
                "run metadata must bind to this pack, target, environment, evaluator, and repeat index",
            )
            self._audit_check(
                checks,
                f"run_{index + 1}_suite_target",
                run.get("suite_digest") == suite_digest and run.get("target") == expected_run_target,
                "Arena run suite and provider/model target must match the campaign",
            )

            results = run.get("results", [])
            result_ids = [item.get("case_id") for item in results if isinstance(item, dict)]
            results_shape_ok = (
                len(results) == len(expected_cases)
                and len(result_ids) == len(results)
                and set(result_ids) == set(expected_cases)
                and len(set(result_ids)) == len(result_ids)
            )
            result_weights_ok = True
            result_values_ok = True
            weighted_total = 0.0
            weight_total = 0.0
            passed = 0
            for item in results:
                if not isinstance(item, dict):
                    result_values_ok = False
                    continue
                case_spec = expected_cases.get(str(item.get("case_id")), {})
                try:
                    score = float(item.get("score"))
                    weight = float(item.get("weight"))
                    latency = float(item.get("latency_ms"))
                except (TypeError, ValueError, OverflowError):
                    result_values_ok = False
                    continue
                if (
                    isinstance(item.get("score"), bool)
                    or not math.isfinite(score)
                    or score < 0.0 or score > 1.0
                    or isinstance(item.get("weight"), bool)
                    or not math.isfinite(weight) or weight <= 0.0
                    or not math.isfinite(latency) or latency < 0.0
                    or not isinstance(item.get("ok"), bool)
                    or not math.isclose(score, 1.0 if item.get("ok") else 0.0, rel_tol=0.0, abs_tol=1e-12)
                    or (item.get("output_digest") is not None and not _SHA256_RE.fullmatch(str(item.get("output_digest"))))
                ):
                    result_values_ok = False
                try:
                    expected_weight = float(case_spec.get("weight", 1.0))
                except (TypeError, ValueError, OverflowError):
                    expected_weight = math.nan
                if not math.isclose(weight, expected_weight, rel_tol=1e-12, abs_tol=1e-12):
                    result_weights_ok = False
                weighted_total += score * weight
                weight_total += weight
                passed += int(item.get("ok") is True)

            derived_score = 100.0 * weighted_total / weight_total if weight_total > 0.0 else 0.0
            try:
                stored_score = float(run.get("score"))
                run_total = int(run.get("total"))
                run_passed = int(run.get("passed"))
                run_failed = int(run.get("failed"))
            except (TypeError, ValueError, OverflowError):
                stored_score, run_total, run_passed, run_failed = math.nan, -1, -1, -1
            aggregates_ok = (
                math.isfinite(stored_score)
                and 0.0 <= stored_score <= 100.0
                and math.isclose(stored_score, derived_score, rel_tol=1e-9, abs_tol=1e-8)
                and run_total == len(results) == len(expected_cases)
                and run_passed == passed
                and run_failed == run_total - passed
            )
            self._audit_check(
                checks,
                f"run_{index + 1}_case_results",
                results_shape_ok and result_weights_ok and result_values_ok and aggregates_ok,
                "case IDs, weights, result values, pass counts, and weighted run score must reconcile",
            )
            if math.isfinite(stored_score):
                run_scores.append(stored_score)

            try:
                run_started = float(run["started_at"])
                run_finished = float(run["finished_at"])
                campaign_started = float(campaign["started_at"])
                campaign_finished = float(campaign["finished_at"])
                timestamps_ok = (
                    all(math.isfinite(value) for value in (run_started, run_finished, campaign_started, campaign_finished))
                    and run_started <= run_finished
                    and campaign_started <= run_started
                    and run_finished <= campaign_finished
                )
            except (KeyError, TypeError, ValueError, OverflowError):
                timestamps_ok = False
            self._audit_check(
                checks,
                f"run_{index + 1}_timestamps",
                timestamps_ok,
                "run timestamps must be finite and contained within the campaign time window",
            )

        try:
            normalized_scores = [float(score) for score in scores]
            scores_finite = len(run_scores) == len(run_ids) and all(
                math.isfinite(score) and 0.0 <= score <= 100.0 for score in normalized_scores
            )
            scores_match_runs = (
                len(normalized_scores) == len(run_scores)
                and all(
                    math.isclose(normalized_scores[index], run_scores[index], rel_tol=1e-9, abs_tol=1e-8)
                    for index in range(len(run_scores))
                )
            )
        except (TypeError, ValueError, OverflowError):
            scores_finite = False
            scores_match_runs = False
        self._audit_check(
            checks,
            "campaign_scores_match_runs",
            scores_finite and scores_match_runs,
            "campaign score list must exactly reconcile with its persisted Arena runs",
        )

        try:
            score_mean = statistics.fmean(float(score) for score in scores)
            score_stddev = statistics.pstdev(float(score) for score in scores)
            expected_variance = score_stddev <= float(pack_manifest["repeat_policy"]["max_score_stddev"])
            summary_ok = (
                math.isclose(score_mean, float(campaign["score_mean"]), rel_tol=1e-9, abs_tol=1e-8)
                and math.isclose(score_stddev, float(campaign["score_stddev"]), rel_tol=1e-9, abs_tol=1e-8)
                and expected_variance is bool(campaign["variance_accepted"])
                and len(scores) == pack_manifest["repeat_policy"]["runs"]
            )
        except (KeyError, TypeError, ValueError, OverflowError, statistics.StatisticsError):
            score_mean, score_stddev, expected_variance, summary_ok = math.nan, math.nan, False, False
        self._audit_check(
            checks,
            "campaign_statistics",
            summary_ok,
            "mean, population standard deviation, and variance decision must be reproducible",
        )

        verified = bool(checks) and all(item["ok"] for item in checks)
        errors = [item["name"] for item in checks if not item["ok"]]
        return {
            "campaign_id": campaign_id,
            "integrity_status": "VERIFIED" if verified else "REJECTED",
            "integrity_verified": verified,
            "variance_accepted": bool(campaign["variance_accepted"]),
            "pack_digest": campaign["pack_digest"],
            "target_digest": campaign["target_digest"],
            "run_count": len(run_ids),
            "checks": checks,
            "failed_checks": errors,
            "quality_certification": "NOT_CERTIFIED",
        }

    def campaign_report(
        self,
        pack_digest: str,
        target_digest: str | None = None,
        *,
        limit: int = 1000,
    ) -> dict[str, Any]:
        """Build a deterministic integrity/stability report without making quality claims."""
        if not self.has_pack(pack_digest):
            return {
                "report_status": "NO_PACK",
                "pack_digest": pack_digest,
                "campaign_count": 0,
                "campaigns": [],
                "quality_certification": "NOT_CERTIFIED",
            }
        campaigns = self.list_campaigns(pack_digest, limit=limit)
        if target_digest:
            campaigns = [item for item in campaigns if item["target_digest"] == target_digest]
        audits = [self.verify_campaign(item["id"]) for item in campaigns]
        audits = [item for item in audits if item is not None]
        by_target: dict[str, list[dict[str, Any]]] = {}
        for item in campaigns:
            by_target.setdefault(str(item["target_digest"]), []).append(item)
        target_summaries = []
        for digest, items in sorted(by_target.items()):
            means = [float(item["score_mean"]) for item in items]
            target_summaries.append({
                "target_digest": digest,
                "campaign_count": len(items),
                "mean_score_across_campaigns": statistics.fmean(means) if means else 0.0,
                "min_campaign_score": min(means) if means else 0.0,
                "max_campaign_score": max(means) if means else 0.0,
                "variance_accepted_campaigns": sum(bool(item["variance_accepted"]) for item in items),
                "integrity_verified_campaigns": sum(
                    1 for audit in audits if audit["target_digest"] == digest and audit["integrity_verified"]
                ),
            })
        audits_by_id = {item["campaign_id"]: item for item in audits}
        all_verified = bool(audits) and len(audits) == len(campaigns) and all(
            item["integrity_verified"] for item in audits
        )
        all_stable = bool(campaigns) and all(bool(item["variance_accepted"]) for item in campaigns)
        report = {
            "report_status": (
                "EVIDENCE_VERIFIED" if all_verified
                else "EVIDENCE_REJECTED" if campaigns
                else "NO_EVIDENCE"
            ),
            "pack_digest": pack_digest,
            "target_filter": target_digest,
            "campaign_count": len(campaigns),
            "integrity_verified_campaigns": sum(1 for item in audits if item["integrity_verified"]),
            "integrity_rejected_campaigns": sum(1 for item in audits if not item["integrity_verified"]),
            "variance_accepted_campaigns": sum(1 for item in campaigns if item["variance_accepted"]),
            "all_campaigns_stable": all_stable,
            "targets": target_summaries,
            "campaigns": [
                {
                    "campaign_id": item["id"],
                    "target_digest": item["target_digest"],
                    "score_mean": item["score_mean"],
                    "score_stddev": item["score_stddev"],
                    "variance_accepted": bool(item["variance_accepted"]),
                    "integrity_status": audits_by_id.get(item["id"], {}).get("integrity_status", "MISSING"),
                }
                for item in campaigns
            ],
            "quality_certification": "NOT_CERTIFIED",
            "claim_boundary": "Integrity verification is not an independent dataset audit or a model-quality certification.",
        }
        report["report_digest"] = digest_value(report)
        return report

    def has_pack(self, pack_digest: str) -> bool:
        """Check immutable pack registration by its primary-key digest."""
        if not isinstance(pack_digest, str) or not _SHA256_RE.fullmatch(pack_digest):
            return False
        with self.arena.db.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM arena_production_packs WHERE digest=?",
                (pack_digest,),
            ).fetchone()
        return row is not None

    def list_packs(self, *, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        with self.arena.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM arena_production_packs ORDER BY created_at DESC, digest DESC LIMIT ?",
                (limit,),
            ).fetchall()
        values: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["manifest"] = json.loads(item.pop("manifest_json"))
            values.append(item)
        return values

    def list_campaigns(
        self, pack_digest: str | None = None, *, limit: int = 100
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        query = "SELECT * FROM arena_campaigns"
        params: list[Any] = []
        if pack_digest:
            query += " WHERE pack_digest=?"
            params.append(pack_digest)
        query += " ORDER BY finished_at DESC, id DESC LIMIT ?"
        params.append(limit)
        with self.arena.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        values: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["target"] = json.loads(item.pop("target_json"))
            item["environment"] = json.loads(item.pop("environment_json"))
            item["run_ids"] = json.loads(item.pop("run_ids_json"))
            item["scores"] = json.loads(item.pop("scores_json"))
            item["variance_accepted"] = bool(item["variance_accepted"])
            values.append(item)
        return values

    def status(self) -> dict[str, Any]:
        with self.arena.db.connect() as conn:
            packs = int(conn.execute("SELECT COUNT(*) FROM arena_production_packs").fetchone()[0])
            campaigns = int(conn.execute("SELECT COUNT(*) FROM arena_campaigns").fetchone()[0])
        return {
            "phase": "F5",
            "authority": "rocksoul_arena_production",
            "state": "production-contract",
            "packs": packs,
            "campaigns": campaigns,
            "required_evidence": [
                "dataset_provenance",
                "evaluator_revision",
                "split_policy",
                "contamination_review",
                "repeat_variance",
                "environment",
                "network",
                "exact_target_identity",
            ],
        }


def campaign_to_dict(campaign: ArenaCampaign) -> dict[str, Any]:
    value = asdict(campaign)
    value["run_ids"] = list(campaign.run_ids)
    value["scores"] = list(campaign.scores)
    value["target"] = dict(campaign.target)
    value["environment"] = dict(campaign.environment)
    return value
