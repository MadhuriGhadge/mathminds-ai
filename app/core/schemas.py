from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, model_validator

class SolveRequest(BaseModel):
    """
    Request model for the /solve endpoint.
    Supports text-only, image-only, or multimodal (text + image) input.
    """
    text: Optional[str] = Field(None, description="The math problem text or specific question about the image.")
    image: Optional[str] = Field(None, description="Base64 encoded image string or Image URL.")
    model_preference: Optional[str] = Field("fast", description="Model preference: 'fast' or 'reasoning'.")
    input: Optional[str] = Field(None, description="Legacy field for backward compatibility.", deprecated=True)

    @property
    def effective_text(self) -> Optional[str]:
        return self.text or self.input

    @model_validator(mode='before')
    @classmethod
    def check_input_compatibility(cls, values: Any) -> Any:
        # Support legacy 'input' field
        if isinstance(values, dict):
            if 'input' in values and not values.get('text'):
                values['text'] = values['input']
        return values
        
    @model_validator(mode='after')
    def check_at_least_one(self) -> 'SolveRequest':
        text = self.text
        image = self.image
        # We don't check 'input' here because it should have been mapped to 'text' above
        if not text and not image:
             raise ValueError("At least one of 'text' or 'image' must be provided.")
        return self

class SolveResponse(BaseModel):
    """
    Response model for the /solve endpoint.
    """
    status: str = Field(..., description="Status of the request (success/error).")
    answer: Optional[Dict[str, Any]] = Field(None, description=" Structured answer from the AI.")
    error: Optional[str] = Field(None, description="Error message if status is error.")
    error_code: Optional[str] = Field(None, description="Error code if status is error.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata about the processing.")

class HealthResponse(BaseModel):
    """
    Response model for the /health endpoint.
    """
    status: str
    version: str
