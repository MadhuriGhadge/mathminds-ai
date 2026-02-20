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

    
    # Environment
    ENV: str = "development" # development, staging, production

    # Database (Required)
    MONGO_URI: Optional[str] = None
    MONGO_DB_NAME: str = "mathminds_db"
    
    # Cache
    REDIS_URL: Optional[str] = None
    
    # API Config
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    TIMEOUT_SECONDS: int = 120
    
    # Feature Flags
    ENABLE_LOCAL_MODELS: bool = True
    ENABLE_CACHE: bool = True
    ENABLE_AUTH: bool = True
    MAX_LLM_CALLS_PER_DAY: int = 18 # Default limit per user per day

    # Integrations
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None
    WOLFRAM_APP_ID: Optional[str] = None

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
                 # Warning for now, might be critical depending on usage
                 pass 

        # Set Defaults for Development
        else:
            if not self.MONGO_URI:
                self.MONGO_URI = "mongodb://localhost:27017/"
            if not self.REDIS_URL:
                self.REDIS_URL = "redis://localhost:6379/0"
        
        return self

# Singleton instance
settings = Settings()
