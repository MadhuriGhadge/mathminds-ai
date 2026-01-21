import logging
import uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from fastapi import FastAPI, HTTPException, status, Depends, Request
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.limiter import limiter
from app.core.orchestrator import Orchestrator
from app.core.schemas import SolveRequest, SolveResponse, HealthResponse
# Import dependency
from app.api.deps import get_orchestrator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MathMinds AI API",
    description="API for solving math problems using Gemini and local reasoning.",
    version="1.0.0"
)

# Initialize Rate Limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
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
        
        # Map internal result to schema
        # The Orchestrator returns a dict that matches the SolveResponse structure mostly
        return SolveResponse(
            status=result["status"],
            answer=result["answer"],
            error=result["error"],
            metadata=result["metadata"]
        )

    except Exception as e:
        logger.error(f"[{req_id}] Unhandled error in /solve: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
