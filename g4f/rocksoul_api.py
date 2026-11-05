"""Authenticated HTTP product API for the ROCKSOUL control plane.

This adapter composes existing stores, routing and execution services. It does
not implement or own provider adapters.
"""
import base64
import binascii
import hmac
import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from .rocksoul_control import ProviderControlStore
from .rocksoul_mesh import MeshStore, MeshError
from .rocksoul_arena import ArenaStore
from .rocksoul_arena_production import ArenaProductionStore
from .rocksoul_db import RocksoulDB
from .rocksoul_execution import ExecutionEngine, ExecutionRequest
from .rocksoul_execution_store import ExecutionTraceStore
from .rocksoul_intelligence import CapabilityRequirement, ExplainableRouter
from .rocksoul_contracts import ContractValidationError, WorkItem, WorkStatus
from .rocksoul_work_store import WorkItemStore, WorkItemStoreError
from .rocksoul_work_graph import WorkGraph, WorkGraphValidationError
from .rocksoul_work_graph_store import WorkGraphStore, WorkGraphStoreError
from .rocksoul_verification import VerificationProfile, VerificationProfileError
from .rocksoul_verification_store import VerificationProfileStore
from .rocksoul_verifier_engine import VerificationEngine


def _safe_response(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _safe_response(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_response(item) for item in value]
    content = getattr(value, "content", None)
    if content is not None:
        return {"content": _safe_response(content)}
    return str(value)


def create_app(db: RocksoulDB | None = None):
    try:
        from fastapi import FastAPI, Header, HTTPException
        from pydantic import BaseModel, ConfigDict, Field, model_validator
    except ImportError as exc:
        raise RuntimeError("ROCKSOUL HTTP API requires the 'rocksoul-api' extra") from exc

    database = db or RocksoulDB()
    traces = ExecutionTraceStore(database)
    work_items = WorkItemStore(database)
    work_graphs = WorkGraphStore(database)
    verification_profiles = VerificationProfileStore(database)
    app = FastAPI(
        title="ROCKSOUL API",
        version="1.0.0",
        description="Product API for routing intelligence, execution and evidence.",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    app.state.rocksoul_db = database

    class ExecuteBody(BaseModel):
        model_config = ConfigDict(extra="forbid")
        model: str = Field(min_length=1, max_length=200)
        messages: list[dict[str, Any]] = Field(min_length=1, max_length=100)
        requirements: list[str] = Field(default_factory=list, max_length=8)
        providers: list[str] = Field(default_factory=list, max_length=50)
        max_attempts: int = Field(default=3, ge=1, le=10)
        max_same_provider_attempts: int = Field(default=1, ge=1, le=3)
        max_total_time: float = Field(default=90.0, gt=0, le=300)
        timeout: float = Field(default=30.0, gt=0, le=120)
        stream: bool = False
        work_id: str | None = Field(default=None, min_length=1, max_length=128)

        @model_validator(mode="after")
        def enforce_payload_budget(self):
            encoded = json.dumps(self.messages, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if len(encoded) > 1_000_000:
                raise ValueError("messages payload must not exceed 1 MiB")
            return self

    def require_operator(api_key: str | None):
        expected = os.environ.get("ROCKSOUL_API_KEY", "")
        if not expected:
            raise HTTPException(status_code=503, detail="ROCKSOUL_API_KEY is not configured")
        if not api_key or not hmac.compare_digest(api_key, expected):
            raise HTTPException(status_code=401, detail="Invalid or missing ROCKSOUL API key")

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "service": "rocksoul-api", "api_version": "1.0.0"}

    @app.get("/api/v1/status")
    def status():
        with database.connect() as conn:
            providers_count = int(conn.execute("SELECT COUNT(*) FROM providers").fetchone()[0])
            models_count = int(conn.execute("SELECT COUNT(*) FROM models").fetchone()[0])
            runs_count = int(conn.execute("SELECT COUNT(*) FROM execution_runs").fetchone()[0])
        return {
            "service": "rocksoul", "status": "operational",
            "providers": providers_count, "models": models_count,
            "execution_runs": runs_count,
        }

    @app.get("/api/v1/providers")
    def providers():
        control = ProviderControlStore(database)
        with database.connect() as conn:
            names = [str(row["name"]) for row in conn.execute("SELECT name FROM providers ORDER BY name")]
        items = []
        for name in names:
            health = database.health(name)
            state = control.get(name)
            items.append({
                "name": name, "state": state.state, "control_reason": state.reason,
                "attempts": health.attempts, "success_rate": round(health.success_rate, 4),
                "score": round(health.score, 2), "avg_latency_ms": health.avg_latency_ms,
                "cooldown_until": state.state_until,
            })
        return {"items": items, "total": len(items)}

    @app.get("/api/v1/routes/{model}/explain")
    def explain_route(model: str, requirements: str = "", providers_filter: str = ""):
        required = [CapabilityRequirement(item.strip()) for item in requirements.split(",") if item.strip()]
        allowed = [item.strip() for item in providers_filter.split(",") if item.strip()] or None
        supported = {"streaming", "tools", "structured_output", "vision", "image"}
        if any(item.name not in supported for item in required):
            raise HTTPException(status_code=422, detail="Unsupported capability requirement")
        return {
            "model": model,
            "requirements": [item.name for item in required],
            "candidates": ExplainableRouter(database).explain(model, required, allowed),
        }


    @app.get("/api/v1/verification-profiles")
    def list_verification_profiles(limit: int = 100, x_rocksoul_api_key: str | None = Header(default=None)):
        require_operator(x_rocksoul_api_key)
        return verification_profiles.list(limit=limit)

    @app.post("/api/v1/verification-profiles")
    def register_verification_profile(body: dict[str, Any], x_rocksoul_api_key: str | None = Header(default=None)):
        require_operator(x_rocksoul_api_key)
        try:
            profile = VerificationProfile.from_dict(body)
            return verification_profiles.register(profile)
        except VerificationProfileError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v1/verification-profiles/{profile_id}/{version}")
    def get_verification_profile(profile_id: str, version: int, x_rocksoul_api_key: str | None = Header(default=None)):
        require_operator(x_rocksoul_api_key)
        result = verification_profiles.get(profile_id, version)
        if result is None:
            raise HTTPException(status_code=404, detail="Verification profile not found")
        return result

    @app.get("/api/v1/work-graphs")
    def list_work_graphs(limit: int = 50, offset: int = 0, x_rocksoul_api_key: str | None = Header(default=None)):
        require_operator(x_rocksoul_api_key)
        try:
            return work_graphs.list(limit=limit, offset=offset)
        except WorkGraphStoreError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/work-graphs")
    def create_work_graph(body: dict[str, Any], x_rocksoul_api_key: str | None = Header(default=None)):
        require_operator(x_rocksoul_api_key)
        try:
            graph = WorkGraph.from_dict(body)
            return work_graphs.create(graph)
        except WorkGraphValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except WorkGraphStoreError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/work-graphs/{graph_id}")
    def get_work_graph(graph_id: str, x_rocksoul_api_key: str | None = Header(default=None)):
        require_operator(x_rocksoul_api_key)
        try:
            return work_graphs.get(graph_id)
        except WorkGraphStoreError as exc:
            raise HTTPException(status_code=404, detail="WorkGraph not found") from exc

    @app.get("/api/v1/work-graphs/{graph_id}/verify-chain")
    def verify_work_graph_chain(graph_id: str, x_rocksoul_api_key: str | None = Header(default=None)):
        require_operator(x_rocksoul_api_key)
        return work_graphs.verify_event_chain(graph_id)

    @app.get("/api/v1/work-graphs/{graph_id}/readiness")
    def resolve_work_graph_readiness(graph_id: str, x_rocksoul_api_key: str | None = Header(default=None)):
        require_operator(x_rocksoul_api_key)
        try:
            return work_graphs.resolve_readiness(graph_id, work_items)
        except WorkGraphStoreError as exc:
            code = 404 if str(exc) == "WorkGraph not found" else 409
            raise HTTPException(status_code=code, detail=str(exc)) from exc

    @app.get("/api/v1/work-items")
    def list_work_items(limit: int = 50, offset: int = 0, x_rocksoul_api_key: str | None = Header(default=None)):
        require_operator(x_rocksoul_api_key)
        return work_items.list(limit=limit, offset=offset)

    @app.post("/api/v1/work-items")
    def create_work_item(body: dict[str, Any], x_rocksoul_api_key: str | None = Header(default=None)):
        require_operator(x_rocksoul_api_key)
        try:
            item = WorkItem.from_dict(body)
            return work_items.create(item)
        except ContractValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except WorkItemStoreError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/work-items/{work_id}")
    def get_work_item(work_id: str, x_rocksoul_api_key: str | None = Header(default=None)):
        require_operator(x_rocksoul_api_key)
        result = work_items.get(work_id)
        if result is None:
            raise HTTPException(status_code=404, detail="WorkItem not found")
        return result

    @app.post("/api/v1/work-items/{work_id}/transitions")
    def transition_work_item(work_id: str, body: dict[str, Any], x_rocksoul_api_key: str | None = Header(default=None)):
        require_operator(x_rocksoul_api_key)
        if set(body) - {"expected_status", "target_status", "payload"}:
            raise HTTPException(status_code=422, detail="Unknown transition fields")
        if not body.get("expected_status") or not body.get("target_status"):
            raise HTTPException(status_code=422, detail="expected_status and target_status are required")
        try:
            return work_items.transition(
                work_id, body["target_status"], expected_status=body["expected_status"],
                payload=body.get("payload"),
            )
        except WorkItemStoreError as exc:
            code = 404 if str(exc) == "WorkItem not found" else 409
            raise HTTPException(status_code=code, detail=str(exc)) from exc
        except (ContractValidationError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/work-items/{work_id}/criteria/{criterion_id}/verify")
    def verify_work_item_criterion(
        work_id: str,
        criterion_id: str,
        body: dict[str, Any],
        x_rocksoul_api_key: str | None = Header(default=None),
    ):
        require_operator(x_rocksoul_api_key)
        allowed = {"profile_id", "profile_version", "artifact_base64", "source", "expected_sha256", "schema"}
        if set(body) - allowed:
            raise HTTPException(status_code=422, detail="Unknown verifier request fields")
        if not all(key in body for key in ("profile_id", "profile_version", "artifact_base64", "source")):
            raise HTTPException(status_code=422, detail="profile_id, profile_version, artifact_base64, and source are required")
        try:
            if not isinstance(body["artifact_base64"], str):
                raise ValueError("artifact_base64 must be a string")
            if len(body["artifact_base64"]) > 1_333_336:
                raise ValueError("encoded artifact must not exceed the 1 MiB decoded limit")
            artifact = base64.b64decode(body["artifact_base64"], validate=True)
            if not artifact or len(artifact) > 1_000_000:
                raise ValueError("artifact must contain 1 to 1000000 bytes")
            profile = verification_profiles.resolve(body["profile_id"], body["profile_version"])
            execution = VerificationEngine().verify(
                profile, artifact, source=body["source"],
                expected_sha256=body.get("expected_sha256"), schema=body.get("schema"),
            )
            return work_items.record_verification(work_id, criterion_id, execution)
        except WorkItemStoreError as exc:
            code = 404 if str(exc) in {"WorkItem not found", "acceptance criterion not found"} else 409
            raise HTTPException(status_code=code, detail=str(exc)) from exc
        except (ValueError, binascii.Error, VerificationProfileError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


    @app.post("/api/v1/work-items/{work_id}/approval")
    def record_work_item_approval(
        work_id: str,
        body: dict[str, Any],
        x_rocksoul_api_key: str | None = Header(default=None),
        x_rocksoul_approval_signature: str | None = Header(default=None),
    ):
        require_operator(x_rocksoul_api_key)
        allowed = {"decision", "approver_id", "approver_role", "contract_digest", "issued_at", "nonce"}
        if set(body) != allowed:
            raise HTTPException(status_code=422, detail="Approval payload fields are incomplete or unknown")
        secret = os.environ.get("ROCKSOUL_APPROVAL_SIGNING_SECRET", "")
        if len(secret) < 32:
            raise HTTPException(status_code=503, detail="ROCKSOUL_APPROVAL_SIGNING_SECRET must contain at least 32 characters")
        if not isinstance(x_rocksoul_approval_signature, str) or len(x_rocksoul_approval_signature) != 64 or any(ch not in "0123456789abcdef" for ch in x_rocksoul_approval_signature):
            raise HTTPException(status_code=401, detail="Signed administrator approval is required")
        try:
            canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="Approval payload must contain finite JSON values") from exc
        expected_signature = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), "sha256").hexdigest()
        if not hmac.compare_digest(x_rocksoul_approval_signature, expected_signature):
            raise HTTPException(status_code=401, detail="Approval signature is invalid")
        issued_at = body.get("issued_at")
        if isinstance(issued_at, bool) or not isinstance(issued_at, int) or abs(int(datetime.now(timezone.utc).timestamp()) - issued_at) > 300:
            raise HTTPException(status_code=401, detail="Approval signature has expired")
        nonce = body.get("nonce")
        if not isinstance(nonce, str) or len(nonce) != 32 or any(ch not in "0123456789abcdef" for ch in nonce):
            raise HTTPException(status_code=422, detail="Approval nonce is invalid")
        if body.get("approver_role") != "admin":
            raise HTTPException(status_code=403, detail="Administrator approval is required")
        current = work_items.get(work_id)
        if current is None:
            raise HTTPException(status_code=404, detail="WorkItem not found")
        if not hmac.compare_digest(str(current["contract_digest"]), str(body.get("contract_digest", ""))):
            raise HTTPException(status_code=409, detail="Approval targets a different immutable WorkItem contract")
        import hashlib
        payload_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        signature_digest = hashlib.sha256(x_rocksoul_approval_signature.encode("ascii")).hexdigest()
        try:
            return work_items.record_approval(
                work_id, decision=body["decision"], approver_id=body["approver_id"],
                approver_role=body["approver_role"], issued_at=issued_at, nonce=nonce,
                signed_payload_digest=payload_digest, signature_digest=signature_digest,
            )
        except WorkItemStoreError as exc:
            code = 404 if str(exc) == "WorkItem not found" else 409
            raise HTTPException(status_code=code, detail=str(exc)) from exc


    @app.get("/api/v1/work-items/{work_id}/evidence-diff")
    def work_item_evidence_diff(work_id: str, x_rocksoul_api_key: str | None = Header(default=None)):
        require_operator(x_rocksoul_api_key)
        item = work_items.get(work_id)
        if item is None:
            raise HTTPException(status_code=404, detail="WorkItem not found")
        integrity = work_items.verify_event_chain(work_id)
        if not integrity.get("ok"):
            raise HTTPException(status_code=409, detail="WorkItem event chain is invalid; evidence diff is unavailable")
        grouped: dict[str, list[dict[str, Any]]] = {};
        for verification in item["verifications"]:
            grouped.setdefault(verification["criterion_id"], []).append(verification)
        criteria = {}
        for criterion_id, attempts in grouped.items():
            attempts.sort(key=lambda entry: (entry["created_at"], entry["verification_id"]))
            previous = attempts[-2] if len(attempts) > 1 else None
            latest = attempts[-1]
            previous_findings = set((previous or {}).get("result", {}).get("findings", []))
            latest_findings = set(latest.get("result", {}).get("findings", []))
            criteria[criterion_id] = {
                "attempt_count": len(attempts),
                "previous": previous,
                "latest": latest,
                "changed": bool(previous and (
                    previous["outcome"] != latest["outcome"]
                    or previous["artifact_digest"] != latest["artifact_digest"]
                    or previous["profile_id"] != latest["profile_id"]
                    or previous["profile_version"] != latest["profile_version"]
                )),
                "findings_added": sorted(latest_findings - previous_findings),
                "findings_resolved": sorted(previous_findings - latest_findings),
            }
        return {"work_id": work_id, "criteria": criteria, "total_criteria_with_evidence": len(criteria), "integrity": integrity}

    @app.get("/api/v1/work-items/{work_id}/evidence-bundle")
    def work_item_evidence_bundle(work_id: str, x_rocksoul_api_key: str | None = Header(default=None)):
        require_operator(x_rocksoul_api_key)
        item = work_items.get(work_id)
        if item is None:
            raise HTTPException(status_code=404, detail="WorkItem not found")
        integrity = work_items.verify_event_chain(work_id)
        return {
            "bundle_schema_version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "work_item": item,
            "integrity": integrity,
            "contents": ["immutable_contract", "lifecycle_events", "execution_links", "verifier_receipts", "approval_events"],
            "trust_boundary": "Metadata-only export: artifact bytes are not retained; source authenticity and external signatures are not established. Event hash chaining is tamper-evident, not a WORM store or external signature.",
        }

    @app.get("/api/v1/work-items/{work_id}/verify-chain")
    def verify_work_item_chain(work_id: str, x_rocksoul_api_key: str | None = Header(default=None)):
        require_operator(x_rocksoul_api_key)
        result = work_items.verify_event_chain(work_id)
        if result.get("reason") == "work_item_not_found":
            raise HTTPException(status_code=404, detail="WorkItem not found")
        return result

    @app.get("/api/v1/traces")
    def list_traces(limit: int = 50, offset: int = 0):
        limit=max(1,min(limit,200)); offset=max(0,min(offset,100000))
        with database.connect() as conn:
            rows=conn.execute("""SELECT r.request_id,r.model,r.started_at,r.finished_at,r.status,r.attempt_count,
                r.final_error_class,r.work_id,p.name selected_provider FROM execution_runs r
                LEFT JOIN providers p ON p.id=r.selected_provider_id
                ORDER BY r.started_at DESC,r.request_id DESC LIMIT ? OFFSET ?""",(limit,offset)).fetchall()
            total=int(conn.execute("SELECT COUNT(*) FROM execution_runs").fetchone()[0])
        return {"items":[dict(row) for row in rows],"total":total,"limit":limit,"offset":offset}

    @app.get("/api/v1/mesh")
    def mesh_overview(limit: int = 100):
        mesh=MeshStore(database); limit=max(1,min(limit,200))
        with database.connect() as conn:
            leases=conn.execute("SELECT id,request_id,node_id,status,created_at,expires_at,finished_at,error FROM mesh_leases ORDER BY created_at DESC LIMIT ?",(limit,)).fetchall()
        return {"status":mesh.status(),"nodes":[{**asdict(node),"score":node.score} for node in mesh.list_nodes()],"leases":[dict(row) for row in leases],"events":mesh.events(limit=limit)}

    @app.post("/api/v1/mesh/nodes/{node_id}/state")
    def set_mesh_node_state(node_id: str, body: dict[str, Any], x_rocksoul_api_key: str | None = Header(default=None)):
        require_operator(x_rocksoul_api_key)
        if set(body)-{"state","reason"}: raise HTTPException(status_code=422,detail="Unknown fields")
        state=str(body.get("state","")).upper()
        if state not in {"ACTIVE","DRAINING","QUARANTINED","OFFLINE"}: raise HTTPException(status_code=422,detail="Unsupported operator node state")
        try: node=MeshStore(database).set_state(node_id,state,str(body.get("reason") or "operator_action")[:300])
        except MeshError as exc: raise HTTPException(status_code=404,detail="Mesh node not found or state invalid") from exc
        return {"node_id":node.node_id,"state":node.state,"reason":node.reason}

    @app.get("/api/v1/arena")
    def arena_overview(limit: int = 100):
        arena=ArenaStore(database); production=ArenaProductionStore(arena); limit=max(1,min(limit,200))
        return {"status":arena.status(),"production":production.status(),"packs":production.list_packs(limit=limit),
                "campaigns":production.list_campaigns(limit=limit),"runs":arena.list_runs(limit=limit),"leaderboard":arena.leaderboard()}

    @app.get("/api/v1/arena/campaigns/{campaign_id}/verify")
    def verify_arena_campaign(campaign_id: str):
        result=ArenaProductionStore(ArenaStore(database)).verify_campaign(campaign_id)
        if result is None: raise HTTPException(status_code=404,detail="Arena campaign not found")
        return result

    @app.get("/api/v1/arena/packs/{pack_digest}/report")
    def arena_pack_report(pack_digest: str,target_digest: str|None=None):
        return ArenaProductionStore(ArenaStore(database)).campaign_report(pack_digest,target_digest)

    @app.post("/api/v1/providers/{provider}/control")
    def control_provider(provider: str,body: dict[str, Any],x_rocksoul_api_key: str|None=Header(default=None)):
        require_operator(x_rocksoul_api_key)
        if set(body)-{"action","reason"}: raise HTTPException(status_code=422,detail="Unknown fields")
        action=str(body.get("action","")).lower(); reason=str(body.get("reason") or "operator_action")[:300]
        store=ProviderControlStore(database)
        actions={"activate":store.active,"quarantine":store.quarantine,"probe":store.begin_recovery,"readmit":store.re_admit}
        if action not in actions: raise HTTPException(status_code=422,detail="Unsupported provider control action")
        try: state=actions[action](provider,reason)
        except (KeyError,ValueError) as exc: raise HTTPException(status_code=404,detail="Provider not found") from exc
        return {"provider":state.provider,"state":state.state,"reason":state.reason}

    @app.get("/api/v1/traces/{request_id}")
    def get_trace(request_id: str):
        trace = traces.trace(request_id)
        if trace is None:
            raise HTTPException(status_code=404, detail="Execution trace not found")
        return trace

    @app.post("/api/v1/execute")
    def execute(body: ExecuteBody, x_rocksoul_api_key: str | None = Header(default=None)):
        require_operator(x_rocksoul_api_key)
        if body.stream:
            raise HTTPException(status_code=422, detail="Streaming is not exposed by this JSON endpoint")
        supported = {"streaming", "tools", "structured_output", "vision", "image"}
        if any(item not in supported for item in body.requirements):
            raise HTTPException(status_code=422, detail="Unsupported capability requirement")
        effective_max_attempts = body.max_attempts
        effective_max_total_time = body.max_total_time
        effective_timeout = body.timeout
        applied_budget = None
        if body.work_id:
            linked_work = work_items.get(body.work_id)
            if linked_work is None:
                raise HTTPException(status_code=404, detail="WorkItem not found")
            if linked_work["status"] != WorkStatus.RUNNING.value:
                raise HTTPException(status_code=409, detail="WorkItem must be RUNNING before execution")
            work_contract = WorkItem.from_dict(linked_work["contract"])
            if work_contract.human_approval_required and (linked_work.get("latest_approval") or {}).get("decision") != "approved":
                raise HTTPException(status_code=409, detail="WorkItem requires a verified administrator approval before execution")
            if "model.execute" not in work_contract.permissions:
                raise HTTPException(status_code=403, detail="WorkItem does not grant model.execute permission")
            if work_contract.deadline_at:
                deadline = datetime.fromisoformat(work_contract.deadline_at.replace("Z", "+00:00"))
                if deadline <= datetime.now(timezone.utc):
                    raise HTTPException(status_code=409, detail="WorkItem deadline has expired")
            if work_contract.budget.max_tokens is not None or work_contract.budget.max_cost_usd is not None:
                raise HTTPException(status_code=409, detail="Current provider adapters cannot enforce token/cost budgets; execution denied")
            effective_max_attempts = min(body.max_attempts, work_contract.budget.max_attempts)
            effective_max_total_time = min(body.max_total_time, work_contract.budget.max_wall_time_seconds)
            effective_timeout = min(body.timeout, effective_max_total_time)
            applied_budget = {
                "max_attempts": effective_max_attempts,
                "max_total_time": effective_max_total_time,
                "timeout": effective_timeout,
            }
        request = ExecutionRequest(
            model=body.model, messages=body.messages,
            requirements=tuple(body.requirements), providers=tuple(body.providers),
            max_attempts=effective_max_attempts,
            max_same_provider_attempts=body.max_same_provider_attempts,
            max_total_time=effective_max_total_time, timeout=effective_timeout, stream=False,
        )
        result = ExecutionEngine(database).execute(request)
        if body.work_id:
            try:
                work_items.attach_execution(body.work_id, result.request_id, result.outcome, applied_budget=applied_budget)
            except WorkItemStoreError as exc:
                raise HTTPException(status_code=409, detail=f"Execution completed but trace linkage failed: {exc}") from exc
        attempts = [{
            "attempt_no": item.attempt_no, "provider": item.provider, "model": item.model,
            "started_at": item.started_at, "finished_at": item.finished_at,
            "latency_ms": item.latency_ms, "status": item.status,
            "error_class": item.error_class, "error": item.error,
            "response_valid": item.response_valid,
        } for item in result.attempts]
        return {
            "request_id": result.request_id, "ok": result.ok, "model": result.model,
            "provider": result.provider, "outcome": result.outcome,
            "transport_outcome": result.outcome,
            "work_id": body.work_id,
            "task_outcome": "unverified" if body.work_id else None,
            "applied_budget": applied_budget,
            "error_class": result.error_class, "error": result.error,
            "response": _safe_response(result.response), "attempts": attempts,
        }

    return app


def main() -> None:
    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit("Install with: pip install 'g4f[rocksoul-api]'") from exc
    host = os.environ.get("ROCKSOUL_API_HOST", "127.0.0.1")
    port = int(os.environ.get("ROCKSOUL_API_PORT", "8765"))
    if host not in {"127.0.0.1", "::1", "localhost"} and not os.environ.get("ROCKSOUL_API_KEY"):
        raise SystemExit("ROCKSOUL_API_KEY is required when binding the API beyond loopback")
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
