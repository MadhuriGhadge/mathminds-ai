import asyncio

# Global semaphore to limit concurrent LLM calls
# Capacity = 1 means strictly one request at a time
LLM_SEMAPHORE = asyncio.Semaphore(1)
