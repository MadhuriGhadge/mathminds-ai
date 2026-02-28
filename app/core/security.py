import logging
import firebase_admin
from firebase_admin import auth, credentials as firebase_credentials
from fastapi import HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.settings import settings

logger = logging.getLogger(__name__)

# Initialize Firebase Admin
_firebase_initialized = False
try:
    if settings.FIREBASE_CREDENTIALS_PATH:
        cred = firebase_credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        logger.info("Firebase Admin initialized successfully.")
    else:
        # Try default/env initialization
        firebase_admin.initialize_app()
        _firebase_initialized = True
        logger.info("Firebase Admin initialized using default credentials.")
except Exception as e:
    logger.warning(f"Firebase Admin initialization skipped or failed: {e}")

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """
    Verifies the Firebase ID Token.
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

    if not _firebase_initialized:
        logger.error("Attempted to verify token but Firebase is not initialized.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        )

    try:
        # Verify the ID token from Firebase
        decoded_token = auth.verify_id_token(token)
        return {
            "uid": decoded_token.get("uid"),
            "email": decoded_token.get("email")
        }
    except Exception as e:
        logger.warning(f"Firebase token verification failed: {e}")
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
