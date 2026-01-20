"""
Data models and schema utilities.

Lightweight dataclasses used to build the structured JSON response. Kept minimal
to avoid heavy external dependencies like pydantic while preserving clear shape.
"""
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional
import json


@dataclass
class MMResponse:
    id: str
    timestamp: str
    query: str
    agent: Optional[str] = None
    success: bool = False
    code: Optional[str] = None
    sanitized_code: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None
    explanation: Optional[str] = None
    error: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)