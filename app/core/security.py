import logging
from fastapi import HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.settings import settings
from app.core.auth_utils import decode_access_token

logger = logging.getLogger(__name__)

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """
    Verifies the Local JWT access token.
    Returns the decoded token dict if valid.
    """
    token = credentials.credentials
    
    # -----------------------------------------------------
    # MOCK AUTH FOR DEVELOPMENT
    # If ENABLE_AUTH is False or token starts with "mock_" AND we are in development
    # -----------------------------------------------------
    is_dev = settings.ENV == "development"
    if not settings.ENABLE_AUTH or (token.startswith("mock_") and is_dev):
        logger.info(f"Using MOCK AUTH for token: {token}")
        return {"uid": "dev_user_123", "email": "dev@mathminds.ai"}

    # Use local JWT verification
    payload = decode_access_token(token)
    if payload:
        # Map 'sub' from JWT to 'uid' to maintain compatibility with existing code
        return {
            "uid": payload.get("sub"),
            "email": payload.get("email")
        }
    
    logger.warning(f"Invalid or expired token provided.")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

def get_current_user(token: dict = Security(verify_token)):
    """
    Dependency to get the current user from the token.
    """
    return token
