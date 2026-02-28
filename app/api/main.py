import os
os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"
from typing import Any, Dict, Optional, List
import sys
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import logging
from datetime import datetime, timezone
import uuid
import sys
import json

from fastapi import FastAPI, HTTPException, status, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.limiter import limiter
from app.core.orchestrator import Orchestrator
from app.core.schemas import SolveRequest, SolveResponse, HealthResponse, Message, ChatSession, SessionRename, UserSignup, UserLogin, TokenResponse
from app.core.auth_utils import hash_password, verify_password, create_access_token
from app.core.logging_config import configure_logging
from app.core.errors import AppError, ErrorCodes, ERROR_MESSAGES
from app.core.settings import settings  # New settings module
import os
# Import dependency
from app.api.deps import get_orchestrator, get_redis_pool, get_mongo_client, get_db_manager, get_redis_client
from app.core.security import verify_token, get_current_user

from contextlib import asynccontextmanager

# Configure logging
configure_logging()
logger = logging.getLogger(__name__)



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Preload resources
    logger.info("🚀 Starting MathMinds AI... Warming up resources.")
    
    try:
        # 1. Initialize Redis Pool
        get_redis_pool()
        
        # 2. Initialize MongoDB Client
        get_mongo_client()
        
        # 3. Initialize Orchestrator (Loads YOLO, Supabase, etc.)
        # This is the heavy lifting
        get_orchestrator()
        
        logger.info("✅ Startup complete: Orchestrator & DBs ready.")
    except Exception as e:
        logger.critical(f"❌ Critical Startup Error: {e}")
        # We might want to exit here, but let's allow it to run in degraded mode 
        # or let the first request fail.
    
    yield
    
    # Shutdown: Cleanup if needed
    logger.info("🛑 Shutting down MathMinds AI...")
    # (Optional) Close connections here if we implemented close methods

