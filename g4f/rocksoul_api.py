"""Authenticated HTTP product API for the ROCKSOUL control plane.

This adapter composes existing stores, routing and execution services. It does
not implement or own provider adapters.
"""
import hmac
import os
from typing import Any

from .rocksoul_control import ProviderControlStore
from .rocksoul_db import RocksoulDB
from .rocksoul_execution import ExecutionEngine, ExecutionRequest
from .rocksoul_execution_store import ExecutionTraceStore
from .rocksoul_intelligence import CapabilityRequirement, ExplainableRouter


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
        from pydantic import BaseModel, ConfigDict, Field
    except ImportError as exc:
        raise RuntimeError("ROCKSOUL HTTP API requires the 'rocksoul-api' extra") from exc

    database = db or RocksoulDB()
    traces = ExecutionTraceStore(database)
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
        request = ExecutionRequest(
            model=body.model, messages=body.messages,
            requirements=tuple(body.requirements), providers=tuple(body.providers),
            max_attempts=body.max_attempts,
            max_same_provider_attempts=body.max_same_provider_attempts,
            max_total_time=body.max_total_time, timeout=body.timeout, stream=False,
        )
        result = ExecutionEngine(database).execute(request)
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
