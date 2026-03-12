"""
schemas.py

BUG FIX — Message model was missing `request_id: Optional[str]`.

Why this caused "no answer" on the UI:
  The GET /chat/sessions/{id}/messages endpoint uses `response_model=List[Message]`.
  FastAPI strips any field NOT declared in the model before sending the response.
  So even though `save_chat_message(..., request_id=request_id)` correctly stores
  request_id in MongoDB, FastAPI silently dropped it on the way back out.

  The frontend's load_messages() dedup merge keys on (role, request_id):
    server_keys = {(m["role"], m["request_id"]) for m in server_msgs if m.get("request_id")}

  With request_id always None from server, server_keys was always empty.
  On every load_messages() call, ALL local messages looked unconfirmed, so they
  got appended again as duplicates — and on the next rerun the trigger condition
  `role=="user" and not sent_to_api` re-fired, sending the question a second time
  and overwriting the answer_placeholder before it could be seen.
"""

from datetime import datetime
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field, model_validator


class SolveRequest(BaseModel):
    text:             Optional[str] = Field(None, description="The math problem text.")
    image:            Optional[str] = Field(None, description="Base64 encoded image string.")
    session_id:       Optional[str] = Field(None, description="Session ID for chat context.")
    model_preference: Optional[str] = Field("fast", description="'fast' or 'reasoning'.")
    request_id:       Optional[str] = Field(None, description="Unique ID for deduplication.")
    input:            Optional[str] = Field(None, description="Legacy field.", deprecated=True)

    @property
    def effective_text(self) -> Optional[str]:
        return self.text or self.input

    @model_validator(mode='before')
    @classmethod
    def check_input_compatibility(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if 'input' in values and not values.get('text'):
                values['text'] = values['input']
        return values

    @model_validator(mode='after')
    def check_at_least_one(self) -> 'SolveRequest':
        if not self.text and not self.image:
            raise ValueError("At least one of 'text' or 'image' must be provided.")
        return self


class SolveResponse(BaseModel):
    request_id:   str
    status:       str  = Field(..., description="success/error")
    problem_type: str  = "unknown"
    source:       str  = "unknown"
    answer:       Any  = Field(None)
    steps:        List[str] = Field(default_factory=list)
    explanation:  Optional[str] = None
    confidence:   float = 0.0
    cached:       bool  = False
    error:        Optional[str] = None
    error_code:   Optional[str] = None
    metadata:     Dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status:  str
    version: str


class Message(BaseModel):
    role:       str
    content:    str
    timestamp:  datetime
    # FIX: This field was missing. FastAPI was stripping it from every response,
    # breaking the frontend dedup merge and causing phantom re-triggers.
    request_id: Optional[str]  = None
    reasoning:  Optional[str]  = None
    metadata:   Dict[str, Any] = {}
    steps:      List[str]      = []


class ChatSession(BaseModel):
    session_id: str
    title:      str
    created_at: datetime


class SessionRename(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)


class UserSignup(BaseModel):
    email:     str
    password:  str = Field(..., min_length=8, max_length=72)
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    email:    str
    password: str = Field(..., max_length=72)


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user_id:      str
    email:        str