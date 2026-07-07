from functools import lru_cache
from typing import Optional
import os

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # `extra="ignore"` so undeclared vars in .env (e.g. platform-injected
    # vars on Railway) don't crash startup with a validation error.
    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

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

    # Which Gemini model to call -- not hardcoded, since a pinned version
    # (e.g. "gemini-2.0-flash") can lose free-tier quota eligibility on
    # Google's side without any code change on ours (confirmed directly
    # against the real API while debugging the frontend's own Gemini
    # integration -- see frontend's GEMINI_INSIGHTS_MODEL for the same
    # reasoning). Swapping models is then just an env var change, not a
    # redeploy. Read directly via os.getenv in GeminiAnalysisService,
    # declared here too so it's documented and so setting it never fails
    # validation, matching the pattern below.
    GEMINI_MODEL: str = Field(
        default="gemini-2.0-flash",
        description="Gemini model used for financial document analysis"
    )

    # Gemini proactive rate limiting -- read directly via os.getenv in
    # GeminiAnalysisService, declared here too so they're documented and
    # so setting them (as .env.example instructs) never fails validation.
    GEMINI_MAX_CALLS_PER_MINUTE: int = Field(
        default=10,
        description="Proactive per-minute cap on Gemini API calls"
    )
    GEMINI_MAX_CALLS_PER_DAY: int = Field(
        default=1000,
        description="Proactive rolling 24h cap on Gemini API calls"
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
            "https://senus-board-report.vercel.app",
        ]
        
        # Allow all origins in development
        if self.DEBUG or self.ENVIRONMENT == "development":
            origins.append("*")
        
        return list(set(origins))  # Remove duplicates


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()