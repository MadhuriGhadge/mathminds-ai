from pydantic_settings import BaseSettings
from pydantic import model_validator
from typing import Optional

class Settings(BaseSettings):
    """
    Application Settings validated by Pydantic.
    Reads from environment variables and .env file.
    """
    # Core API Keys (Required)
    GOOGLE_API_KEY: str
    GOOGLE_CLOUD_PROJECT: Optional[str] = None
    
    # Vertex AI Search (Grounding/Discovery Engine)
    VERTEX_SEARCH_PROJECT_ID: Optional[str] = None
    VERTEX_SEARCH_LOCATION: str = "global"
    VERTEX_SEARCH_DATA_STORE_ID: Optional[str] = None

    
    # Environment
    ENV: str = "development" # development, staging, production

    # Database (Required)
    MONGO_URI: Optional[str] = None
    MONGO_DB_NAME: str = "mathminds_db"
    
    # Cache
    REDIS_URL: Optional[str] = None
    
    # API Config
    API_HOST: str = "0.0.0.0"
    PORT: int = 8000  # Standard Render/Cloud Run env var
    LOG_LEVEL: str = "INFO"
    TIMEOUT_SECONDS: int = 120
    
    # Feature Flags
    ENABLE_LOCAL_MODELS: bool = True
    ENABLE_CACHE: bool = True
    ENABLE_AUTH: bool = True
    MAX_LLM_CALLS_PER_DAY: int = 100 # Default limit per user per day

    # Integrations
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None
    WOLFRAM_APP_ID: Optional[str] = None
    N8N_WEBHOOK_URL: Optional[str] = None

    # Security
    JWT_SECRET_KEY: str = "super_secret_key_change_me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 1 Week

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore" # Ignore extra env vars
    }

    @model_validator(mode='after')
    def set_defaults_and_validate(self):
        # Enforce Production Constraints
        if self.ENV == "production":
            if not self.MONGO_URI:
                raise ValueError("MONGO_URI must be set in production environment")
            if not self.REDIS_URL:
                raise ValueError("REDIS_URL must be set in production environment")
            if not self.FIREBASE_CREDENTIALS_PATH:
                raise ValueError("FIREBASE_CREDENTIALS_PATH must be set in production environment")
            if not self.VERTEX_SEARCH_DATA_STORE_ID:
                # We allow it to be empty if the user wants to fallback to scraping, 
                # but for 100% production readiness we should warn.
                logger.warning("VERTEX_SEARCH_DATA_STORE_ID is not set. Scraper will use fallback logic.")

        # Set Defaults for Development
        else:
            if not self.MONGO_URI:
                self.MONGO_URI = "mongodb://localhost:27017/"
            if not self.REDIS_URL:
                self.REDIS_URL = "redis://localhost:6379/0"
        
        return self

# Singleton instance
settings = Settings()