app = FastAPI(
    title="MathMinds AI API",
    description="API for solving math problems using Gemini and local reasoning.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handler (Catch-All)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(f"[{request_id}] Unhandled Exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "error": "Internal Server Error",
            "error_code": "INTERNAL_ERROR",
            "metadata": {
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    )

# Initialize Rate Limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    """Handle application-level errors with proper HTTP status codes."""
    
    # Map error codes to HTTP status codes
    error_to_status = {
        ErrorCodes.INPUT_VALIDATION_ERROR: status.HTTP_400_BAD_REQUEST,
        ErrorCodes.RESOURCE_NOT_FOUND: status.HTTP_404_NOT_FOUND,
        ErrorCodes.DEPENDENCY_ERROR: status.HTTP_503_SERVICE_UNAVAILABLE,
        ErrorCodes.GEMINI_ERROR: status.HTTP_503_SERVICE_UNAVAILABLE,
        ErrorCodes.RATE_LIMIT_EXCEEDED: status.HTTP_429_TOO_MANY_REQUESTS,
        ErrorCodes.INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
    }
    
    http_status = error_to_status.get(exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.error(f"[{request_id}] AppError: {exc.code} - {exc.message}")
    
    return JSONResponse(
        status_code=http_status,
        content={
            "status": "error",
            "error": exc.message,
            "error_code": exc.code,
            "metadata": {
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    )

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    # Context for logging
    log_context = {"request_id": request_id, "path": request.url.path, "method": request.method}
    
    logger.info("Request started", extra=log_context)
    
    import time
    start_time = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    response.headers["X-Request-ID"] = request_id
    
    logger.info("Request finished", extra={
        **log_context, 
        "status_code": response.status_code, 
        "duration": duration
    })
    
    return response

@app.get("/health")
async def health_check():
    """Detailed health check endpoint."""
    health_status = {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {}
    }
    
    # Check Redis
    try:
        redis_client = get_redis_client()
        if redis_client:
            redis_client.ping()
            health_status["components"]["redis"] = "✓ healthy" # using shared pool
        else:
            health_status["components"]["redis"] = "✗ unavailable"
    except Exception as e:
        health_status["components"]["redis"] = f"✗ error: {str(e)}"
    
    # Check MongoDB
    try:
        mongo_client = get_mongo_client()
        if mongo_client:
            # Low timeout ping
            mongo_client.admin.command('ping')
            health_status["components"]["mongodb"] = "✓ healthy"
        else:
            health_status["components"]["mongodb"] = "✗ unavailable"
    except Exception as e:
        health_status["components"]["mongodb"] = f"✗ error: {str(e)}"
    
    # Check Gemini
    try:
        # Just verify we have API key
        api_key = os.getenv("GOOGLE_API_KEY")
        if api_key:
            health_status["components"]["gemini"] = "✓ configured"
        else:
            health_status["components"]["gemini"] = "✗ not configured"
    except Exception as e:
        health_status["components"]["gemini"] = f"✗ error: {str(e)}"
    
    # Overall status
    if any("✗" in str(v) for v in health_status["components"].values()):
        health_status["status"] = "degraded"
    
    return health_status

@app.post("/solve")
@limiter.limit("5/minute")
async def solve_problem(
    request: Request,
    solve_req: SolveRequest, 
    orchestrator: Orchestrator = Depends(get_orchestrator),
    current_user: dict = Depends(get_current_user) # Protect this route
):
    """
    Solves a mocked problem provided in the request body.
    """
    # Grab request_id from state
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    if not orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestrator not initialized"
        )

    # Deduplication Check (Redis)
    final_request_id = solve_req.request_id or req_id
    dedup_key = f"active_req:{final_request_id}"
    
    redis_client = None
    try:
        redis_client = get_redis_client()
        # Set key with 300s expiry, only if it doesn't exist (nx=True)
        if not redis_client.set(dedup_key, "processing", ex=300, nx=True):
            logger.warning(f"[{final_request_id}] Blocked duplicate request (UI retry).")
            # Return 202 Accepted (Processing) - Friendly response
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={
                    "status": "processing",
                    "message": "Request is currently being processed. Please wait...",
                    "metadata": {"request_id": final_request_id}
                }
            )
    except Exception as e:
        logger.warning(f"Redis dedup failed (failing open): {e}")
        # If Redis fails, we allow the request to proceed (fail open)

    async def event_generator():
        try:
            async for chunk in orchestrator.process_problem(
                text=solve_req.effective_text, 
                image=solve_req.image, 
                request_id=final_request_id,
                model_preference=solve_req.model_preference,
                session_id=solve_req.session_id,
                user_id=current_user.get("uid")
            ):
                yield json.dumps(chunk) + "\n"
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield json.dumps({"type": "error", "content": "Internal processing error"}) + "\n"
        finally:
            if redis_client:
                try:
                    redis_client.delete(dedup_key)
                except Exception:
                    pass

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

# --- Chat History Endpoints ---

@app.get("/chat/sessions", response_model=List[ChatSession])
async def list_chat_sessions(
    current_user: dict = Depends(get_current_user),
    db_manager = Depends(get_db_manager)
):
    """List all chat sessions for the current user."""
    return db_manager.list_sessions(current_user["uid"])

@app.post("/chat/sessions", response_model=ChatSession)
async def create_chat_session(
    current_user: dict = Depends(get_current_user),
    db_manager = Depends(get_db_manager)
):
    """Create a new chat session."""
    session_id = str(uuid.uuid4())
    title = "New Chat"
    if db_manager.create_session(current_user["uid"], session_id, title):
        return {
            "session_id": session_id,
            "title": title,
            "created_at": datetime.utcnow()
        }
    raise HTTPException(status_code=500, detail="Failed to create session")

@app.get("/chat/sessions/{session_id}/messages", response_model=List[Message])
async def get_session_history(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db_manager = Depends(get_db_manager)
):
    """Get message history for a specific session."""
    history = db_manager.get_chat_history(current_user["uid"], session_id)
    if not history and history != []:
        raise HTTPException(status_code=404, detail="Session not found")
    return history

@app.patch("/chat/sessions/{session_id}")
async def rename_chat_session(
    session_id: str,
    rename_data: SessionRename,
    current_user: dict = Depends(get_current_user),
    db_manager = Depends(get_db_manager)
):
    """Rename a chat session."""
    if db_manager.rename_session(current_user["uid"], session_id, rename_data.title):
        return {"status": "success", "title": rename_data.title}
    raise HTTPException(status_code=404, detail="Session not found or rename failed")

@app.delete("/chat/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db_manager = Depends(get_db_manager)
):
    """Delete a chat session."""
    if db_manager.delete_session(current_user["uid"], session_id):
        return {"status": "success", "message": "Session deleted"}
    raise HTTPException(status_code=404, detail="Session not found or delete failed")

# --- User Profile Endpoints ---
from pydantic import BaseModel
from typing import List, Optional

class UserProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    math_level: Optional[str] = "Student"
    interests: Optional[List[str]] = []

@app.get("/users/profile")
async def get_profile(
    current_user: dict = Depends(get_current_user),
    db_manager = Depends(get_db_manager)
):
    """Get current user profile."""
    try:
        profile = db_manager.get_user_profile(current_user["uid"])
        if not profile:
            # Return basic info if no profile exists yet
            return {
                "user_id": current_user["uid"],
                "email": current_user.get("email"),
                "display_name": "",
                "math_level": "Student",
                "interests": [],
                "is_new": True
            }
        
        # Remove MongoDB _id
        if "_id" in profile:
            del profile["_id"]
        return profile
    except Exception as e:
        logger.error(f"Profile fetch error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch profile")

@app.post("/users/profile")
async def update_profile(
    profile_data: UserProfileUpdate,
    current_user: dict = Depends(get_current_user),
    db_manager = Depends(get_db_manager)
):
    """Update user profile."""
    try:
        success = db_manager.update_user_profile(current_user["uid"], profile_data.dict(exclude_unset=True))
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update profile")
        return {"status": "success", "profile": profile_data.dict()}
    except Exception as e:
        logger.error(f"Profile update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
# ── Auth Endpoints (DECOMMISSIONED - Use Firebase) ──────────────────────────

@app.post("/auth/signup")
async def signup():
    """Signups are now handled by Firebase on the frontend."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Local signup is decommissioned. Please use Firebase Auth."
    )

@app.post("/auth/login")
async def login():
    """Login is now handled by Firebase on the frontend."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Local login is decommissioned. Please use Firebase Auth."
    )
