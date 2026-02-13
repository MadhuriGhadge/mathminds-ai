from abc import ABC, abstractmethod
from typing import Dict, Optional, Any

class BaseModel(ABC):
    """
    Abstract base class for all AI models (Gemini, Qwen, etc).
    Enforces a consistent interface for the Orchestrator.
    """
    
    @abstractmethod
    async def solve(self, prompt: str, image_data: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Solve a problem using the model.
        
        Args:
            prompt: The text prompt.
            image_data: Optional Base64 encoded image or URL.
            **kwargs: Additional model-specific arguments.
            
        Returns:
            Dict containing:
                - 'answer': The solution text/markdown.
                - 'confidence': Float between 0.0 and 1.0.
                - 'model': Name of the model used.
                - 'metadata': Additional info.
        """
        pass
