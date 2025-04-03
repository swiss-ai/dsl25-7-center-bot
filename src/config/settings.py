from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Slack settings
    SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN", "")
    SLACK_SIGNING_SECRET: str = os.getenv("SLACK_SIGNING_SECRET", "")
    
    # Claude settings
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = "claude-3-opus-20240229"
    
    # Rate limiting
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("true", "1", "t")
    MAX_REQUESTS_PER_MINUTE: int = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "100"))
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "sqlite:///./aicenter.db"  # SQLite default for development
    )
    SQL_ECHO: bool = os.getenv("SQL_ECHO", "false").lower() in ("true", "1", "t")
    
    # Redis
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL")
    USE_REDIS: bool = REDIS_URL is not None
    
    # Vector Database
    CHROMA_PERSIST_DIRECTORY: str = os.getenv("CHROMA_PERSIST_DIRECTORY", "./chroma_db")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    
    # Google Drive - Legacy direct integration
    GOOGLE_CREDENTIALS_PATH: Optional[str] = os.getenv("GOOGLE_CREDENTIALS_PATH")
    GOOGLE_TOKEN_PATH: Optional[str] = os.getenv("GOOGLE_TOKEN_PATH")
    
    # MCP Google Drive Integration
    MCP_GDRIVE_ENABLED: bool = os.getenv("MCP_GDRIVE_ENABLED", "false").lower() in ("true", "1", "t")
    MCP_CONFIG_PATH: Optional[str] = os.getenv("MCP_CONFIG_PATH")
    
    # Web Content Integration
    WEB_CONTENT_ENABLED: bool = os.getenv("WEB_CONTENT_ENABLED", "false").lower() in ("true", "1", "t")
    WEB_CONTENT_URLS_FILE: str = os.getenv("WEB_CONTENT_URLS_FILE", "web_content_urls.txt")
    WEB_CONTENT_SYNC_INTERVAL: int = int(os.getenv("WEB_CONTENT_SYNC_INTERVAL", "86400"))  # Default: once per day in seconds
    
    # Firecrawl Integration
    FIRECRAWL_ENABLED: bool = os.getenv("FIRECRAWL_ENABLED", "false").lower() in ("true", "1", "t")
    FIRECRAWL_CONFIG_PATH: str = os.getenv("FIRECRAWL_CONFIG_PATH", "crawl_config.yaml")

settings = Settings()

# Validate critical settings
def validate_settings():
    missing_settings = []
    
    if not settings.SLACK_BOT_TOKEN:
        missing_settings.append("SLACK_BOT_TOKEN")
    
    if not settings.SLACK_SIGNING_SECRET:
        missing_settings.append("SLACK_SIGNING_SECRET")
    
    if not settings.ANTHROPIC_API_KEY:
        missing_settings.append("ANTHROPIC_API_KEY")
    
    if missing_settings:
        missing = ", ".join(missing_settings)
        raise ValueError(f"Missing required environment variables: {missing}")