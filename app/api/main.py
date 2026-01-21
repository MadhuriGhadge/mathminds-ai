import logging
import uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from fastapi import FastAPI, HTTPException, status, Depends, Request
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.limiter import limiter
from app.core.limiter import limiter
from app.core.orchestrator import Orchestrator
from app.core.schemas import SolveRequest, SolveResponse, HealthResponse
from app.core.logging_config import configure_logging
from app.core.errors import AppError, ErrorCodes, ERROR_MESSAGES
# Import dependency
from app.api.deps import get_orchestrator

# Configure logging
configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MathMinds AI API",
    description="API for solving math problems using Gemini and local reasoning.",
    version="1.0.0"
)

# Initialize Rate Limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST, # Or 500 depending on code
        content={
            "status": "error",
            "error": exc.message,
            "error_code": exc.code,
            "metadata": {}
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

@app.get("/health", response_model=HealthResponse)
async def health_check(orchestrator: Orchestrator = Depends(get_orchestrator)):
    """
    Health check endpoint.
    """
    if not orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="System failing to initialize"
        )
    return {"status": "healthy", "version": "1.0.0"}

@app.post("/solve", response_model=SolveResponse)
@limiter.limit("5/minute")
async def solve_problem(
    request: Request,
    solve_req: SolveRequest, 
    orchestrator: Orchestrator = Depends(get_orchestrator)
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

    try:
        result = orchestrator.process_problem(solve_req.input, request_id=req_id)
        
        # Sanitize metadata for public response
        public_metadata = result["metadata"].copy()
        public_metadata.pop("_internal_debug", None)
        
        # Map internal result to schema
        return SolveResponse(
            status=result["status"],
            answer=result["answer"],
            error=result.get("error_msg"), # Map internal msg to public error field
            error_code=result.get("error_code"),
            metadata=public_metadata
        )

    except Exception as e:
        logger.error(f"[{req_id}] Unhandled error in /solve: {e}")
        # Return generic error
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "error": ERROR_MESSAGES[ErrorCodes.INTERNAL_ERROR],
                "error_code": ErrorCodes.INTERNAL_ERROR,
                "metadata": {"request_id": req_id}
            }
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
