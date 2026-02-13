import multiprocessing
import os

# Binding
host = os.getenv("HOST", "0.0.0.0")
port = os.getenv("PORT", "8000")
bind = f"{host}:{port}"

# Worker Options
# Default to (2 * cpu) + 1, but allow override
workers_default = multiprocessing.cpu_count() * 2 + 1
workers = int(os.getenv("WORKERS", workers_default))
worker_class = "uvicorn.workers.UvicornWorker"

# Memory Leak Prevention
# Restart workers after a certain number of requests to limit memory leaks
max_requests = int(os.getenv("MAX_REQUESTS", 1000))
max_requests_jitter = int(os.getenv("MAX_REQUESTS_JITTER", 50))

# Timeouts
timeout = int(os.getenv("TIMEOUT", 120)) # Higher timeout for GenAI calls/model loading
keepalive = int(os.getenv("KEEPALIVE", 5))

# Logging
accesslog = os.getenv("ACCESS_LOG", "-")
errorlog = os.getenv("ERROR_LOG", "-")
loglevel = os.getenv("LOG_LEVEL", "info")

# Process Name
proc_name = "mathminds_api"
