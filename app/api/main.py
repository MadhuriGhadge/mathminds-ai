import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from fastapi import FastAPI, HTTPException, status
from app.core.orchestrator import Orchestrator
from app.core.schemas import SolveRequest, SolveResponse, HealthResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MathMinds AI API",
    description="API for solving math problems using Gemini and local reasoning.",
    version="1.0.0"
)

#want to use dependency injection or lifespan events
orchestrator = None

@app.on_event("startup")
async def startup_event():
    global orchestrator
    try:
        orchestrator = Orchestrator()
        logger.info("Orchestrator initialized successfully.")
    except Exception as e:
        logger.critical(f"Failed to initialize Orchestrator: {e}")
        #want to exit here or handle it gracefully depending on deployment
        pass

@app.get("/health", response_model=HealthResponse)
async def health_check():
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
async def solve_problem(request: SolveRequest):
    """
    Solves a math problem provided in the request body.
    """
    if not orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestrator not initialized"
        )

    try:
        result = orchestrator.process_problem(request.input)
        
        # Map internal result to schema
        # The Orchestrator returns a dict that matches the SolveResponse structure mostly
        return SolveResponse(
            status=result["status"],
            answer=result["answer"],
            error=result["error"],
            metadata=result["metadata"]
        )

    except Exception as e:
        logger.error(f"Unhandled error in /solve: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
