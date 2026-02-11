import logging
import firebase_admin
from firebase_admin import credentials, auth
from fastapi import HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.settings import settings

logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
try:
    if settings.FIREBASE_CREDENTIALS_PATH:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialized successfully.")
    else:
        logger.warning("FIREBASE_CREDENTIALS_PATH not set. Auth will fail if enabled.")
except Exception as e:
    logger.error(f"Failed to initialize Firebase: {e}")

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """
    Verifies the Firebase ID token.
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

    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        logger.warning(f"Auth failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_current_user(token: dict = Security(verify_token)):
    """
    Dependency to get the current user from the token.
    """
    return token
