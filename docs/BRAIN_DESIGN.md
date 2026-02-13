# AI Brain Design

Pipeline:

Input → Normalize → Hash → Cache Check → DB Check → LLM → Validate → Store → Cache → Response

Responsibilities:

- core: orchestration
- memory: cache + database
- reasoning: model calls
- validation: output safety
