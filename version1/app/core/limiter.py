from slowapi import Limiter
from slowapi.util import get_remote_address

# Initialize Limiter
# We use the client's IP address (get_remote_address) as the default identifier for rate limiting.
limiter = Limiter(key_func=get_remote_address)
