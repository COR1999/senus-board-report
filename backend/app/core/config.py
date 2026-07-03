from functools import lru_cache
from typing import Optional
import os

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # Database
    DATABASE_URL: str = Field(
        default="postgresql://user:password@localhost/senus_board",
        description="PostgreSQL database URL"
    )

    # Gemini API
    GEMINI_API_KEY: Optional[str] = Field(
        default=None,
        description="Google Gemini API key"
    )

    # OpenAI API
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="OpenAI API key"
    )

    # Environment
    ENVIRONMENT: str = Field(
        default="development",
        description="Application environment"
    )

    # Application
    APP_NAME: str = "Senus Board Intelligence Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # CORS - Dynamic configuration
    FRONTEND_URL: str = Field(
        default="http://localhost:3000",
        description="Frontend application URL"
    )

    # Logging
    log_level: str = "INFO"

    @property
    def allowed_origins(self) -> list:
        """Get allowed CORS origins based on environment."""
        origins = [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            self.FRONTEND_URL,
            "https://senus-board.vercel.app",
        ]
        
        # Allow all origins in development
        if self.DEBUG or self.ENVIRONMENT == "development":
            origins.append("*")
        
        return list(set(origins))  # Remove duplicates


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()