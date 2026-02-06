from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """
    Application Settings validated by Pydantic.
    Reads from environment variables and .env file.
    """
    # Core API Keys (Required)
    GOOGLE_API_KEY: str
    
    # Database (Required for production, optional for dev if mocked)
    MONGO_URI: str = "mongodb://localhost:27017/"
    MONGO_DB_NAME: str = "mathminds_db"
    
    # Cache
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # API Config
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    TIMEOUT_SECONDS: int = 120
    
    # Feature Flags
    ENABLE_LOCAL_MODELS: bool = True
    ENABLE_CACHE: bool = True

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore" # Ignore extra env vars
    }

# Singleton instance
settings = Settings()
