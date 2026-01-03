"""Application configuration using Pydantic Settings"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/aidomains"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    # External APIs
    ct_log_api: str = "https://crt.sh"
    anthropic_api_key: Optional[str] = None  # Claude AI API key for LLM evaluation

    # Discovery Settings
    discovery_schedule: str = "0 9,14,20 * * *"
    max_concurrent_validations: int = 10
    domain_timeout: int = 2

    # Smart Pipeline Thresholds
    investigation_score_threshold: int = 50  # Lower for aggressive mode
    enrichment_score_threshold: int = 35     # Lower for aggressive mode (was 70)

    # Concurrency Limits (per T3_MEDIUM_OPTIMIZATION.md)
    max_concurrent_investigations: int = 3
    max_concurrent_enrichments: int = 2

    # Screenshot/Enrichment Settings
    screenshot_enabled: bool = True
    screenshot_timeout: int = 30
    screenshot_storage: str = "s3"

    # AWS S3 Configuration
    aws_s3_bucket: str = ""
    aws_s3_region: str = "us-east-1"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None

    # Retry Settings
    retry_network_errors: bool = True
    max_retries: int = 3
    retry_backoff_base: float = 2.0

    # Alert Settings
    alert_email: Optional[str] = None

    # Timezone
    tz: str = "UTC"

    # Security Settings
    allowed_origins: str = "http://localhost:3000"
    api_key_enabled: bool = False
    api_keys: Optional[str] = None

    # MCP Services
    brave_search_api_key: Optional[str] = None

    # GitHub Discovery (increases rate limit from 60/hr to 5000/hr)
    github_token: Optional[str] = None

    # LLM Scoring Mode (aggressive, moderate, conservative)
    llm_scoring_mode: str = "aggressive"

    # LLM Model configuration (Claude 3.5 Sonnet for vision + better reasoning)
    llm_model: str = "claude-3-5-sonnet-20241022"

    # Training data directory
    training_data_dir: str = "./training_data"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )


# Global settings instance
settings = Settings()
