"""
main.py — FastAPI entry point for MathMinds AI
"""

import os
import sys
import asyncio
import logging
import uuid
import time

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Windows async fix
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"

from fastapi import FastAPI, HTTPException, status, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.limiter import limiter
from app.core.orchestrator import Orchestrator
from app.core.schemas import (
    SolveRequest,
    ChatSession,
    Message,
    SessionRename,
)
from app.core.logging_config import configure_logging
from app.core.settings import settings
from app.core.errors import AppError, ErrorCodes

from app.api.deps import (
    get_orchestrator,
    get_redis_pool,
    get_mongo_client,
    get_db_manager,
    get_redis_client,
)

from app.core.security import get_current_user

# Logging
configure_logging()
logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB limit


# ═════════════════════════════════════════════════════════════════════
# LIFESPAN
# ═════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting MathMinds AI")

    try:
        get_redis_pool()
        get_mongo_client()
        get_orchestrator()
        logger.info("Startup complete")
    except Exception as e:
        logger.critical(f"Startup failure: {e}")

    yield

    logger.info("Shutting down MathMinds")

    try:
        from app.api.deps import close_redis, close_mongo

        close_redis()
        close_mongo()

        logger.info("Shutdown complete")
    except Exception as e:
        logger.error(f"Shutdown error: {e}")


# ═════════════════════════════════════════════════════════════════════
# FASTAPI APP
# ═════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="MathMinds AI API",
    description="AI-powered math solver API",
    version="1.0.0",
    lifespan=lifespan,
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═════════════════════════════════════════════════════════════════════
# MIDDLEWARE
# ═════════════════════════════════════════════════════════════════════

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):

    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    start_time = time.time()

    logger.info(
        "Request started",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
        },
    )

    response = await call_next(request)

    duration = time.time() - start_time

    response.headers["X-Request-ID"] = request_id

    logger.info(
        "Request finished",
        extra={
            "request_id": request_id,
            "status_code": response.status_code,
            "duration": duration,
        },
    )

    return response


@app.middleware("http")
async def timeout_middleware(request: Request, call_next):

    try:
        return await asyncio.wait_for(call_next(request), timeout=120)

    except asyncio.TimeoutError:

        logger.error(f"Timeout: {request.url.path}")

        return JSONResponse(
            status_code=504,
            content={"detail": "Request timed out"},
        )


# ═════════════════════════════════════════════════════════════════════
# EXCEPTION HANDLERS
# ═════════════════════════════════════════════════════════════════════

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):

    request_id = getattr(request.state, "request_id", "unknown")

    logger.error(
        f"[{request_id}] Unhandled error: {exc}",
        exc_info=True
    )

    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "error": "Internal Server Error",
            "metadata": {
                "request_id": request_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        },
    )


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):

    mapping = {
        ErrorCodes.INPUT_VALIDATION_ERROR: 400,
        ErrorCodes.RESOURCE_NOT_FOUND: 404,
        ErrorCodes.RATE_LIMIT_EXCEEDED: 429,
        ErrorCodes.DEPENDENCY_ERROR: 503,
        ErrorCodes.GEMINI_ERROR: 503,
    }

    status_code = mapping.get(exc.code, 500)

    request_id = getattr(request.state, "request_id", "unknown")

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "error": exc.message,
            "error_code": exc.code,
            "metadata": {
                "request_id": request_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        },
    )


# ═════════════════════════════════════════════════════════════════════
# GENERAL ROUTES
# ═════════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    return {"message": "MathMinds API running"}


@app.get("/version")
async def version():
    return {
        "version": "1.0.0",
        "build": os.getenv("BUILD_ID"),
        "commit": os.getenv("GIT_SHA"),
    }


@app.get("/health")
async def health():

    health: Dict[str, Any] = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {},
    }

    try:
        # 2s timeout for Redis
        ping_task = asyncio.to_thread(get_redis_client().ping)
        await asyncio.wait_for(ping_task, timeout=2.0)
        health["services"]["redis"] = "healthy"
    except Exception as e:
        health["services"]["redis"] = str(e)
        health["status"] = "degraded"

    try:
        # 2s timeout for Mongo
        mongo_ping = asyncio.to_thread(get_mongo_client().admin.command, "ping")
        await asyncio.wait_for(mongo_ping, timeout=2.0)
        health["services"]["mongodb"] = "healthy"
    except Exception as e:
        health["services"]["mongodb"] = str(e)
        health["status"] = "degraded"

    return health


# ═════════════════════════════════════════════════════════════════════
# SOLVE ROUTE
# ═════════════════════════════════════════════════════════════════════

@app.post("/solve")
@limiter.limit("5/minute")
async def solve_problem(
    request: Request,
    solve_req: SolveRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
    current_user: dict = Depends(get_current_user),
):
    """
    Solve a math problem and return the result.
    """

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    if not solve_req.effective_text and not solve_req.image:
        raise HTTPException(
            status_code=400,
            detail="Either text or image must be provided",
        )

    if solve_req.image and len(solve_req.image) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Image too large",
        )

    logger.info(
        "Solve request received",
        extra={
            "request_id": request_id,
            "user_id": current_user["uid"],
            "session_id": solve_req.session_id,
        },
    )

    try:
        result = await orchestrator.solve_problem(
            query=solve_req.effective_text,
            image=solve_req.image,
            user_id=current_user["uid"],
            session_id=solve_req.session_id,
            request_id=request_id,
        )

        return JSONResponse(status_code=200, content=result)

    except Exception as e:

        logger.error(f"Solve error: {e}")

        raise HTTPException(
            status_code=500,
            detail="Internal processing error",
        )


# ═════════════════════════════════════════════════════════════════════
# CHAT ROUTES
# ═════════════════════════════════════════════════════════════════════

@app.get("/chat/sessions", response_model=List[ChatSession])
async def list_sessions(
    current_user: dict = Depends(get_current_user),
    db_manager=Depends(get_db_manager),
):
    return db_manager.list_sessions(current_user["uid"])


@app.post("/chat/sessions", response_model=ChatSession)
async def create_session(
    current_user: dict = Depends(get_current_user),
    db_manager=Depends(get_db_manager),
):

    session_id = str(uuid.uuid4())
    title = "New Chat"

    if db_manager.create_session(current_user["uid"], session_id, title):
        return {
            "session_id": session_id,
            "title": title,
            "created_at": datetime.now(timezone.utc),
        }

    raise HTTPException(500, "Failed to create session")


@app.get("/chat/sessions/{session_id}/messages", response_model=List[Message])
async def get_messages(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db_manager=Depends(get_db_manager),
):

    history = db_manager.get_chat_history(current_user["uid"], session_id)

    if history is None:
        raise HTTPException(404, "Session not found")

    return history


@app.patch("/chat/sessions/{session_id}")
async def rename_session(
    session_id: str,
    rename_data: SessionRename,
    current_user: dict = Depends(get_current_user),
    db_manager=Depends(get_db_manager),
):

    if db_manager.rename_session(
        current_user["uid"],
        session_id,
        rename_data.title,
    ):
        return {"status": "success"}

    raise HTTPException(404, "Session not found")


@app.delete("/chat/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db_manager=Depends(get_db_manager),
):

    if db_manager.delete_session(current_user["uid"], session_id):
        return {"status": "success"}

    raise HTTPException(404, "Session not found")


# ═════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═════════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    import uvicorn

    port = int(os.environ.get("PORT", 8080))

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
    )