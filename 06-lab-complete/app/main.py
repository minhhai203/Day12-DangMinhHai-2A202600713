"""Production-ready Day 12 AI agent."""
from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from redis.exceptions import RedisError

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_and_record_cost, get_usage
from app.rate_limiter import check_rate_limit
from app.storage import storage
from utils.mock_llm import ask as llm_ask


logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
_is_ready = False
_in_flight_requests = 0


def log_event(event: str, **fields: object) -> None:
    logger.info(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": event,
                "instance_id": settings.instance_id,
                **fields,
            },
            ensure_ascii=False,
        )
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _is_ready
    log_event("startup", version=settings.app_version, environment=settings.environment)
    try:
        storage.ping()
        _is_ready = True
        log_event("ready", redis=True)
    except RedisError as exc:
        _is_ready = False
        log_event("startup_dependency_failed", dependency="redis", error=str(exc))

    yield

    # Uvicorn handles SIGTERM and waits for in-flight requests before this runs.
    _is_ready = False
    log_event("graceful_shutdown", in_flight_requests=_in_flight_requests)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _in_flight_requests
    started = time.time()
    _in_flight_requests += 1
    try:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Instance-ID"] = settings.instance_id
        log_event(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round((time.time() - started) * 1000, 1),
        )
        return response
    finally:
        _in_flight_requests -= 1


class AskRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = Field(default=None, max_length=64)


class AskResponse(BaseModel):
    user_id: str
    session_id: str
    question: str
    answer: str
    history_count: int
    served_by: str
    model: str
    timestamp: str


def _contextual_answer(question: str, history: list[dict]) -> str:
    normalized = question.lower()
    asks_about_previous = any(
        phrase in normalized
        for phrase in ("what did i", "what did we", "previous", "vừa nói", "trước đó")
    )
    previous_questions = [
        message["content"]
        for message in history[:-1]
        if message.get("role") == "user"
    ]
    if asks_about_previous and previous_questions:
        return f'Your previous question was: "{previous_questions[-1]}"'
    return llm_ask(question)


@app.get("/")
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "endpoints": {
            "ask": "POST /ask",
            "history": "GET /sessions/{session_id}/history",
            "health": "GET /health",
            "ready": "GET /ready",
        },
    }


@app.post("/ask", response_model=AskResponse)
def ask_agent(body: AskRequest, _api_key: str = Depends(verify_api_key)):
    if not _is_ready:
        raise HTTPException(status_code=503, detail="Service is not ready")

    session_id = body.session_id or uuid.uuid4().hex
    try:
        if body.session_id and not storage.session_exists(session_id):
            raise HTTPException(status_code=404, detail="Session not found or expired")
        storage.assert_session_owner(session_id, body.user_id)
        check_rate_limit(body.user_id)

        input_tokens = max(1, len(body.question.split()) * 2)
        estimated_output_tokens = 150
        check_and_record_cost(body.user_id, input_tokens, estimated_output_tokens)

        storage.append_message(session_id, body.user_id, "user", body.question)
        history = storage.get_history(session_id, body.user_id)
        answer = _contextual_answer(body.question, history)
        storage.append_message(session_id, body.user_id, "assistant", answer)
        history = storage.get_history(session_id, body.user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RedisError as exc:
        log_event("redis_error", error=str(exc))
        raise HTTPException(status_code=503, detail="Storage unavailable") from exc

    return AskResponse(
        user_id=body.user_id,
        session_id=session_id,
        question=body.question,
        answer=answer,
        history_count=len(history),
        served_by=settings.instance_id,
        model=settings.llm_model,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/sessions/{session_id}/history")
def session_history(
    session_id: str,
    user_id: str,
    _api_key: str = Depends(verify_api_key),
):
    try:
        history = storage.get_history(session_id, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Storage unavailable") from exc
    if not history:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    return {"session_id": session_id, "user_id": user_id, "messages": history}


@app.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    user_id: str,
    _api_key: str = Depends(verify_api_key),
):
    try:
        deleted = storage.delete_session(session_id, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"deleted": deleted, "session_id": session_id}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": settings.app_version,
        "instance_id": settings.instance_id,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready")
def ready():
    try:
        redis_ready = storage.ping()
    except RedisError:
        redis_ready = False
    if not _is_ready or not redis_ready:
        raise HTTPException(status_code=503, detail="Redis is not ready")
    return {"ready": True, "redis": True, "instance_id": settings.instance_id}


@app.get("/metrics")
def metrics(user_id: str, _api_key: str = Depends(verify_api_key)):
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "in_flight_requests": _in_flight_requests,
        "user_usage": get_usage(user_id),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        timeout_graceful_shutdown=30,
    )
