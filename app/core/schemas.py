from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class SolveRequest(BaseModel):
    """
    Request model for the /solve endpoint.
    """
    input: str = Field(..., description="The math problem text or latex to solve.", min_length=1)

class SolveResponse(BaseModel):
    """
    Response model for the /solve endpoint.
    """
    status: str = Field(..., description="Status of the request (success/error).")
    answer: Optional[Dict[str, Any]] = Field(None, description=" Structured answer from the AI.")
    error: Optional[str] = Field(None, description="Error message if status is error.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata about the processing.")

class HealthResponse(BaseModel):
    """
    Response model for the /health endpoint.
    """
    status: str
    version: str
