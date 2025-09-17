"""
Application settings using pydantic-settings.

Centralizes configuration for local/dev and Cloud Run production deployment.
Supports Google Secret Manager integration and environment-based configuration.
"""

import os
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, computed_field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App Configuration
    ENVIRONMENT: str = Field(default="development", description="Environment: development, staging, production")
    DEBUG: bool = Field(default=True, description="Enable debug mode")
    LOG_LEVEL: str = Field(default="info", description="Logging level")

    # Claude LLM Configuration
    ANTHROPIC_API_KEY: str | None = Field(default=None, description="Anthropic API key for Claude")
    CLAUDE_MODEL: str = Field(default="claude-3-5-sonnet-20241022", description="Claude model to use")

    # Database Configuration
    DATABASE_URL: str = Field(default="sqlite:///./clinic.db", description="Database connection URL")
    DB_ECHO: bool = Field(default=False, description="Enable SQLAlchemy query logging")

    # Server Configuration
    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=8080, description="Server port (8080 for Cloud Run)")
    
    # CORS Configuration
    CORS_ORIGINS_STR: str = Field(default="*", description="Comma-separated CORS origins")
    
    @computed_field
    @property
    def CORS_ORIGINS(self) -> List[str]:
        """Parse CORS origins from string to list."""
        if self.CORS_ORIGINS_STR == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS_STR.split(",") if origin.strip()]

    # Security & Rate Limiting
    RATE_LIMIT_VERIFIED_PER_MIN: int = Field(default=30, description="Rate limit for verified users")
    RATE_LIMIT_UNVERIFIED_PER_MIN: int = Field(default=10, description="Rate limit for unverified users")
    
    # Health Check Configuration
    STARTUP_TIMEOUT_SECONDS: int = Field(default=300, description="Startup timeout for production")
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


