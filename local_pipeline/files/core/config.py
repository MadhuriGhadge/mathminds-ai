"""
Configuration for MathMinds AI.

This module provides configuration options that can be adjusted based on
the environment (Windows vs Unix, development vs production, etc.).
"""
import os
import sys
import platform


class Config:
    """
    Global configuration for MathMinds AI.
    """
    
    # LLM Configuration
    LLM_MODEL = os.getenv("MATHMINDS_MODEL", "qwen2.5:3b-instruct-q4_K_M")
    LLM_TIMEOUT = int(os.getenv("MATHMINDS_TIMEOUT", "120"))
    LLM_BASE_URL = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    
    # Execution Configuration
    EXEC_TIMEOUT = int(os.getenv("MATHMINDS_EXEC_TIMEOUT", "8"))
    
    # Execution Method: 'auto', 'multiprocessing', or 'threading'
    # 'auto' will choose based on platform
    # 'multiprocessing' is more secure but can have issues on Windows
    # 'threading' is simpler but provides less isolation
    EXEC_METHOD = os.getenv("MATHMINDS_EXEC_METHOD", "auto")
    
    # Logging
    LOG_LEVEL = os.getenv("MATHMINDS_LOG_LEVEL", "INFO")
    
    @classmethod
    def get_exec_method(cls) -> str:
        """
        Determine which execution method to use.
        Returns 'multiprocessing' or 'threading'.
        """
        if cls.EXEC_METHOD == "auto":
            # On Windows, prefer threading due to spawn issues
            # On Unix, prefer multiprocessing for better isolation
            if platform.system() == "Windows":
                return "threading"
            else:
                return "multiprocessing"
        elif cls.EXEC_METHOD in ["multiprocessing", "threading"]:
            return cls.EXEC_METHOD
        else:
            # Default to threading for safety
            return "threading"
    
    @classmethod
    def is_windows(cls) -> bool:
        """Check if running on Windows."""
        return platform.system() == "Windows"
    
    @classmethod
    def summary(cls) -> str:
        """Return a summary of current configuration."""
        return f"""
MathMinds AI Configuration:
---------------------------
LLM Model:        {cls.LLM_MODEL}
LLM Timeout:      {cls.LLM_TIMEOUT}s
LLM Base URL:     {cls.LLM_BASE_URL}
Exec Timeout:     {cls.EXEC_TIMEOUT}s
Exec Method:      {cls.get_exec_method()} (configured: {cls.EXEC_METHOD})
Platform:         {platform.system()} {platform.release()}
Log Level:        {cls.LOG_LEVEL}
"""


# Create a global config instance
config = Config()